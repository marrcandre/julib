import json

import pytest
from django.conf import settings
from django.core.management import call_command
from django.db import IntegrityError

from library.models import Library, Membership, User

pytestmark = pytest.mark.django_db


def test_default_login_redirect_is_books():
    assert settings.LOGIN_REDIRECT_URL == "/livros"


def test_technical_account_updates_library_name_and_blank_fallback(client, member):
    library = Library.objects.create(name="Casa")
    Membership.objects.create(user=member, library=library, role="admin")

    response = client.put(
        "/api/v1/library/name",
        data='{"name":"  Biblioteca da Família  "}',
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json() == {"name": "Biblioteca da Família"}
    library.refresh_from_db()
    assert library.name == "Biblioteca da Família"

    response = client.put(
        "/api/v1/library/name", data='{"name":"   "}', content_type="application/json"
    )
    assert response.status_code == 200
    assert response.json() == {"name": ""}
    library.refresh_from_db()
    assert library.name == ""


def test_nontechnical_member_cannot_update_library_name(client):
    user = User.objects.create_user(username="ju", email="ju@example.com")
    library = Library.objects.create(name="Casa")
    Membership.objects.create(user=user, library=library)
    client.force_login(user)

    response = client.put(
        "/api/v1/library/name", data='{"name":"Invadida"}', content_type="application/json"
    )
    assert response.status_code == 403
    library.refresh_from_db()
    assert library.name == "Casa"


def test_library_name_is_limited_to_150_characters(client, member):
    library = Library.objects.create(name="Casa")
    Membership.objects.create(user=member, library=library, role="admin")
    response = client.put(
        "/api/v1/library/name",
        data='{"name":"' + "x" * 151 + '"}',
        content_type="application/json",
    )
    assert response.status_code == 422
    library.refresh_from_db()
    assert library.name == "Casa"


def test_dashboard_endpoint_is_removed(client, member):
    Library.objects.create(name="Casa")
    response = client.get("/api/v1/dashboard")
    assert response.status_code == 404


def test_only_explicitly_authorized_user_can_create_library(client, member):
    denied = client.post(
        "/api/v1/libraries",
        data='{"name":"Nova biblioteca"}',
        content_type="application/json",
    )
    assert denied.status_code == 403
    assert Library.objects.count() == 0

    member.can_create_libraries = True
    member.save(update_fields=["can_create_libraries"])
    created = client.post(
        "/api/v1/libraries",
        data='{"name":"  Biblioteca da Família  "}',
        content_type="application/json",
    )

    assert created.status_code == 200
    data = created.json()
    assert data["name"] == "Biblioteca da Família"
    assert data["role"] == "admin"
    assert Membership.objects.filter(user=member, library_id=data["id"], role="admin").exists()


def test_bootstrap_grants_create_capability_only_to_configured_admin(member):
    other = User.objects.create_user(username="ju", email="ju@example.com", is_staff=True)

    call_command("bootstrap_library")

    member.refresh_from_db()
    other.refresh_from_db()
    assert member.email == settings.ADMIN_EMAIL
    assert member.can_create_libraries is True
    assert other.can_create_libraries is False
    assert Membership.objects.get(user=member).role == "admin"
    assert Membership.objects.get(user=other).role == "member"


def test_library_creation_rejects_blank_and_overlong_names(client, member):
    member.can_create_libraries = True
    member.save(update_fields=["can_create_libraries"])
    for name in ("   ", "x" * 151):
        response = client.post(
            "/api/v1/libraries",
            data=json.dumps({"name": name}),
            content_type="application/json",
        )
        assert response.status_code in {400, 422}
    assert Library.objects.count() == 0


def test_library_creation_rolls_back_when_membership_creation_fails(client, member, monkeypatch):
    member.can_create_libraries = True
    member.save(update_fields=["can_create_libraries"])

    def fail_membership(*args, **kwargs):
        raise IntegrityError("membership write failed")

    monkeypatch.setattr(Membership.objects, "create", fail_membership)
    response = client.post(
        "/api/v1/libraries",
        data=json.dumps({"name": "Sem órfã"}),
        content_type="application/json",
    )

    assert response.status_code == 409
    assert Library.objects.count() == 0


def test_library_names_can_repeat_and_listing_is_membership_scoped(client, member):
    member.can_create_libraries = True
    member.save(update_fields=["can_create_libraries"])
    first = client.post(
        "/api/v1/libraries",
        data=json.dumps({"name": "Igreja"}),
        content_type="application/json",
    )
    second = client.post(
        "/api/v1/libraries",
        data=json.dumps({"name": "Igreja"}),
        content_type="application/json",
    )
    other_user = User.objects.create_user(username="other", email="other@example.com")
    hidden = Library.objects.create(name="Privada")
    Membership.objects.create(user=other_user, library=hidden)

    listed = client.get("/api/v1/libraries")

    assert first.status_code == second.status_code == 200
    assert first.json()["id"] != second.json()["id"]
    assert [item["name"] for item in listed.json()] == ["Igreja", "Igreja"]
