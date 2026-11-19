import hashlib
import importlib.util
import json
import os
import subprocess
import tarfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit

import psycopg
import pytest
from psycopg import sql

BACKUP_SCRIPT = Path(__file__).resolve().parents[2] / "scripts/backup.py"
spec = importlib.util.spec_from_file_location("backup_postgres17", BACKUP_SCRIPT)
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


def _pgpass_escape(value):
    return value.replace("\\", "\\\\").replace(":", "\\:").replace("\n", "\\n")


def _url_for_database(parsed, database_name):
    return urlunsplit((parsed.scheme, parsed.netloc, f"/{database_name}", parsed.query, ""))


def test_encrypted_package_restores_fictional_data_on_postgres17(tmp_path):
    base_url = os.environ.get("JULIB_BACKUP_TEST_DATABASE_URL")
    if not base_url:
        pytest.skip("JULIB_BACKUP_TEST_DATABASE_URL is not configured")

    parsed = urlsplit(base_url)
    if parsed.scheme not in {"postgres", "postgresql"} or parsed.hostname not in {
        "127.0.0.1",
        "localhost",
    }:
        pytest.fail("Disposable restore test requires a localhost PostgreSQL URL")

    host = parsed.hostname
    port = parsed.port or 5432
    username = unquote(parsed.username or "")
    password = unquote(parsed.password or "")
    database_prefix = f"julib_backup_fixture_{uuid.uuid4().hex[:12]}"
    source_db = f"{database_prefix}_source"
    target_db = f"{database_prefix}_target"
    created_databases = []

    with psycopg.connect(base_url, autocommit=True) as admin:
        version = int(admin.execute("SHOW server_version_num").fetchone()[0])
        assert 170000 <= version < 180000
        for database_name in (source_db, target_db):
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))
            created_databases.append(database_name)

    passfile = tmp_path / "pgpass"
    passfile.write_text(
        ":".join(_pgpass_escape(value) for value in (host, str(port), "*", username, password))
        + "\n",
        encoding="utf-8",
    )
    passfile.chmod(0o600)
    pg_env = {**os.environ, "PGPASSFILE": str(passfile), "PGSSLMODE": "disable"}
    pg_args = ["--host", host, "--port", str(port), "--username", username, "--no-password"]
    pg17_container = os.environ.get("JULIB_PG17_CONTAINER")
    if pg17_container:
        pg_args = ["-U", username]
        pg_env = os.environ.copy()

    try:
        source_url = _url_for_database(parsed, source_db)
        with psycopg.connect(source_url, autocommit=True) as source:
            source.execute(
                "CREATE TABLE public.fixture_books (id integer PRIMARY KEY, title text NOT NULL)"
            )
            source.execute(
                "INSERT INTO public.fixture_books VALUES "
                "(1, 'Fictional Book A'), (2, 'Fictional Book B')"
            )

        dump_path = tmp_path / "database.dump"
        dump_command = (
            ["docker", "exec", pg17_container, "pg_dump", *pg_args]
            if pg17_container
            else ["pg_dump", *pg_args]
        )
        dump = subprocess.run(
            [
                *dump_command,
                "--dbname",
                source_db,
                "--schema=public",
                "--format=custom",
                "--no-owner",
                "--no-acl",
            ],
            env=pg_env,
            capture_output=True,
            check=False,
        )
        assert dump.returncode == 0
        dump_path.write_bytes(dump.stdout)

        media_bytes = b"fictional cover bytes"
        media_path = tmp_path / "cover.jpg"
        media_path.write_bytes(media_bytes)
        manifest = {
            "created_at": datetime.now(UTC).isoformat(),
            "format": 2,
            "media": [
                {
                    "public_id": "julib/test/fictional-cover",
                    "file": "media/0.jpg",
                    "size_bytes": len(media_bytes),
                    "sha256": hashlib.sha256(media_bytes).hexdigest(),
                }
            ],
        }
        package_path = tmp_path / "package.tar.gz"
        with tarfile.open(package_path, "w:gz") as archive:
            archive.add(dump_path, arcname="database.dump", recursive=False)
            archive.add(media_path, arcname="media/0.jpg", recursive=False)
            backup.add_bytes(
                archive,
                "manifest.json",
                json.dumps(manifest, separators=(",", ":")).encode(),
            )

        private_key, public_key = backup.keypair()
        encrypted_path = tmp_path / "backup.enc"
        backup.encrypt_file(
            package_path,
            encrypted_path,
            public_key,
            max_bytes=backup.DEFAULT_MAX_BYTES,
        )
        verified = backup.verify_backup(
            encrypted_path,
            private_key,
            expected_sha256=hashlib.sha256(encrypted_path.read_bytes()).hexdigest(),
        )
        assert verified["media_count"] == 1
        assert verified["database_bytes"] == dump_path.stat().st_size

        restored_package = tmp_path / "restored.tar.gz"
        restored_package.write_bytes(backup.decrypt(encrypted_path.read_bytes(), private_key))
        restored_dump = tmp_path / "restored.dump"
        with tarfile.open(restored_package, "r:gz") as archive:
            member = archive.extractfile("database.dump")
            assert member is not None
            restored_dump.write_bytes(member.read())

        target_url = _url_for_database(parsed, target_db)
        with psycopg.connect(target_url, autocommit=True) as target:
            target.execute("DROP SCHEMA public CASCADE")
        restore = subprocess.run(
            [
                *(
                    ["docker", "exec", "-i", pg17_container, "pg_restore", *pg_args]
                    if pg17_container
                    else ["pg_restore", *pg_args]
                ),
                "--dbname",
                target_db,
                "--exit-on-error",
                "--no-owner",
                "--no-acl",
                *([] if pg17_container else [str(restored_dump)]),
            ],
            env=pg_env,
            input=restored_dump.read_bytes() if pg17_container else None,
            capture_output=True,
            check=False,
        )
        assert restore.returncode == 0
        with psycopg.connect(target_url) as target:
            rows = target.execute(
                "SELECT id, title FROM public.fixture_books ORDER BY id"
            ).fetchall()
        assert rows == [(1, "Fictional Book A"), (2, "Fictional Book B")]
    finally:
        with psycopg.connect(base_url, autocommit=True) as admin:
            for database_name in reversed(created_databases):
                admin.execute(
                    sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                        sql.Identifier(database_name)
                    )
                )
