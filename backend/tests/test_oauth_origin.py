import re
from urllib.parse import parse_qs, urlsplit

import pytest
from django.test import Client, override_settings

pytestmark = pytest.mark.django_db


@override_settings(
    APP_ORIGIN="https://app.example.com",
    ALLOWED_HOSTS=["api.example.com", "app.example.com"],
    CSRF_TRUSTED_ORIGINS=["https://app.example.com"],
)
def test_proxy_oauth_uses_configured_public_origin_and_rejects_bad_hosts():
    client = Client(enforce_csrf_checks=True)
    page = client.get("/accounts/google/login/", HTTP_HOST="api.example.com", secure=True)
    assert page.status_code == 200
    token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page.content.decode())[1]
    response = client.post(
        "/accounts/google/login/",
        {"csrfmiddlewaretoken": token},
        HTTP_HOST="api.example.com",
        HTTP_ORIGIN="https://app.example.com",
        secure=True,
    )
    assert response.status_code == 302
    query = parse_qs(urlsplit(response["Location"]).query)
    assert query["redirect_uri"] == ["https://app.example.com/accounts/google/login/callback/"]
    assert (
        client.get("/accounts/google/login/", HTTP_HOST="attacker.example.com").status_code == 400
    )
