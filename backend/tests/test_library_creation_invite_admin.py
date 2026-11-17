import re
from datetime import timedelta
from urllib.parse import urlsplit

import pytest
from django.contrib import admin
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import Client
from django.utils import timezone

from library.models import LibraryCreationInvite, User

pytestmark = pytest.mark.django_db


def test_technical_owner_can_issue_link_once_from_django_admin(client, member):
    member.is_superuser = True
    member.save(update_fields=["is_superuser"])

    response = client.post(
        "/admin/library/librarycreationinvite/add/",
        {"email": "admin-link@example.com", "_save": "Salvar"},
        follow=True,
    )

    assert response.status_code == 200
    invite = LibraryCreationInvite.objects.get()
    assert invite.email == "admin-link@example.com"
    body = response.content.decode()
    links = re.findall(r"https?://[^\s<>]+/convites/criar#[\w-]+", body)
    assert len(links) == 1
    assert urlsplit(links[0]).fragment != invite.token_hash
    assert "token_hash" not in body


def test_django_admin_lists_and_revokes_creation_invites(member, rf):
    member.is_superuser = True
    member.save(update_fields=["is_superuser"])
    invite = LibraryCreationInvite.objects.create(
        token_hash="e" * 64,
        created_by=member,
        email="revoke@example.com",
        created_at=timezone.now(),
        expires_at=timezone.now() + timedelta(days=7),
    )
    model_admin = admin.site._registry[LibraryCreationInvite]
    request = rf.post("/admin/library/librarycreationinvite/")
    request.user = member
    request.session = {}
    request._messages = FallbackStorage(request)

    model_admin.revoke_selected(request, LibraryCreationInvite.objects.filter(pk=invite.pk))

    invite.refresh_from_db()
    assert invite.revoked_at is not None


def test_django_admin_detail_hides_creation_invite_token_hash(client, member):
    member.is_superuser = True
    member.save(update_fields=["is_superuser"])
    invite = LibraryCreationInvite.objects.create(
        token_hash="f" * 64,
        created_by=member,
        created_at=timezone.now(),
        expires_at=timezone.now() + timedelta(days=7),
    )

    response = client.get(f"/admin/library/librarycreationinvite/{invite.pk}/change/")

    assert response.status_code == 200
    body = response.content.decode()
    assert invite.token_hash not in body
    assert "token_hash" not in body


def test_non_owner_cannot_manage_creation_invites_in_django_admin():
    non_owner = User.objects.create_user(
        username="staff-not-owner", email="ju@example.com", is_staff=True, is_superuser=True
    )
    client = Client()
    client.force_login(non_owner)

    response = client.get("/admin/library/librarycreationinvite/add/")

    assert response.status_code == 403
