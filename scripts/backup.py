"""Encrypted PostgreSQL and managed-cover backup. Run only from private operations repository."""

import argparse
import hashlib
import io
import json
import os
import secrets
import struct
import subprocess
import tarfile
import tempfile
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
    public_ids: tuple[str, ...], directory: Path, max_total_bytes: int
) -> tuple[list[dict], dict[str, tuple]]:
    import cloudinary.api
    import httpx

    result = []
    fingerprints = {}
    total = 0
    with httpx.Client(
        timeout=httpx.Timeout(30.0, connect=10.0), follow_redirects=False
    ) as client:
        for index, public_id in enumerate(public_ids):
            try:
                resource = cloudinary.api.resource(public_id)
            except Exception:  # noqa: BLE001 - provider errors can contain signed URLs
                raise RuntimeError("Falha ao consultar uma mídia Cloudinary.") from None
            fingerprint = _cloudinary_fingerprint(resource)
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
            fingerprints[public_id] = fingerprint
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
        or not isinstance(byte_count, int)
        or isinstance(byte_count, bool)
        or byte_count < 0
    ):
        raise RuntimeError("Cloudinary não forneceu a versão verificável da mídia.")
    return asset_id, version, byte_count, resource.get("format")


def _assert_cloudinary_unchanged(fingerprints: dict[str, tuple]) -> None:
    import cloudinary.api

    for public_id, expected in fingerprints.items():
        try:
            actual = _cloudinary_fingerprint(cloudinary.api.resource(public_id))
        except Exception:  # noqa: BLE001 - provider errors can contain signed URLs
            raise RuntimeError(
                "Mídia Cloudinary ausente ou indisponível após o download."
            ) from None
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
            media, media_fingerprints = _download_media(public_ids_before, root, limit)
            _assert_cloudinary_unchanged(media_fingerprints)
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
