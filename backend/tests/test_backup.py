import importlib.util
from pathlib import Path

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
