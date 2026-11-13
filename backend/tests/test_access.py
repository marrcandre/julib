import pytest
from django.test import Client, override_settings

from library.models import Book, Library, Membership, User

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


def test_session_includes_google_avatar_with_empty_fallback(users):
    from allauth.socialaccount.models import SocialAccount

    client = Client()
    client.force_login(users[0])
    with override_settings(ALLOWED_EMAILS=["marco@example.com"]):
        assert client.get("/api/v1/session").json()["avatar_url"] == ""
        SocialAccount.objects.create(
            user=users[0],
            provider="google",
            uid="test-google-user",
            extra_data={"picture": "https://lh3.googleusercontent.com/test-avatar"},
        )
        assert client.get("/api/v1/session").json()["avatar_url"] == (
            "https://lh3.googleusercontent.com/test-avatar"
        )


def test_session_returns_only_accessible_libraries_and_creation_capability(client, member):
    own = Library.objects.create(name="Pessoal")
    Membership.objects.create(user=member, library=own, role="admin")
    other_user = User.objects.create_user(username="other", email="other@example.com")
    other = Library.objects.create(name="Alheia")
    Membership.objects.create(user=other_user, library=other, role="admin")

    response = client.get("/api/v1/session")

    assert response.status_code == 200
    assert response.json()["libraries"] == [{"id": own.pk, "name": "Pessoal", "role": "admin"}]
    assert response.json()["can_create_libraries"] is False


def test_api_requires_explicit_library_when_user_has_multiple_memberships(client, member):
    first = Library.objects.create(name="Pessoal")
    second = Library.objects.create(name="Família")
    Membership.objects.create(user=member, library=first)
    Membership.objects.create(user=member, library=second)
    Book.objects.create(library=first, title="Primeiro", authors=["Autora"])

    response = client.get("/api/v1/books")

    assert response.status_code == 403


def test_api_uses_library_header_and_rejects_a_library_without_membership(client, member):
    own = Library.objects.create(name="Pessoal")
    Membership.objects.create(user=member, library=own)
    Book.objects.create(library=own, title="Meu livro", authors=["Autora"])
    other = Library.objects.create(name="Alheia")
    Book.objects.create(library=other, title="Outro livro", authors=["Autor"])

    response = client.get("/api/v1/books", HTTP_X_LIBRARY_ID=str(own.pk))
    denied = client.get("/api/v1/books", HTTP_X_LIBRARY_ID=str(other.pk))

    assert response.status_code == 200
    assert [item["title"] for item in response.json()["items"]] == ["Meu livro"]
    assert denied.status_code == 403


def test_foreign_library_is_rejected_by_all_library_scoped_lists(client, member):
    own = Library.objects.create(name="Pessoal")
    Membership.objects.create(user=member, library=own)
    foreign = Library.objects.create(name="Alheia")
    paths = (
        "/api/v1/books",
        "/api/v1/locations",
        "/api/v1/tags",
        "/api/v1/people",
        "/api/v1/loans",
        "/api/v1/imports",
        "/api/v1/share/manage",
    )

    for path in paths:
        response = client.get(path, HTTP_X_LIBRARY_ID=str(foreign.pk))
        assert response.status_code == 403, path
