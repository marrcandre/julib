import hashlib
import importlib.util
import io
import json
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

spec = importlib.util.spec_from_file_location(
    "backup", Path(__file__).resolve().parents[2] / "scripts/backup.py"
)


def test_backup_public_key_envelope_roundtrip_and_tampering():
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    private, public = module.keypair()
    encrypted = module.encrypt(b"books and loans", public)
    assert b"books and loans" not in encrypted
    assert module.decrypt(encrypted, private) == b"books and loans"
    with pytest.raises(Exception):
        module.decrypt(encrypted[:-1] + bytes([encrypted[-1] ^ 1]), private)


def test_postgres_dump_runs_with_default_transaction_read_only(monkeypatch, tmp_path):
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    called = {}

    output = tmp_path / "dump.out"

    class Process:
        def __init__(self, data=b"dump", returncode=0):
            self.stdout = io.BytesIO(data)
            self.returncode = returncode

        def wait(self):
            return self.returncode

        def poll(self):
            return self.returncode

        def terminate(self):
            self.returncode = -15

    def fake_popen(command, *, stdout, stderr, env):
        called.update(command=command, stdout=stdout, stderr=stderr, env=env)
        called["passfile_data"] = Path(env["PGPASSFILE"]).read_text()
        called["passfile_mode"] = Path(env["PGPASSFILE"]).stat().st_mode & 0o777
        return Process()

    monkeypatch.setattr(module.subprocess, "Popen", fake_popen)
    monkeypatch.setenv("PGOPTIONS", "-c statement_timeout=30000")

    module.dump_database("postgresql://reader:secret@db.example/library", output, 100)
    assert called["stdout"] == module.subprocess.PIPE
    assert called["stderr"] == module.subprocess.DEVNULL
    assert not any("secret" in arg for arg in called["command"])
    assert "password" not in called["env"].get("DATABASE_URL", "")
    passfile = Path(called["env"]["PGPASSFILE"])
    assert called["passfile_data"].strip().endswith(":reader:secret")
    assert called["passfile_mode"] == 0o600
    assert not passfile.exists()
    assert "-c statement_timeout=30000" in called["env"]["PGOPTIONS"]
    assert "-c default_transaction_read_only=on" in called["env"]["PGOPTIONS"]


def test_pg_dump_failure_is_sanitized_and_cleans_password_file(monkeypatch, tmp_path):
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    observed = {}

    class Process:
        stdout = io.BytesIO()

        def wait(self):
            return 1

        def poll(self):
            return 1

        def terminate(self):
            pass

    def fake_popen(command, **kwargs):
        observed["passfile"] = Path(kwargs["env"]["PGPASSFILE"])
        observed["command"] = command
        return Process()

    monkeypatch.setattr(module.subprocess, "Popen", fake_popen)
    with pytest.raises(RuntimeError, match="pg_dump falhou") as error:
        module.dump_database(
            "postgresql://reader:secret@db.example/library", tmp_path / "dump", 100
        )
    assert "secret" not in str(error.value)
    assert "secret" not in " ".join(observed["command"])
    assert not observed["passfile"].exists()


def test_pg_dump_rejects_empty_successful_output(monkeypatch, tmp_path):
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class Process:
        stdout = io.BytesIO()

        def wait(self):
            return 0

        def poll(self):
            return 0

        def terminate(self):
            pass

    monkeypatch.setattr(module.subprocess, "Popen", lambda *args, **kwargs: Process())
    output = tmp_path / "dump"
    with pytest.raises(RuntimeError, match="arquivo vazio"):
        module.dump_database("postgresql://reader:secret@db.example/library", output, 100)
    assert not output.exists()


def test_pg_dump_size_limit_removes_dump_and_password_file(monkeypatch, tmp_path):
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    observed = {}

    class Process:
        stdout = io.BytesIO(b"too large")

        def __init__(self):
            self.returncode = None

        def wait(self):
            self.returncode = -15
            return self.returncode

        def poll(self):
            return self.returncode

        def terminate(self):
            self.returncode = -15

    def fake_popen(command, **kwargs):
        observed["passfile"] = Path(kwargs["env"]["PGPASSFILE"])
        return Process()

    monkeypatch.setattr(module.subprocess, "Popen", fake_popen)
    output = tmp_path / "dump"
    with pytest.raises(RuntimeError, match="excedeu o limite"):
        module.dump_database("postgresql://reader:secret@db.example/library", output, 2)
    assert not output.exists()
    assert not observed["passfile"].exists()


def test_pgpassfile_escapes_special_characters_and_clears_password_env(monkeypatch, tmp_path):
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    observed = {}

    class Process:
        stdout = io.BytesIO(b"dump")

        def wait(self):
            return 0

        def poll(self):
            return 0

        def terminate(self):
            pass

    def fake_popen(command, *, stdout, stderr, env):
        observed.update(command=command, env=env)
        observed["passfile_data"] = Path(env["PGPASSFILE"]).read_text()
        return Process()

    monkeypatch.setattr(module.subprocess, "Popen", fake_popen)
    monkeypatch.setenv("PGPASSWORD", "inherited-secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql://other:also-secret@old/db")
    module.dump_database(
        "postgresql://reader:p%3Aa%5Css@db.example:6543/library", tmp_path / "dump", 100
    )
    assert "PGPASSWORD" not in observed["env"]
    assert "DATABASE_URL" not in observed["env"]
    assert "BACKUP_DATABASE_URL" not in observed["env"]
    assert observed["passfile_data"] == r"db.example:6543:library:reader:p\:a\\ss" + "\n"
    assert "p:a\\ss" not in " ".join(observed["command"])


def test_database_url_rejects_secret_bearing_query_parameters():
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with pytest.raises(ValueError, match="parâmetros não permitidos") as error:
        module._connection_parts(
            "postgresql://reader:secret@db.example/library?sslpassword=another-secret"
        )
    assert "secret" not in str(error.value)


def test_file_envelope_stream_roundtrip_and_authenticated_tamper(tmp_path):
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    private, public = module.keypair()
    source = tmp_path / "source"
    encrypted = tmp_path / "backup.enc"
    decrypted = tmp_path / "decrypted"
    source.write_bytes(b"Julib data" * 400_000)

    module.encrypt_file(source, encrypted, public, max_bytes=5_000_000)
    module.decrypt_file(encrypted, decrypted, private)
    assert decrypted.read_bytes() == source.read_bytes()
    assert b"Julib data" not in encrypted.read_bytes()

    damaged = bytearray(encrypted.read_bytes())
    damaged[-20] ^= 1
    encrypted.write_bytes(damaged)
    decrypted.unlink()
    with pytest.raises(ValueError, match="Autenticação"):
        module.decrypt_file(encrypted, decrypted, private)
    assert not decrypted.exists()


def test_stream_encryption_limit_removes_partial_output(tmp_path):
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _, public = module.keypair()
    source = tmp_path / "large"
    encrypted = tmp_path / "too-large.enc"
    source.write_bytes(b"x" * 1024)

    with pytest.raises(RuntimeError, match="limite"):
        module.encrypt_file(source, encrypted, public, max_bytes=300)
    assert not encrypted.exists()
    assert not list(tmp_path.glob(".too-large.enc.*.tmp"))


def test_file_encryption_does_not_overwrite_existing_backup(tmp_path):
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _, public = module.keypair()
    source = tmp_path / "source"
    destination = tmp_path / "backup.enc"
    source.write_bytes(b"replacement")
    destination.write_bytes(b"existing backup")

    with pytest.raises(FileExistsError):
        module.encrypt_file(source, destination, public, max_bytes=1_000)
    assert destination.read_bytes() == b"existing backup"
    assert not list(tmp_path.glob(".backup.enc.*.tmp"))


def test_file_encryption_rejects_non_rsa_public_key(tmp_path):
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    key = ec.generate_private_key(ec.SECP256R1()).public_key()
    public = key.public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    source = tmp_path / "source"
    source.write_bytes(b"data")

    with pytest.raises(ValueError, match="RSA"):
        module.encrypt_file(source, tmp_path / "backup.enc", public, max_bytes=1_000)


def test_decryption_does_not_overwrite_existing_plaintext(tmp_path):
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    private, public = module.keypair()
    source = tmp_path / "source"
    encrypted = tmp_path / "backup.enc"
    destination = tmp_path / "restore.tar.gz"
    source.write_bytes(b"new plaintext")
    module.encrypt_file(source, encrypted, public, max_bytes=1_000)
    destination.write_bytes(b"existing plaintext")

    with pytest.raises(FileExistsError):
        module.decrypt_file(encrypted, destination, private)
    assert destination.read_bytes() == b"existing plaintext"
    assert not list(tmp_path.glob(".restore.tar.gz.*.tmp"))


def test_stream_encryption_interrupt_removes_temporary_file(monkeypatch, tmp_path):
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _, public = module.keypair()
    source = tmp_path / "source"
    destination = tmp_path / "backup.enc"
    source.write_bytes(b"data")

    class Encryptor:
        def authenticate_additional_data(self, _):
            pass

        def update(self, _):
            raise KeyboardInterrupt

    class FakeCipher:
        def __init__(self, *_):
            pass

        def encryptor(self):
            return Encryptor()

    monkeypatch.setattr(module, "Cipher", FakeCipher)
    with pytest.raises(KeyboardInterrupt):
        module.encrypt_file(source, destination, public, max_bytes=1_000)
    assert not destination.exists()
    assert not list(tmp_path.glob(".backup.enc.*.tmp"))


def make_encrypted_package(
    module,
    private,
    public,
    tmp_path,
    media=None,
    manifest_format=2,
    include_media=True,
    corrupt_manifest_hash=False,
    duplicate_manifest_item=False,
    extra_entries=(),
):
    media = media or {}
    manifest_media = []
    for public_id, (filename, content) in media.items():
        item = {"public_id": public_id, "file": filename}
        if manifest_format == 2:
            item.update(size_bytes=len(content), sha256=hashlib.sha256(content).hexdigest())
            if corrupt_manifest_hash:
                item["sha256"] = "0" * 64
        manifest_media.append(item)
    if duplicate_manifest_item and manifest_media:
        manifest_media.append(dict(manifest_media[0]))
    manifest = {
        "created_at": "2026-11-19T00:00:00+00:00",
        "format": manifest_format,
        "media": manifest_media,
    }
    archive_path = tmp_path / "package.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        database = tarfile.TarInfo("database.dump")
        database.size = 4
        archive.addfile(database, io.BytesIO(b"dump"))
        for _, (filename, content) in media.items() if include_media else ():
            item = tarfile.TarInfo(filename)
            item.size = len(content)
            archive.addfile(item, io.BytesIO(content))
        for name, content in extra_entries:
            item = tarfile.TarInfo(name)
            item.size = len(content)
            archive.addfile(item, io.BytesIO(content))
        raw_manifest = json.dumps(manifest).encode()
        item = tarfile.TarInfo("manifest.json")
        item.size = len(raw_manifest)
        archive.addfile(item, io.BytesIO(raw_manifest))
    encrypted = module.encrypt(archive_path.read_bytes(), public)
    input_path = tmp_path / "backup.enc"
    input_path.write_bytes(encrypted)
    return input_path


def test_verify_checks_manifest_media_hash_and_legacy_format(tmp_path):
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    private, public = module.keypair()
    source = make_encrypted_package(
        module,
        private,
        public,
        tmp_path,
        {"cover-1": ("media/0.jpg", b"image bytes")},
    )
    result = module.verify_backup(source, private)
    assert result["media_count"] == 1
    assert result["format"] == 2

    legacy = make_encrypted_package(
        module,
        private,
        public,
        tmp_path,
        {"cover-old": ("media/0.jpg", b"old image")},
        manifest_format=1,
    )
    assert module.verify_backup(legacy, private)["format"] == 1


def test_verify_rejects_corrupt_or_missing_media_and_bad_encrypted_hash(tmp_path):
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    private, public = module.keypair()
    source = make_encrypted_package(
        module,
        private,
        public,
        tmp_path,
        {"cover-1": ("media/0.jpg", b"image bytes")},
    )
    with pytest.raises(ValueError, match="SHA-256"):
        module.verify_backup(source, private, expected_sha256="0" * 64)

    source.write_bytes(
        source.read_bytes()[:-17]
        + bytes([source.read_bytes()[-17] ^ 1])
        + source.read_bytes()[-16:]
    )
    with pytest.raises(ValueError, match="Autenticação"):
        module.verify_backup(source, private)


@pytest.mark.parametrize(
    ("include_media", "corrupt_manifest_hash", "duplicate_manifest_item"),
    [(False, False, False), (True, True, False), (True, False, True)],
)
def test_verify_rejects_missing_corrupt_or_duplicate_media(
    tmp_path, include_media, corrupt_manifest_hash, duplicate_manifest_item
):
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    private, public = module.keypair()
    source = make_encrypted_package(
        module,
        private,
        public,
        tmp_path,
        {"cover-1": ("media/0.jpg", b"image bytes")},
        include_media=include_media,
        corrupt_manifest_hash=corrupt_manifest_hash,
        duplicate_manifest_item=duplicate_manifest_item,
    )
    with pytest.raises(ValueError):
        module.verify_backup(source, private)


def test_verify_rejects_tar_path_traversal(tmp_path):
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    private, public = module.keypair()
    source = make_encrypted_package(
        module,
        private,
        public,
        tmp_path,
        extra_entries=[("../outside.txt", b"bad")],
    )
    with pytest.raises(ValueError, match="entradas inválidas"):
        module.verify_backup(source, private)


def test_media_reference_change_aborts_package():
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with pytest.raises(RuntimeError, match="mudaram"):
        module.assert_media_references_unchanged(
            ("cover-1",), ("cover-1", "cover-2"), "durante o dump"
        )


def test_insufficient_disk_space_fails_before_work(monkeypatch, tmp_path):
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(
        module.os,
        "statvfs",
        lambda _: SimpleNamespace(f_bavail=1, f_frsize=1),
    )
    with pytest.raises(RuntimeError, match="Espaço temporário"):
        module.require_disk_space(tmp_path, 100)


def test_cloudinary_media_is_streamed_and_hashed(monkeypatch, tmp_path):
    import cloudinary.api
    import httpx

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(
        cloudinary.api,
        "resource",
        lambda public_id: {
            "secure_url": "https://res.cloudinary.com/test/image/upload/sample.jpg",
            "format": "jpg",
            "asset_id": "asset-id-1",
            "version": 7,
            "bytes": 5,
        },
    )

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def raise_for_status(self):
            return None

        def iter_bytes(self, _):
            yield from (b"im", b"age")

    class Client:
        def __init__(self, **_):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def stream(self, method, url):
            assert method == "GET" and url.startswith("https://")
            return Response()

    monkeypatch.setattr(httpx, "Client", Client)
    entries, fingerprints = module._download_media(("library/book-1",), tmp_path, 100)
    module._assert_cloudinary_unchanged(fingerprints)
    assert entries == [
        {
            "public_id": "library/book-1",
            "file": "media/0.jpg",
            "size_bytes": 5,
            "sha256": hashlib.sha256(b"image").hexdigest(),
        }
    ]
    assert (tmp_path / "media/0.jpg").read_bytes() == b"image"


def test_cloudinary_download_failure_is_sanitized(monkeypatch, tmp_path):
    import cloudinary.api
    import httpx

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(
        cloudinary.api,
        "resource",
        lambda _: {
            "secure_url": "https://res.cloudinary.com/test/image/upload/sample.jpg",
            "format": "jpg",
            "asset_id": "asset-id-1",
            "version": 7,
            "bytes": 5,
        },
    )

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def raise_for_status(self):
            raise RuntimeError("signed-url-secret")

    class Client:
        def __init__(self, **_):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def stream(self, *_):
            return Response()

    monkeypatch.setattr(httpx, "Client", Client)
    with pytest.raises(RuntimeError, match="Falha ao baixar") as error:
        module._download_media(("library/book-1",), tmp_path, 100)
    assert "signed-url-secret" not in str(error.value)
    assert not list(tmp_path.rglob("*jpg"))


def test_cloudinary_asset_version_change_aborts_backup(monkeypatch):
    import cloudinary.api

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    responses = iter(
        [
            {"asset_id": "asset-id-1", "version": 7, "bytes": 5, "format": "jpg"},
            {"asset_id": "asset-id-1", "version": 8, "bytes": 5, "format": "jpg"},
        ]
    )
    monkeypatch.setattr(cloudinary.api, "resource", lambda _: next(responses))
    expected = {"library/book-1": module._cloudinary_fingerprint(cloudinary.api.resource("x"))}
    with pytest.raises(RuntimeError, match="mudou"):
        module._assert_cloudinary_unchanged(expected)
