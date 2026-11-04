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


def test_signed_upload_accepts_cloudinary_url(monkeypatch):
    for name in ("CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("CLOUDINARY_URL", "cloudinary://url-key:url-secret@url-cloud")
    lib = Library.objects.create(name="Casa")
    data = signature(lib)
    assert data["cloud_name"] == "url-cloud"
    assert data["api_key"] == "url-key"
    assert "url-secret" not in str(data)
    assert len(data["signature"]) == 40
