#!/usr/bin/env python3
"""Prepare and finalize Julib's shared SemVer release."""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "0.1.0"
BASELINE_SHA = "679e7061f1167678f2deaa7e1f59fd909afbcf88"
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def version_tuple(value: str) -> tuple[int, int, int]:
    match = SEMVER.fullmatch(value)
    if not match:
        raise ValueError(f"Versão SemVer inválida: {value}")
    return tuple(map(int, match.groups()))


def bump_version(current: str, increment: str) -> str:
    major, minor, patch = version_tuple(current)
    if increment == "major":
        return f"{major + 1}.0.0"
    if increment == "minor":
        return f"{major}.{minor + 1}.0"
    if increment == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError(f"Incremento inválido: {increment}")


def read_versions(root: Path = ROOT) -> dict[str, str]:
    frontend = json.loads((root / "frontend/package.json").read_text())
    lock = json.loads((root / "frontend/package-lock.json").read_text())
    pyproject = (root / "backend/pyproject.toml").read_text()
    uv_lock = (root / "backend/uv.lock").read_text()
    project_version = re.search(r'(?m)^version\s*=\s*"([^"]+)"', pyproject)
    backend_lock = re.search(
        r'(?ms)^\[\[package\]\]\s*\nname = "julib-backend"\s*\nversion = "([^"]+)"',
        uv_lock,
    )
    if not project_version or not backend_lock:
        raise ValueError("Não foi possível ler a versão do backend e do uv.lock.")
    return {
        "frontend/package.json": frontend["version"],
        "frontend/package-lock.json": lock["version"],
        "frontend/package-lock.json root package": lock["packages"][""]["version"],
        "backend/pyproject.toml": project_version.group(1),
        "backend/uv.lock": backend_lock.group(1),
    }


def synchronize_versions(root: Path, version: str) -> None:
    version_tuple(version)
    package_path = root / "frontend/package.json"
    package = json.loads(package_path.read_text())
    package["version"] = version
    package_path.write_text(json.dumps(package, indent=2) + "\n")

    lock_path = root / "frontend/package-lock.json"
    lock = json.loads(lock_path.read_text())
    lock["version"] = version
    lock["packages"][""]["version"] = version
    lock_path.write_text(json.dumps(lock, indent=2) + "\n")

    project_path = root / "backend/pyproject.toml"
    project = project_path.read_text()
    project, count = re.subn(
        r'(?m)^(version\s*=\s*)"[^"]+"', rf'\g<1>"{version}"', project, count=1
    )
    if count != 1:
        raise ValueError("Não foi possível sincronizar a versão do pyproject.toml.")
    project_path.write_text(project)

    lock_path = root / "backend/uv.lock"
    lock = lock_path.read_text()
    lock, count = re.subn(
        r'(?ms)(^\[\[package\]\]\s*\nname = "julib-backend"\s*\nversion = )"[^"]+"',
        rf'\g<1>"{version}"',
        lock,
        count=1,
    )
    if count != 1:
        raise ValueError("Não foi possível sincronizar a versão do uv.lock.")
    lock_path.write_text(lock)


def published_versions(root: Path = ROOT) -> list[str]:
    result = subprocess.run(
        ["git", "tag", "--list", "v[0-9]*"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    versions = []
    for tag in result.stdout.splitlines():
        value = tag.removeprefix("v")
        try:
            version_tuple(value)
        except ValueError:
            continue
        versions.append(value)
    return versions


def latest_published(root: Path = ROOT) -> str:
    versions = published_versions(root)
    return max(versions, key=version_tuple) if versions else BASELINE


def validate_versions(root: Path = ROOT) -> str:
    versions = read_versions(root)
    distinct = set(versions.values())
    if len(distinct) != 1:
        raise ValueError(
            "Versões divergentes: " + ", ".join(f"{key}={value}" for key, value in versions.items())
        )
    version = distinct.pop()
    if version_tuple(version) <= version_tuple(latest_published(root)):
        raise ValueError(f"v{version} não é um candidato pendente de publicação.")
    return version


def prepare(increment: str, root: Path = ROOT) -> str:
    versions = read_versions(root)
    distinct = set(versions.values())
    if len(distinct) != 1:
        raise ValueError("Versões divergentes: sincronize os metadados antes do release.")
    current = distinct.pop()
    latest = latest_published(root)
    if version_tuple(current) > version_tuple(latest):
        return current
    if version_tuple(current) < version_tuple(latest):
        raise ValueError(f"A versão do código ({current}) está atrás da última release ({latest}).")
    candidate = bump_version(current, increment)
    if f"v{candidate}" in {f"v{item}" for item in published_versions(root)}:
        raise ValueError(f"A tag v{candidate} já foi publicada.")
    synchronize_versions(root, candidate)
    return candidate


def run(command: list[str], root: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=root, check=True, text=True, capture_output=True)


def ensure_baseline_release(root: Path = ROOT) -> None:
    tag = f"v{BASELINE}"
    baseline = run(["git", "rev-parse", f"{BASELINE_SHA}^{{commit}}"], root).stdout.strip()
    tags = {item.strip() for item in run(["git", "tag", "--list", tag], root).stdout.splitlines()}
    if tag in tags:
        tagged = run(["git", "rev-parse", f"{tag}^{{}}"], root).stdout.strip()
        if tagged != baseline:
            raise ValueError(f"A tag {tag} precisa apontar para o baseline {BASELINE_SHA}.")
    else:
        run(["git", "tag", "-a", tag, baseline, "-m", f"Julib {tag} baseline"], root)
        run(["git", "push", "origin", tag], root)

    release = subprocess.run(
        ["gh", "release", "view", tag, "--json", "tagName"],
        cwd=root,
        text=True,
        capture_output=True,
    )
    if release.returncode:
        run(["gh", "release", "create", tag, "--target", baseline, "--generate-notes"], root)


def finalize(sha: str, root: Path = ROOT) -> str:
    versions = set(read_versions(root).values())
    if len(versions) != 1:
        raise ValueError("Versões divergentes; a finalização foi interrompida.")
    version = versions.pop()
    version_tuple(version)
    target = run(["git", "rev-parse", "HEAD"], root).stdout.strip()
    requested = run(["git", "rev-parse", sha], root).stdout.strip()
    if target != requested:
        raise ValueError("O SHA de finalização deve ser o commit implantado neste checkout.")
    if version_tuple(version) > version_tuple(BASELINE):
        baseline = run(["git", "rev-parse", f"{BASELINE_SHA}^{{commit}}"], root).stdout.strip()
        run(["git", "merge-base", "--is-ancestor", baseline, requested], root)
        ensure_baseline_release(root)
    tag = f"v{version}"
    tags = {item.strip() for item in run(["git", "tag", "--list", tag], root).stdout.splitlines()}
    latest = latest_published(root)
    if tag in tags:
        tagged_sha = run(["git", "rev-parse", f"{tag}^{{}}"], root).stdout.strip()
        if tagged_sha != requested:
            raise ValueError(f"A tag {tag} já aponta para outro commit.")
        if version_tuple(version) < version_tuple(latest):
            raise ValueError(
                f"A versão do código ({version}) está atrás da última release ({latest})."
            )
    else:
        if version_tuple(version) <= version_tuple(latest):
            raise ValueError(f"v{version} não é um candidato pendente de publicação.")
        run(["git", "tag", "-a", tag, requested, "-m", f"Julib {tag}"], root)
        run(["git", "push", "origin", tag], root)

    release = subprocess.run(
        ["gh", "release", "view", tag, "--json", "tagName"],
        cwd=root,
        text=True,
        capture_output=True,
    )
    if release.returncode:
        run(["gh", "release", "create", tag, "--target", requested, "--generate-notes"], root)
    return tag


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare", help="prepara/incrementa candidato SemVer")
    prepare_parser.add_argument("increment", choices=["patch", "minor", "major"])
    subparsers.add_parser("validate", help="valida candidato não publicado e metadados")
    finalize_parser = subparsers.add_parser(
        "finalize", help="cria tag e GitHub Release para o SHA implantado"
    )
    finalize_parser.add_argument("--sha", required=True)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            print(f"Candidato v{prepare(args.increment)} pronto.")
        elif args.command == "validate":
            print(f"Candidato v{validate_versions()} válido.")
        else:
            print(f"Release {finalize(args.sha)} finalizada.")
    except (ValueError, subprocess.CalledProcessError) as error:
        detail = getattr(error, "stderr", None) or str(error)
        print(detail.strip(), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
