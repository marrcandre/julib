import pytest
from django.test import Client, override_settings

from library.models import User

pytestmark = pytest.mark.django_db


@override_settings(ALLOWED_EMAILS=["one@example.com", "two@example.com"])
def test_catalog_preferences_are_validated_and_private_to_each_account():
    one = User.objects.create_user(username="one", email="one@example.com")
    two = User.objects.create_user(username="two", email="two@example.com")
    client = Client()
    client.force_login(one)
    initial = client.get("/api/v1/session").json()
    assert (initial["catalog_view"], initial["cover_columns"]) == ("covers", 7)
    response = client.put(
        "/api/v1/preferences/catalog",
        {"catalog_view": "list", "cover_columns": 9},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert client.get("/api/v1/session").json()["cover_columns"] == 9
    assert (
        client.put(
            "/api/v1/preferences/catalog",
            {"catalog_view": "covers", "cover_columns": 100},
            content_type="application/json",
        ).status_code
        == 422
    )
    client.force_login(two)
    other = client.get("/api/v1/session").json()
    assert (other["catalog_view"], other["cover_columns"]) == ("covers", 7)
    assert (
        Client().put("/api/v1/preferences/catalog", {}, content_type="application/json").status_code
        == 401
    )


@override_settings(ALLOWED_EMAILS=["one@example.com"])
def test_catalog_preferences_require_csrf_for_authenticated_user():
    user = User.objects.create_user(username="one", email="one@example.com")
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    assert (
        client.put(
            "/api/v1/preferences/catalog",
            {"catalog_view": "cards", "cover_columns": 5},
            content_type="application/json",
        ).status_code
        == 403
    )


def test_database_defaults_keep_older_user_inserts_compatible():
    from django.db import connection

    # Simulate the previous app version, which doesn't include the new columns.
    with connection.cursor() as cursor:
        cursor.execute("""
            INSERT INTO library_user
                (username, password, first_name, last_name, email,
                 is_superuser, is_staff, is_active, date_joined)
            VALUES ('older-app', '!', '', '', 'old@example.com', false, false, true, NOW())
        """)
    user = User.objects.get(username="older-app")
    assert (user.catalog_view, user.cover_columns) == ("covers", 7)
