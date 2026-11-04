import pytest
from django.test import Client, override_settings

from library.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def users():
    return [
        User.objects.create_user(username=n, email=f"{n}@example.com", is_staff=n == "marco")
        for n in ("marco", "ju", "other")
    ]


@override_settings(
    ALLOWED_EMAILS=["marco@example.com", "ju@example.com"], ADMIN_EMAIL="marco@example.com"
)
def test_session_allowlist_and_private_tools(users):
    client = Client()
    assert client.get("/api/v1/health").json() == {"status": "ok"}
    assert client.get("/api/v1/session").status_code == 401
    for user, expected in zip(users, (200, 200, 403)):
        client.force_login(user)
        assert client.get("/api/v1/session").status_code == expected
        tools = 200 if user.username == "marco" else 403
        assert client.get("/api/v1/docs").status_code == tools
        assert client.get("/api/v1/openapi.json").status_code == tools
        assert client.get("/admin/").status_code == tools


@override_settings(ALLOWED_EMAILS=["ju@example.com"], ADMIN_EMAIL="marco@example.com")
def test_session_mutations_require_csrf(users):
    client = Client(enforce_csrf_checks=True)
    client.force_login(users[1])
    assert client.post("/api/v1/logout").status_code == 403


def test_login_exposes_only_google_and_disables_local_email_flows(mailoutbox):
    client = Client()
    response = client.get("/accounts/login/")
    assert response.status_code == 200
    html = response.content.decode()
    assert "/accounts/google/login/" in html
    assert 'name="login"' not in html
    assert 'name="password"' not in html
    assert client.post("/accounts/login/", {"login": "marco@example.com"}).status_code == 403
    assert client.get("/accounts/signup/").status_code == 404
    assert client.get("/accounts/password/reset/").status_code == 404
    assert len(mailoutbox) == 0
