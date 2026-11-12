import pytest
from django.conf import settings

from library.models import Library, Membership, User

pytestmark = pytest.mark.django_db


def test_default_login_redirect_is_books():
    assert settings.LOGIN_REDIRECT_URL == "/livros"


def test_technical_account_updates_library_name_and_blank_fallback(client, member):
    library = Library.objects.create(name="Casa")
    Membership.objects.create(user=member, library=library)

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
    Membership.objects.create(user=member, library=library)
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
