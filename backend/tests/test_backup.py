import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

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


def test_postgres_dump_runs_with_default_transaction_read_only(monkeypatch):
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    called = {}

    def fake_run(command, *, check, capture_output, env):
        called.update(command=command, check=check, capture_output=capture_output, env=env)
        return SimpleNamespace(stdout=b"dump")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setenv("PGOPTIONS", "-c statement_timeout=30000")

    assert module.dump_database("postgresql://read-only") == b"dump"
    assert called["check"] is True
    assert called["capture_output"] is True
    assert "-c statement_timeout=30000" in called["env"]["PGOPTIONS"]
    assert "-c default_transaction_read_only=on" in called["env"]["PGOPTIONS"]
