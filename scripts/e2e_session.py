"""Cria sessão descartável somente no banco local/CI, sem rota de login alternativa."""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django

django.setup()
from django.conf import settings
from django.test import Client
from library.models import Library, Membership, User

if settings.DATABASES["default"]["HOST"] not in (
    "localhost",
    "127.0.0.1",
) or not settings.DATABASES["default"]["NAME"].endswith(("_ci", "_e2e")):
    raise SystemExit("Use um banco loopback com sufixo _ci ou _e2e.")
if (
    not settings.DEBUG
    or settings.ADMIN_EMAIL != "marco@example.com"
    or settings.ALLOWED_EMAILS != ["marco@example.com", "ju@example.com"]
):
    raise SystemExit("Este script exige DEBUG e allowlist descartável de testes.")
lib = Library.objects.first() or Library.objects.create(name="Biblioteca de testes")
user, _ = User.objects.get_or_create(
    username="e2e",
    defaults={
        "email": "marco@example.com",
        "is_staff": True,
        "is_superuser": True,
        "can_create_libraries": True,
    },
)
user.is_staff = True
user.is_superuser = True
user.can_create_libraries = True
user.save(update_fields=["is_staff", "is_superuser", "can_create_libraries"])
membership, _ = Membership.objects.get_or_create(
    user=user, library=lib, defaults={"role": Membership.ROLE_ADMIN}
)
if membership.role != Membership.ROLE_ADMIN:
    membership.role = Membership.ROLE_ADMIN
    membership.save(update_fields=["role"])
client = Client()
client.force_login(user)
path = Path(
    os.environ.get(
        "E2E_SESSION_PATH",
        str(Path(__file__).resolve().parents[1] / ".superpowers/e2e-session.json"),
    )
)
path.parent.mkdir(exist_ok=True)
path.write_text(
    json.dumps(
        {
            "name": "sessionid",
            "value": client.cookies["sessionid"].value,
            "domain": "127.0.0.1",
            "path": "/",
            "httpOnly": True,
            "secure": False,
            "sameSite": "Lax",
        }
    )
)
