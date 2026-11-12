import importlib.util
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

RELEASE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "release.py"
SPEC = importlib.util.spec_from_file_location("julib_release", RELEASE_PATH)
release = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(release)


@pytest.mark.parametrize(
    ("current", "increment", "expected"),
    [
        ("0.1.0", "patch", "0.1.1"),
        ("0.1.0", "minor", "0.2.0"),
        ("0.1.0", "major", "1.0.0"),
        ("1.4.9", "minor", "1.5.0"),
    ],
)
def test_explicit_semver_bump(current, increment, expected):
    assert release.bump_version(current, increment) == expected


def test_semver_rejects_invalid_value():
    with pytest.raises(ValueError):
        release.bump_version("1.2", "patch")


def test_synchronized_version_metadata(tmp_path):
    root = tmp_path
    (root / "frontend").mkdir()
    (root / "backend").mkdir()
    (root / "scripts").mkdir()
    (root / "frontend/package.json").write_text('{"name":"julib-frontend","version":"0.1.0"}\n')
    (root / "frontend/package-lock.json").write_text(
        '{"name":"julib-frontend","version":"0.1.0","packages":{"":{"name":"julib-frontend","version":"0.1.0"}}}\n'
    )
    (root / "backend/pyproject.toml").write_text(
        '[project]\nname="julib-backend"\nversion = "0.1.0"\n'
    )
    (root / "backend/uv.lock").write_text(
        '[[package]]\nname = "julib-backend"\nversion = "0.1.0"\n'
    )

    release.synchronize_versions(root, "0.2.0")

    assert release.read_versions(root) == {
        "frontend/package.json": "0.2.0",
        "frontend/package-lock.json": "0.2.0",
        "frontend/package-lock.json root package": "0.2.0",
        "backend/pyproject.toml": "0.2.0",
        "backend/uv.lock": "0.2.0",
    }


def test_retry_keeps_an_existing_unpublished_candidate(tmp_path):
    root = tmp_path
    (root / "frontend").mkdir()
    (root / "backend").mkdir()
    (root / "frontend/package.json").write_text('{"name":"julib-frontend","version":"0.1.0"}\n')
    (root / "frontend/package-lock.json").write_text(
        '{"name":"julib-frontend","version":"0.1.0","packages":{"":{"name":"julib-frontend","version":"0.1.0"}}}\n'
    )
    (root / "backend/pyproject.toml").write_text(
        '[project]\nname="julib-backend"\nversion = "0.1.0"\n'
    )
    (root / "backend/uv.lock").write_text(
        '[[package]]\nname = "julib-backend"\nversion = "0.1.0"\n'
    )
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)

    assert release.prepare("minor", root) == "0.2.0"
    assert release.prepare("minor", root) == "0.2.0"
    assert release.prepare("patch", root) == "0.2.0"
    assert release.validate_versions(root) == "0.2.0"


def test_finalize_retries_github_release_after_tag_exists(tmp_path, monkeypatch):
    root = tmp_path
    (root / "frontend").mkdir()
    (root / "backend").mkdir()
    (root / "frontend/package.json").write_text('{"name":"julib-frontend","version":"0.1.0"}\n')
    (root / "frontend/package-lock.json").write_text(
        '{"name":"julib-frontend","version":"0.1.0","packages":{"":{"name":"julib-frontend","version":"0.1.0"}}}\n'
    )
    (root / "backend/pyproject.toml").write_text(
        '[project]\nname="julib-backend"\nversion = "0.1.0"\n'
    )
    (root / "backend/uv.lock").write_text(
        '[[package]]\nname = "julib-backend"\nversion = "0.1.0"\n'
    )
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Julib Test"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "julib@example.com"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "baseline"], cwd=root, check=True)
    baseline_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()
    subprocess.run(["git", "tag", "-a", "v0.1.0", "-m", "baseline"], cwd=root, check=True)
    release.synchronize_versions(root, "0.2.0")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "candidate"], cwd=root, check=True)
    subprocess.run(["git", "tag", "-a", "v0.2.0", "-m", "Julib v0.2.0"], cwd=root, check=True)
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()
    commands = []
    release_creation_attempts = 0
    real_run = subprocess.run

    def fake_run(command, **kwargs):
        nonlocal release_creation_attempts
        if command[0] == "gh":
            commands.append(command)
            if command[2] == "view":
                return subprocess.CompletedProcess(
                    command, 0 if command[3] == "v0.1.0" else 1, "", "not found"
                )
            release_creation_attempts += 1
            if release_creation_attempts == 1:
                if kwargs.get("check"):
                    raise subprocess.CalledProcessError(1, command, stderr="temporary failure")
                return subprocess.CompletedProcess(command, 1, "", "temporary failure")
            return subprocess.CompletedProcess(command, 0, "", "")
        return real_run(command, **kwargs)

    monkeypatch.setattr(release, "BASELINE_SHA", baseline_sha)
    monkeypatch.setattr(release, "subprocess", SimpleNamespace(run=fake_run))
    with pytest.raises(subprocess.CalledProcessError):
        release.finalize(sha, root)
    assert release.finalize(sha, root) == "v0.2.0"
    assert commands == [
        ["gh", "release", "view", "v0.1.0", "--json", "tagName"],
        ["gh", "release", "view", "v0.2.0", "--json", "tagName"],
        ["gh", "release", "create", "v0.2.0", "--target", sha, "--generate-notes"],
        ["gh", "release", "view", "v0.1.0", "--json", "tagName"],
        ["gh", "release", "view", "v0.2.0", "--json", "tagName"],
        ["gh", "release", "create", "v0.2.0", "--target", sha, "--generate-notes"],
    ]
