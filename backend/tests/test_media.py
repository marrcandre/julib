import pytest
from django.core.exceptions import ValidationError

from library.media import signature, verify_upload
from library.models import Library

pytestmark = pytest.mark.django_db


@pytest.fixture
def cloud(monkeypatch):
    for name, value in [
        ("CLOUDINARY_CLOUD_NAME", "test-cloud"),
        ("CLOUDINARY_API_KEY", "test-key"),
        ("CLOUDINARY_API_SECRET", "test-secret"),
    ]:
        monkeypatch.setenv(name, value)


def test_signed_upload_does_not_expose_secret(cloud):
    lib = Library.objects.create(name="Casa")
    data = signature(lib)
    assert data["folder"] == f"julib/{lib.pk}"
    assert "test-secret" not in str(data)
    assert len(data["signature"]) == 40


def test_attach_cover_checks_ownership_size_and_format(cloud, monkeypatch):
    import cloudinary.api

    lib = Library.objects.create(name="Casa")
    with pytest.raises(ValidationError):
        verify_upload(lib, "another-library/id")
    monkeypatch.setattr(
        cloudinary.api,
        "resource",
        lambda _: {
            "format": "jpg",
            "bytes": 6 * 1024 * 1024,
            "secure_url": "https://res.cloudinary.com/test.jpg",
        },
    )
    with pytest.raises(ValidationError):
        verify_upload(lib, f"julib/{lib.pk}/id")
    monkeypatch.setattr(
        cloudinary.api,
        "resource",
        lambda _: {
            "format": "jpg",
            "bytes": 1024,
            "secure_url": "https://res.cloudinary.com/test.jpg",
        },
    )
    assert verify_upload(lib, f"julib/{lib.pk}/id")["cover_url"].startswith("https:")
