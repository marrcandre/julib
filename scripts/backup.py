"""Encrypted PostgreSQL and managed-cover backup. Run only from private operations repository."""

import argparse
import calendar
import hashlib
import io
import json
import os
import re
import secrets
import struct
import subprocess
import tarfile
import tempfile
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

MAGIC = b"JULIB01"
DEFAULT_MAX_BYTES = 50 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024
MAX_MANIFEST_BYTES = 2 * 1024 * 1024
MAX_MEDIA_BYTES = 8 * 1024 * 1024
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 10_000
CLOUDINARY_BATCH_SIZE = 100
CLOUDINARY_MAX_ATTEMPTS = 3
CLOUDINARY_MAX_RATE_WAIT_SECONDS = 600


class BackupLimitError(RuntimeError):
    pass


def keypair() -> tuple[bytes, bytes]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    return (
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
        key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        ),
    )


def _rsa_public_key(pem: bytes) -> rsa.RSAPublicKey:
    key = serialization.load_pem_public_key(pem)
    if not isinstance(key, rsa.RSAPublicKey):
        raise ValueError("A chave pública de cifragem precisa ser RSA.")  # noqa: TRY004
    return key


def _rsa_private_key(pem: bytes) -> rsa.RSAPrivateKey:
    key = serialization.load_pem_private_key(pem, password=None)
    if not isinstance(key, rsa.RSAPrivateKey):
        raise ValueError("A chave privada de recuperação precisa ser RSA.")  # noqa: TRY004
    return key


def encrypt(data: bytes, public_pem: bytes) -> bytes:
    key = secrets.token_bytes(32)
    nonce = secrets.token_bytes(12)
    public = _rsa_public_key(public_pem)
    encrypted_key = public.encrypt(
        key,
        padding.OAEP(
            mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None
        ),
    )
    encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    encryptor.authenticate_additional_data(MAGIC)
    return (
        MAGIC
        + struct.pack(">H", len(encrypted_key))
        + encrypted_key
        + nonce
        + encryptor.update(data)
        + encryptor.finalize()
        + encryptor.tag
    )


def decrypt(data: bytes, private_pem: bytes) -> bytes:
    if len(data) < 9 or not data.startswith(MAGIC):
        raise ValueError("Formato de backup inválido.")
    size = struct.unpack(">H", data[7:9])[0]
    offset = 9 + size
    if size < 256 or offset + 12 + 16 > len(data):
        raise ValueError("Formato de backup inválido.")
    private = _rsa_private_key(private_pem)
    key = private.decrypt(
        data[9:offset],
        padding.OAEP(
            mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None
        ),
    )
    decryptor = Cipher(
        algorithms.AES(key), modes.GCM(data[offset : offset + 12], data[-16:])
    ).decryptor()
    decryptor.authenticate_additional_data(MAGIC)
    try:
        return decryptor.update(data[offset + 12 : -16]) + decryptor.finalize()
    except InvalidTag as exc:
        raise ValueError("Autenticação do backup inválida.") from exc


def encrypt_file(
    source: Path, destination: Path, public_pem: bytes, max_bytes: int
) -> int:
    destination.parent.mkdir(parents=True, exist_ok=True)
    key = secrets.token_bytes(32)
    nonce = secrets.token_bytes(12)
    public = _rsa_public_key(public_pem)
    wrapped = public.encrypt(
        key,
        padding.OAEP(
            mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None
        ),
    )
    header = MAGIC + struct.pack(">H", len(wrapped)) + wrapped + nonce
    if source.stat().st_size + len(header) + 16 > max_bytes:
        raise RuntimeError("Pacote cifrado excederia o limite configurado.")
    fd, temp_path = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    try:
        os.fchmod(fd, 0o600)
        encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
        encryptor.authenticate_additional_data(MAGIC)
        size = len(header) + 16
        with os.fdopen(fd, "wb") as out, source.open("rb") as inp:
            out.write(header)
            while chunk := inp.read(CHUNK_SIZE):
                encrypted = encryptor.update(chunk)
                size += len(encrypted)
                if size > max_bytes:
                    raise RuntimeError("Pacote cifrado excedeu o limite configurado.")
                out.write(encrypted)
            tail = encryptor.finalize()
            size += len(tail) + len(encryptor.tag)
            if size > max_bytes:
                raise RuntimeError("Pacote cifrado excedeu o limite configurado.")
            out.write(tail)
            out.write(encryptor.tag)
            out.flush()
            os.fsync(out.fileno())
        os.link(temp_path, destination)
        Path(temp_path).unlink()
        return size
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        Path(temp_path).unlink(missing_ok=True)
        raise


def decrypt_file(source: Path, destination: Path, private_pem: bytes) -> int:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    try:
        os.fchmod(fd, 0o600)
        with source.open("rb") as inp:
            prefix = inp.read(9)
            if len(prefix) < 9 or prefix[:7] != MAGIC:
                raise ValueError("Formato de backup inválido.")
            wrapped_size = struct.unpack(">H", prefix[7:9])[0]
            if wrapped_size < 256 or wrapped_size > 1024:
                raise ValueError("Formato de backup inválido.")
            wrapped = inp.read(wrapped_size)
            nonce = inp.read(12)
            if len(wrapped) != wrapped_size or len(nonce) != 12:
                raise ValueError("Formato de backup truncado.")
            end = inp.seek(0, os.SEEK_END)
            ciphertext_size = end - (9 + wrapped_size + 12 + 16)
            if ciphertext_size < 0:
                raise ValueError("Formato de backup truncado.")
            inp.seek(end - 16)
            tag = inp.read(16)
            inp.seek(9 + wrapped_size + 12)
            private = _rsa_private_key(private_pem)
            key = private.decrypt(
                wrapped,
                padding.OAEP(
                    mgf=padding.MGF1(hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )
            decryptor = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor()
            decryptor.authenticate_additional_data(MAGIC)
            remaining = ciphertext_size
            written = 0
            with os.fdopen(fd, "wb") as out:
                while remaining:
                    chunk = inp.read(min(CHUNK_SIZE, remaining))
                    if not chunk:
                        raise ValueError("Formato de backup truncado.")
                    remaining -= len(chunk)
                    plain = decryptor.update(chunk)
                    out.write(plain)
                    written += len(plain)
                try:
                    tail = decryptor.finalize()
                except InvalidTag as exc:
                    raise ValueError("Autenticação do backup inválida.") from exc
                out.write(tail)
                written += len(tail)
                out.flush()
                os.fsync(out.fileno())
        os.link(temp_path, destination)
        Path(temp_path).unlink()
        return written
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        Path(temp_path).unlink(missing_ok=True)
        raise


def add_bytes(archive: tarfile.TarFile, name: str, data: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = 0o600
    archive.addfile(info, io.BytesIO(data))


def _passfile_escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("*", "\\*")
        .replace("?", "\\?")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )


def _connection_parts(database: str) -> tuple[str, str, str, str, str, str]:
    parsed = urlsplit(database)
    if (
        parsed.scheme not in ("postgres", "postgresql")
        or not parsed.hostname
        or parsed.username is None
        or parsed.password is None
    ):
        raise ValueError(
            "BACKUP_DATABASE_URL deve ser uma URL PostgreSQL com usuário e senha."
        )
    host = parsed.hostname
    host_for_url = f"[{host}]" if ":" in host else host
    port = str(parsed.port or 5432)
    query = parse_qsl(parsed.query, keep_blank_values=True)
    safe_query_keys = {
        "sslmode",
        "sslrootcert",
        "sslcert",
        "sslkey",
        "connect_timeout",
        "target_session_attrs",
        "channel_binding",
        "gssencmode",
    }
    if any(key.lower() not in safe_query_keys for key, _ in query):
        raise ValueError(
            "BACKUP_DATABASE_URL contém parâmetros não permitidos na query."
        )
    dbname = unquote(parsed.path.lstrip("/"))
    username = unquote(parsed.username)
    password = unquote(parsed.password)
    if not dbname or any(
        "\n" in x or "\r" in x for x in (host, dbname, username, password)
    ):
        raise ValueError("BACKUP_DATABASE_URL tem campos inválidos.")
    safe = urlunsplit(
        (
            parsed.scheme,
            f"{parsed.username}@{host_for_url}:{port}",
            parsed.path,
            urlencode(query),
            "",
        )
    )
    return safe, host, port, dbname, username, password


def dump_database(
    database: str, output: Path, max_bytes: int, temp_dir: Path | None = None
) -> None:
    safe_database, host, port, dbname, username, password = _connection_parts(database)
    environment = os.environ.copy()
    for name in (
        "PGPASSWORD",
        "DATABASE_URL",
        "MIGRATION_DATABASE_URL",
        "BACKUP_DATABASE_URL",
    ):
        environment.pop(name, None)
    pgoptions = environment.get("PGOPTIONS", "").strip()
    environment["PGOPTIONS"] = (
        f"{pgoptions} -c default_transaction_read_only=on".strip()
    )
    fd, passfile = tempfile.mkstemp(prefix=".pgpass-", dir=temp_dir)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(
                ":".join(
                    _passfile_escape(x)
                    for x in (host, port, dbname, username, password)
                )
                + "\n"
            )
        fd = -1
        environment["PGPASSFILE"] = passfile
        process = subprocess.Popen(
            [
                "pg_dump",
                safe_database,
                "--schema=public",
                "--format=custom",
                "--no-owner",
                "--no-acl",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=environment,
        )
        try:
            assert process.stdout is not None
            with process.stdout, output.open("xb") as stream:
                os.chmod(output, 0o600)
                size = 0
                while chunk := process.stdout.read(CHUNK_SIZE):
                    size += len(chunk)
                    if size > max_bytes:
                        process.terminate()
                        process.wait()
                        raise RuntimeError(
                            "Dump PostgreSQL excedeu o limite configurado."
                        )
                    stream.write(chunk)
                returncode = process.wait()
                if returncode != 0:
                    raise RuntimeError(
                        f"pg_dump falhou com código {returncode}; saída omitida para proteger credenciais."
                    )
                if size == 0:
                    raise RuntimeError("pg_dump produziu um arquivo vazio.")
        except BaseException:
            if process.poll() is None:
                process.terminate()
                process.wait()
            raise
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    finally:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
        Path(passfile).unlink(missing_ok=True)


@contextmanager
def read_only_transaction():
    from django.db import connection, transaction

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
        yield


def _media_ids(Book) -> tuple[str, ...]:
    with read_only_transaction():
        values = (
            Book.objects.exclude(cover_id="")
            .values_list("cover_id", flat=True)
            .distinct()
        )
        return tuple(sorted(values))


def assert_media_references_unchanged(
    expected: tuple[str, ...], actual: tuple[str, ...], phase: str
) -> None:
    if expected != actual:
        raise RuntimeError(
            f"Referências Cloudinary mudaram {phase}; backup interrompido."
        )


def _download_media(
    public_ids: tuple[str, ...],
    directory: Path,
    max_total_bytes: int,
    rate_budget: dict | None = None,
) -> tuple[list[dict], dict[str, tuple]]:
    import httpx

    result = []
    resources = _cloudinary_metadata(public_ids, rate_budget=rate_budget)
    fingerprints = {
        public_id: _cloudinary_fingerprint(resources[public_id])
        for public_id in public_ids
    }
    total = 0
    with httpx.Client(
        timeout=httpx.Timeout(30.0, connect=10.0), follow_redirects=False
    ) as client:
        for index, public_id in enumerate(public_ids):
            resource = resources[public_id]
            fingerprint = fingerprints[public_id]
            url = resource.get("secure_url", "")
            parsed_url = urlsplit(url) if isinstance(url, str) else None
            if (
                parsed_url is None
                or parsed_url.scheme != "https"
                or parsed_url.hostname != "res.cloudinary.com"
                or parsed_url.username is not None
            ):
                raise RuntimeError("Cloudinary retornou uma URL de mídia inválida.")
            extension = resource.get("format", "bin")
            if not isinstance(extension, str) or not extension.isalnum():
                extension = "bin"
            relative = f"media/{index}.{extension.lower()}"
            destination = directory / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256()
            size = 0
            try:
                with client.stream("GET", url) as response:
                    response.raise_for_status()
                    with destination.open("xb") as stream:
                        os.chmod(destination, 0o600)
                        for chunk in response.iter_bytes(CHUNK_SIZE):
                            size += len(chunk)
                            total += len(chunk)
                            if size > MAX_MEDIA_BYTES or total > max_total_bytes:
                                raise BackupLimitError(
                                    "Mídias Cloudinary excederam o limite configurado."
                                )
                            digest.update(chunk)
                            stream.write(chunk)
            except BackupLimitError:
                destination.unlink(missing_ok=True)
                raise
            except Exception:  # noqa: BLE001 - HTTP errors can contain signed URLs
                destination.unlink(missing_ok=True)
                raise RuntimeError(
                    "Falha ao baixar ou validar uma mídia Cloudinary."
                ) from None
            if size != fingerprint[2]:
                destination.unlink(missing_ok=True)
                raise RuntimeError(
                    "Tamanho baixado não corresponde à mídia Cloudinary."
                )
            result.append(
                {
                    "public_id": public_id,
                    "file": relative,
                    "size_bytes": size,
                    "sha256": digest.hexdigest(),
                }
            )
    return result, fingerprints


def _cloudinary_fingerprint(resource: dict) -> tuple:
    asset_id = resource.get("asset_id")
    version = resource.get("version")
    byte_count = resource.get("bytes")
    if (
        not isinstance(asset_id, str)
        or not asset_id
        or not isinstance(version, int)
        or isinstance(version, bool)
        or version <= 0
        or not isinstance(byte_count, int)
        or isinstance(byte_count, bool)
        or byte_count < 0
        or not isinstance(resource.get("format"), str)
        or not resource["format"]
    ):
        raise RuntimeError("Cloudinary não forneceu a versão verificável da mídia.")
    return asset_id, version, byte_count, resource["format"]


def _cloudinary_batches(public_ids: tuple[str, ...]):
    for start in range(0, len(public_ids), CLOUDINARY_BATCH_SIZE):
        yield public_ids[start : start + CLOUDINARY_BATCH_SIZE]


def _cloudinary_reset_epoch(value) -> float | None:
    if isinstance(value, time.struct_time):
        return float(calendar.timegm(value))
    if isinstance(value, (tuple, list)) and len(value) >= 6:
        try:
            return float(calendar.timegm(value))
        except (OverflowError, TypeError, ValueError):
            return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _cloudinary_reset_wait(rate_budget: dict, error: Exception | None = None) -> float:
    reset_epoch = _cloudinary_reset_epoch(rate_budget.get("reset_at"))
    headers = getattr(error, "headers", None) if error else None
    retry_after = None
    if headers:
        retry_after = headers.get("Retry-After") or headers.get("retry-after")
    if retry_after is not None:
        try:
            retry_epoch = time.time() + float(retry_after)
        except (TypeError, ValueError):
            try:
                from email.utils import parsedate_to_datetime

                retry_epoch = parsedate_to_datetime(str(retry_after)).timestamp()
            except (TypeError, ValueError, OverflowError):
                retry_epoch = None
        if retry_epoch is not None:
            reset_epoch = max(reset_epoch or retry_epoch, retry_epoch)
    if reset_epoch is None:
        raise RuntimeError(
            "Limite da Admin API Cloudinary sem indicador de reset; backup interrompido."
        ) from None
    delay = max(0.0, reset_epoch - time.time())
    if delay > CLOUDINARY_MAX_RATE_WAIT_SECONDS:
        raise RuntimeError(
            "Reset da Admin API Cloudinary excede o limite de espera; backup interrompido."
        ) from None
    return delay


def _cloudinary_has_reset_indicator(
    rate_budget: dict, error: Exception | None = None
) -> bool:
    if _cloudinary_reset_epoch(rate_budget.get("reset_at")) is not None:
        return True
    headers = getattr(error, "headers", None) if error else None
    return bool(headers and (headers.get("Retry-After") or headers.get("retry-after")))


def _bounded_cloudinary_sleep(rate_budget: dict, delay: float) -> None:
    remaining = rate_budget.setdefault(
        "wait_seconds_remaining", CLOUDINARY_MAX_RATE_WAIT_SECONDS
    )
    if delay > remaining:
        raise RuntimeError(
            "Espera acumulada da Admin API Cloudinary excede o orçamento total."
        ) from None
    rate_budget["wait_seconds_remaining"] = remaining - delay
    if delay:
        time.sleep(delay)


def _wait_for_cloudinary_reset(
    rate_budget: dict, error: Exception | None = None
) -> None:
    delay = _cloudinary_reset_wait(rate_budget, error)
    _bounded_cloudinary_sleep(rate_budget, delay)
    rate_budget["remaining"] = None
    rate_budget["reset_at"] = None


def _cloudinary_error_status(error: Exception) -> int | None:
    status = getattr(error, "http_code", None) or getattr(error, "status", None)
    if isinstance(status, int) and not isinstance(status, bool):
        return status
    match = re.match(r"Error (\d{3})\b", str(error))
    return int(match.group(1)) if match else None


def _cloudinary_api_batch(public_ids: tuple[str, ...], rate_budget: dict) -> dict:
    import cloudinary.api
    import cloudinary.exceptions

    for attempt in range(1, CLOUDINARY_MAX_ATTEMPTS + 1):
        remaining = rate_budget.get("remaining")
        calls_left = rate_budget.get("calls_remaining")
        if (
            isinstance(remaining, int)
            and not isinstance(remaining, bool)
            and isinstance(calls_left, int)
            and remaining < calls_left
        ):
            _wait_for_cloudinary_reset(rate_budget)
        try:
            response = cloudinary.api.resources_by_ids(list(public_ids))
        except cloudinary.exceptions.AuthorizationRequired:
            raise RuntimeError(
                "Cloudinary recusou a autenticação da Admin API."
            ) from None
        except cloudinary.exceptions.NotAllowed:
            raise RuntimeError(
                "Cloudinary recusou a autorização da Admin API."
            ) from None
        except cloudinary.exceptions.NotFound:
            raise RuntimeError("Mídia Cloudinary ausente na Admin API.") from None
        except cloudinary.exceptions.RateLimited as exc:
            if attempt == CLOUDINARY_MAX_ATTEMPTS:
                raise RuntimeError(
                    "Limite da Admin API Cloudinary persistiu após tentativas limitadas."
                ) from None
            if _cloudinary_has_reset_indicator(rate_budget, exc):
                _wait_for_cloudinary_reset(rate_budget, exc)
            else:
                _bounded_cloudinary_sleep(rate_budget, 2 ** (attempt - 1))
                rate_budget["remaining"] = None
                rate_budget["reset_at"] = None
            continue
        except Exception as exc:  # noqa: BLE001 - SDK errors may contain credentials
            status = _cloudinary_error_status(exc)
            invalid_response = str(exc).startswith("Error parsing server response")
            transient = not invalid_response and (status is None or status >= 500)
            if not transient or attempt == CLOUDINARY_MAX_ATTEMPTS:
                raise RuntimeError(
                    "Falha não transitória na consulta da Admin API Cloudinary."
                ) from None
            _bounded_cloudinary_sleep(rate_budget, 2 ** (attempt - 1))
            continue

        if isinstance(calls_left, int) and calls_left > 0:
            rate_budget["calls_remaining"] = calls_left - 1
        for field in ("rate_limit_remaining", "rate_limit_allowed"):
            value = getattr(response, field, None)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                key = "remaining" if field == "rate_limit_remaining" else "allowed"
                rate_budget[key] = value
        reset_at = getattr(response, "rate_limit_reset_at", None)
        if _cloudinary_reset_epoch(reset_at) is not None:
            rate_budget["reset_at"] = reset_at
        if not isinstance(response, dict) or not isinstance(
            response.get("resources"), list
        ):
            raise TypeError("Resposta inválida da Admin API Cloudinary.")
        return response
    raise RuntimeError("Admin API Cloudinary excedeu o limite de tentativas.")


def _cloudinary_metadata(
    public_ids: tuple[str, ...], rate_budget: dict | None = None
) -> dict[str, dict]:
    if len(set(public_ids)) != len(public_ids):
        raise RuntimeError("Lista de mídias contém IDs duplicados.")
    if not public_ids:
        return {}
    if rate_budget is None:
        rate_budget = {
            "calls_remaining": (len(public_ids) + CLOUDINARY_BATCH_SIZE - 1)
            // CLOUDINARY_BATCH_SIZE,
            "remaining": None,
            "reset_at": None,
            "allowed": None,
            "wait_seconds_remaining": CLOUDINARY_MAX_RATE_WAIT_SECONDS,
        }
    result = {}
    for batch in _cloudinary_batches(public_ids):
        response = _cloudinary_api_batch(batch, rate_budget)
        batch_expected = set(batch)
        batch_result = {}
        for resource in response["resources"]:
            if not isinstance(resource, dict):
                raise TypeError("Resposta inválida da Admin API Cloudinary.")
            public_id = resource.get("public_id")
            if not isinstance(public_id, str) or not public_id:
                raise RuntimeError("Resposta inválida da Admin API Cloudinary.")
            if public_id not in batch_expected:
                raise RuntimeError("Admin API Cloudinary retornou mídia inesperada.")
            if public_id in batch_result:
                raise RuntimeError("Admin API Cloudinary retornou mídia duplicada.")
            _cloudinary_fingerprint(resource)
            batch_result[public_id] = resource
        if set(batch_result) != batch_expected:
            raise RuntimeError("Mídia Cloudinary ausente ou resposta incompleta.")
        result.update(batch_result)
    if set(result) != set(public_ids):
        raise RuntimeError("Mídia Cloudinary ausente ou resposta incompleta.")
    return result


def _assert_cloudinary_unchanged(
    fingerprints: dict[str, tuple], rate_budget: dict | None = None
) -> None:
    public_ids = tuple(fingerprints)
    resources = _cloudinary_metadata(public_ids, rate_budget=rate_budget)
    for public_id, expected in fingerprints.items():
        actual = _cloudinary_fingerprint(resources[public_id])
        if actual != expected:
            raise RuntimeError(
                "Mídia Cloudinary mudou durante a cópia; backup interrompido."
            )


def _validate_archive(path: Path) -> dict:
    try:
        actual = {}
        manifest_data = None
        database_bytes = 0
        expanded = 0
        seen = set()
        with tarfile.open(path, mode="r|gz") as archive:
            for member in archive:
                pure = PurePosixPath(member.name)
                if (
                    member.name in seen
                    or member.size < 0
                    or pure.is_absolute()
                    or ".." in pure.parts
                    or pure.as_posix() != member.name
                    or not member.isfile()
                ):
                    raise ValueError("Arquivo de backup contém entradas inválidas.")
                seen.add(member.name)
                if len(seen) > MAX_ARCHIVE_ENTRIES:
                    raise ValueError(
                        "Pacote excedeu a quantidade permitida de arquivos."
                    )
                expanded += member.size
                if expanded > MAX_ARCHIVE_BYTES:
                    raise ValueError(
                        "Conteúdo descompactado excedeu o limite permitido."
                    )
                stream = archive.extractfile(member)
                if stream is None:
                    raise ValueError("Arquivo de backup inválido.")
                if member.name == "database.dump":
                    if member.size <= 0:
                        raise ValueError("Dump PostgreSQL vazio.")
                    database_bytes = member.size
                    while stream.read(CHUNK_SIZE):
                        pass
                elif member.name == "manifest.json":
                    if member.size > MAX_MANIFEST_BYTES:
                        raise ValueError("Manifesto excedeu o limite permitido.")
                    manifest_data = stream.read(MAX_MANIFEST_BYTES + 1)
                    if len(manifest_data) != member.size:
                        raise ValueError("Manifesto truncado.")
                elif pure.parts[0] == "media" and len(pure.parts) == 2:
                    digest = hashlib.sha256()
                    size = 0
                    while chunk := stream.read(CHUNK_SIZE):
                        digest.update(chunk)
                        size += len(chunk)
                    actual[member.name] = (size, digest.hexdigest())
                else:
                    raise ValueError("Pacote contém arquivo não esperado.")
        if database_bytes <= 0 or manifest_data is None:
            raise ValueError("Backup não contém dump e manifesto válidos.")
        manifest = json.loads(manifest_data)
        if not isinstance(manifest, dict):
            raise TypeError("Manifesto incompatível.")
        version = manifest.get("format")
        media = manifest.get("media")
        if (
            type(version) is not int
            or version not in (1, 2)
            or not isinstance(media, list)
        ):
            raise ValueError("Manifesto incompatível.")
        created_at = manifest.get("created_at")
        if not isinstance(created_at, str) or not created_at:
            raise ValueError("Data de geração ausente no manifesto.")
        media_names = set()
        public_ids = set()
        for entry in media:
            if not isinstance(entry, dict):
                raise TypeError("Manifesto de mídia inválido.")
            public_id = entry.get("public_id")
            name = entry.get("file")
            if (
                not isinstance(public_id, str)
                or not public_id
                or public_id in public_ids
                or not isinstance(name, str)
            ):
                raise ValueError("Manifesto de mídia duplicado ou inválido.")
            public_ids.add(public_id)
            pure = PurePosixPath(name)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or len(pure.parts) != 2
                or pure.parts[0] != "media"
                or name in media_names
            ):
                raise ValueError("Caminho de mídia inválido ou duplicado.")
            media_names.add(name)
            if name not in actual:
                raise ValueError("Arquivo de mídia ausente no pacote.")
            size, file_hash = actual[name]
            if version == 2:
                manifest_size = entry.get("size_bytes")
                manifest_hash = entry.get("sha256")
                if (
                    type(manifest_size) is not int
                    or manifest_size != size
                    or not isinstance(manifest_hash, str)
                    or manifest_hash != file_hash
                ):
                    raise ValueError(
                        "Tamanho ou SHA-256 de mídia não corresponde ao manifesto."
                    )
        if set(actual) != media_names:
            raise ValueError(
                "Pacote contém mídias ausentes ou não listadas no manifesto."
            )
        return {
            "format": version,
            "created_at": created_at,
            "media_count": len(media),
            "database_bytes": database_bytes,
        }
    except (
        tarfile.TarError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        IndexError,
    ) as exc:
        raise ValueError("Pacote de backup ou manifesto inválido.") from exc


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_backup(
    source: Path, private_pem: bytes, expected_sha256: str | None = None
) -> dict:
    if source.stat().st_size > DEFAULT_MAX_BYTES:
        raise ValueError("Arquivo cifrado excedeu o limite de verificação de 50 MiB.")
    digest = _sha256_file(source)
    if expected_sha256 is not None and (
        len(expected_sha256) != 64 or digest.lower() != expected_sha256.lower()
    ):
        raise ValueError("SHA-256 do arquivo cifrado não corresponde ao esperado.")
    with tempfile.TemporaryDirectory(prefix="julib-verify-") as work:
        os.chmod(work, 0o700)
        archive_path = Path(work) / "package.tar.gz"
        decrypt_file(source, archive_path, private_pem)
        summary = _validate_archive(archive_path)
    summary.update(encrypted_bytes=source.stat().st_size, sha256=digest)
    return summary


def backup(output: Path, public_key: Path, with_media: bool) -> None:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()
    from library.models import Book

    if with_media:
        from library.media import configure

        configure()
    database = os.environ["BACKUP_DATABASE_URL"]
    limit = int(os.environ.get("BACKUP_MAX_BYTES", str(DEFAULT_MAX_BYTES)))
    if limit <= 0:
        raise RuntimeError("BACKUP_MAX_BYTES deve ser positivo.")
    if limit > DEFAULT_MAX_BYTES:
        raise RuntimeError(
            "BACKUP_MAX_BYTES não pode exceder o limite aprovado de 50 MiB."
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    require_disk_space(output.parent, limit * 2 + 2 * 1024 * 1024)
    with tempfile.TemporaryDirectory(prefix="julib-backup-", dir=output.parent) as work:
        os.chmod(work, 0o700)
        root = Path(work)
        dump = root / "database.dump"
        media_dir = root / "media"
        media_dir.mkdir(mode=0o700)
        public_ids_before = _media_ids(Book) if with_media else ()
        if len(public_ids_before) + 2 > MAX_ARCHIVE_ENTRIES:
            raise RuntimeError("Quantidade de mídias excede o limite do manifesto.")
        dump_database(database, dump, limit, root)
        dump.chmod(0o600)
        public_ids_after_dump = _media_ids(Book) if with_media else public_ids_before
        assert_media_references_unchanged(
            public_ids_before, public_ids_after_dump, "durante o dump"
        )
        if with_media:
            batch_count = (
                len(public_ids_before) + CLOUDINARY_BATCH_SIZE - 1
            ) // CLOUDINARY_BATCH_SIZE
            rate_budget = {
                "calls_remaining": batch_count * 2,
                "remaining": None,
                "reset_at": None,
                "allowed": None,
                "wait_seconds_remaining": CLOUDINARY_MAX_RATE_WAIT_SECONDS,
            }
            media, media_fingerprints = _download_media(
                public_ids_before, root, limit, rate_budget=rate_budget
            )
            _assert_cloudinary_unchanged(media_fingerprints, rate_budget=rate_budget)
        else:
            media = []
        public_ids_after_media = _media_ids(Book) if with_media else public_ids_before
        assert_media_references_unchanged(
            public_ids_before, public_ids_after_media, "durante a cópia de mídia"
        )
        estimated_package = (
            dump.stat().st_size
            + sum(item["size_bytes"] for item in media)
            + 2 * 1024 * 1024
        )
        if estimated_package > MAX_ARCHIVE_BYTES:
            raise RuntimeError("Pacote descompactado excederia o limite de segurança.")
        if shutil_disk_free(root) < estimated_package + min(limit, estimated_package):
            raise RuntimeError(
                "Espaço temporário insuficiente para empacotar o backup."
            )
        manifest = {
            "created_at": datetime.now(UTC).isoformat(),
            "format": 2,
            "media": media,
        }
        archive_path = root / "package.tar.gz"
        with tarfile.open(archive_path, mode="w:gz") as archive:
            archive.add(dump, arcname="database.dump", recursive=False)
            for item in media:
                archive.add(root / item["file"], arcname=item["file"], recursive=False)
            add_bytes(
                archive,
                "manifest.json",
                json.dumps(manifest, separators=(",", ":")).encode(),
            )
        archive_path.chmod(0o600)
        _validate_archive(archive_path)
        encrypted_path = root / "backup.enc"
        size = encrypt_file(
            archive_path, encrypted_path, public_key.read_bytes(), limit
        )
        os.link(encrypted_path, output)
        output.chmod(0o600)
    print(f"Backup cifrado criado: {size} bytes. SHA-256: {_sha256_file(output)}.")


def shutil_disk_free(path: Path) -> int:
    stats = os.statvfs(path)
    return stats.f_bavail * stats.f_frsize


def require_disk_space(path: Path, required_bytes: int) -> None:
    if shutil_disk_free(path) < required_bytes:
        raise RuntimeError("Espaço temporário insuficiente para iniciar o backup.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    key = sub.add_parser("keygen")
    key.add_argument("--private", type=Path, required=True)
    key.add_argument("--public", type=Path, required=True)
    create = sub.add_parser("create")
    create.add_argument("--public", type=Path, required=True)
    create.add_argument("--output", type=Path, required=True)
    create.add_argument("--media", action="store_true")
    restore = sub.add_parser("decrypt")
    restore.add_argument("--private", type=Path, required=True)
    restore.add_argument("--input", type=Path, required=True)
    restore.add_argument("--output", type=Path, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--private", type=Path, required=True)
    verify.add_argument("--input", type=Path, required=True)
    verify.add_argument("--sha256")
    args = parser.parse_args()
    try:
        if args.command == "keygen":
            if args.private.exists() or args.public.exists():
                raise SystemExit("Não sobrescrever chaves existentes.")
            private, public = keypair()
            args.private.parent.mkdir(parents=True, exist_ok=True)
            args.public.parent.mkdir(parents=True, exist_ok=True)
            args.private.write_bytes(private)
            args.private.chmod(0o600)
            args.public.write_bytes(public)
            args.public.chmod(0o600)
        elif args.command == "create":
            backup(args.output, args.public, args.media)
        elif args.command == "decrypt":
            if args.output.exists():
                raise SystemExit("Destino de recuperação já existe.")
            decrypt_file(args.input, args.output, args.private.read_bytes())
            args.output.chmod(0o600)
        else:
            summary = verify_backup(args.input, args.private.read_bytes(), args.sha256)
            print(json.dumps(summary, sort_keys=True))
    except (RuntimeError, ValueError, OSError, InvalidTag) as exc:
        parser.exit(1, f"Falha segura no processamento do backup: {exc}\n")
    except Exception:  # noqa: BLE001 - provider/database exceptions may contain credentials
        parser.exit(
            1, "Falha segura no processamento do backup; detalhes foram omitidos.\n"
        )


if __name__ == "__main__":
    main()
