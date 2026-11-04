import pytest
from django.test import override_settings

from library.models import User


@pytest.fixture(autouse=True)
def allowed_accounts():
    with override_settings(
        ALLOWED_EMAILS=["marco@example.com", "ju@example.com"], ADMIN_EMAIL="marco@example.com"
    ):
        yield


@pytest.fixture
def member(client):
    user = User.objects.create_user(username="marco", email="marco@example.com", is_staff=True)
    client.force_login(user)
    return user
