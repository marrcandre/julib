import json
import os
import subprocess
import sys
from pathlib import Path


def test_database_connection_preserves_tls_options():
    env = {
        **os.environ,
        "DATABASE_URL": "postgresql://test:test@db.example.supabase.co:5432/postgres?sslmode=require",
    }
    output = subprocess.check_output(
        [
            sys.executable,
            "-c",
            "import json;from config.settings import DATABASES;print(json.dumps(DATABASES['default']['OPTIONS']))",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        text=True,
    )
    options = json.loads(output)
    assert options["sslmode"] == "require"
    assert options["prepare_threshold"] is None
