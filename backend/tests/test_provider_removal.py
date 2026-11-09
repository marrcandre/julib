import json

import httpx
import pytest

from library.cover_lookup import lookup_cover
from library.models import Book
from library.presentation import cover_attribution, metadata_attribution
from library.providers import search_books


def test_separate_legacy_cover_lookup_keeps_safe_sources(monkeypatch):
    monkeypatch.setenv("GOOGLE_BOOKS_API_KEY", "test-key")
    calls = []

    def handler(request):
        calls.append(str(request.url))
        assert "google" not in request.url.host
        if request.url.path == "/api/books":
            return httpx.Response(
                200,
                json={
                    "ISBN:9780261102217": {
                        "cover": {"large": "https://covers.openlibrary.org/b/id/1-L.jpg"}
                    }
                },
            )
        return httpx.Response(200, content=b"image", headers={"content-type": "image/jpeg"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert lookup_cover(client, "9780261102217", "Livro", ["Autor"]).startswith(
            "https://covers.openlibrary.org/"
        )
    assert calls


def test_optional_metadata_origin_does_not_label_a_user_cover():
    for source in ["openlibrary", "brasilapi", "goodreads"]:
        book = Book(
            title="Livro",
            source=source,
            source_id="/works/OL1W",
            cover_id="julib/1/own",
            cover_url="https://res.cloudinary.com/test/own.jpg",
        )
        assert cover_attribution(book) == {"attribution_name": "", "attribution_url": ""}
    # Restoring an old backup must not silently suppress mandatory legacy credits.
    google = Book(title="Legado", source="google", source_id="legacy")
    assert cover_attribution(google)["attribution_name"] == ""
    assert metadata_attribution(google)["metadata_attribution_name"] == "Google Books"


def test_google_is_first_metadata_but_legacy_cover_fallback_is_preserved(monkeypatch):
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        if "openlibrary" in url:
            return httpx.Response(200, json={"docs": []}, request=httpx.Request("GET", url))
        if "brasilapi" in url:
            assert kwargs["params"]["providers"] in {"cbl", "mercado-editorial"}
            return httpx.Response(404, json={}, request=httpx.Request("GET", url))
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "fallback",
                        "volumeInfo": {
                            "title": "Livro",
                            "authors": ["Autor"],
                            "industryIdentifiers": [
                                {"type": "ISBN_13", "identifier": "9780261102217"}
                            ],
                        },
                    }
                ]
            },
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr("library.providers.bounded_get", get)
    assert search_books("9780261102217")[0]["source"] == "google"
    assert "googleapis" in calls[0]
    hosts = []

    def handler(request):
        hosts.append(request.url.host)
        if request.url.host == "openlibrary.org":
            return httpx.Response(200, json={})
        if request.url.host == "www.googleapis.com":
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "cover",
                            "volumeInfo": {
                                "industryIdentifiers": [{"identifier": "9780261102217"}],
                                "imageLinks": {
                                    "thumbnail": "https://books.google.com/books/content?id=cover"
                                },
                            },
                        }
                    ]
                },
            )
        return httpx.Response(200, content=b"image", headers={"content-type": "image/jpeg"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert (
            lookup_cover(client, "9780261102217", "Livro", ["Autor"])
            == "https://books.google.com/books/content?id=cover"
        )
    assert hosts == ["openlibrary.org", "www.googleapis.com", "books.google.com"]


def test_google_metadata_remains_distinct_from_uploaded_cover():
    book = Book(
        source="google",
        source_id="metadata",
        cover_id="julib/1/user",
        cover_url="https://res.cloudinary.com/user.jpg",
    )
    assert cover_attribution(book)["attribution_name"] == ""
    assert metadata_attribution(book)["metadata_attribution_name"] == "Google Books"


@pytest.mark.parametrize("payload", [None, [], {"docs": None}, {"docs": [None]}])
def test_malformed_openlibrary_response_does_not_block_fallback(monkeypatch, payload):
    def get(url, **kwargs):
        if "googleapis" in url:
            return httpx.Response(503, request=httpx.Request("GET", url))
        if "openlibrary" in url:
            return httpx.Response(
                200,
                content=json.dumps(payload).encode(),
                headers={"content-type": "application/json"},
                request=httpx.Request("GET", url),
            )
        assert "brasilapi" in url
        return httpx.Response(
            200,
            json={"isbn": "9780261102217", "title": "Fallback", "authors": ["Autor"]},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr("library.providers.bounded_get", get)
    assert search_books("9780261102217")[0]["source"] == "brasilapi"
