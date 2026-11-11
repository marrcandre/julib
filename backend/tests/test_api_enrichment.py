import httpx
import pytest

from library.providers import search_books

ISBN = "9788535914849"


def test_incomplete_google_result_gets_exact_edition_fields_and_cover(monkeypatch):
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        if "googleapis" in url:
            payload = {
                "items": [
                    {
                        "id": "google-id",
                        "volumeInfo": {
                            "title": "1984",
                            "authors": ["George Orwell"],
                            "industryIdentifiers": [{"identifier": ISBN}],
                        },
                    }
                ]
            }
        elif "brasilapi" in url:
            payload = {
                "isbn": ISBN,
                "title": "1984",
                "authors": ["George Orwell"],
                "publisher": "Companhia",
                "provider": kwargs["params"]["providers"],
            }
        elif url.endswith("/api/books"):
            payload = {
                f"ISBN:{ISBN}": {
                    "title": "1984",
                    "authors": [{"name": "George Orwell"}],
                    "number_of_pages": 416,
                    "publish_date": "2009",
                    "cover": {"large": "https://covers.openlibrary.org/b/id/42-L.jpg"},
                }
            }
        else:
            return httpx.Response(
                200,
                content=b"jpeg-image" * 20,
                headers={"content-type": "image/jpeg"},
                request=httpx.Request("GET", url),
            )
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))

    monkeypatch.setattr("library.providers.bounded_get", get)
    result = search_books(ISBN)[0]
    assert "brasilapi" in calls[0]
    assert calls.index(next(url for url in calls if "googleapis" in url)) > calls.index(
        next(url for url in calls if "openlibrary" in url and url.endswith("/api/books"))
    )
    assert result["publisher"] == "Companhia" and result["page_count"] == 416
    assert result["cover_url"].startswith("https://covers.openlibrary.org/")
    assert result["provenance"]["page_count"]["source"] == "openlibrary"
    assert result["provenance"]["title"]["source"] == "cbl"


def test_cbl_without_cover_does_not_hide_mercado_cover(monkeypatch):
    def get(url, **kwargs):
        if "googleapis" in url:
            payload = {"items": []}
        elif "brasilapi" in url:
            source = kwargs["params"]["providers"]
            payload = {
                "isbn": ISBN,
                "title": "1984",
                "authors": ["George Orwell"],
                "provider": source,
                "cover_url": "https://res.cloudinary.com/publisher/cover.jpg"
                if source == "mercado-editorial"
                else None,
            }
        elif "openlibrary" in url:
            payload = {}
        else:
            return httpx.Response(
                200,
                content=b"image" * 30,
                headers={"content-type": "image/jpeg"},
                request=httpx.Request("GET", url),
            )
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))

    monkeypatch.setattr("library.providers.bounded_get", get)
    result = search_books(ISBN)[0]
    assert result["source"] == "brasilapi"
    assert result["cover_url"].startswith("https://res.cloudinary.com/")
    assert result["provenance"]["cover_url"]["source"] == "mercado-editorial"


def test_image_check_rejects_callers_private_hosts_and_tiny_placeholder(monkeypatch):
    from library.providers import Lookup

    calls = []

    def get(url, **kwargs):
        calls.append(url)
        return httpx.Response(
            200,
            content=b"blank",
            headers={"content-type": "image/png"},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr("library.providers.bounded_get", get)
    lookup = Lookup()
    assert lookup.image("https://127.0.0.1/private") == ""
    assert lookup.image("https://covers.openlibrary.org/b/isbn/9788535914849-L.jpg") == ""
    assert len(calls) == 1 and "default=false" in calls[0]


def test_budget_and_positive_cache_do_not_repeat_public_queries(monkeypatch):
    from library.providers import Lookup

    calls = []

    def get(url, **kwargs):
        calls.append(url)
        return httpx.Response(200, json={"title": "Livro"}, request=httpx.Request("GET", url))

    monkeypatch.setattr("library.providers.bounded_get", get)
    lookup = Lookup()
    assert lookup.json("https://example.com/api", {})["title"] == "Livro"
    assert Lookup().json("https://example.com/api", {})["title"] == "Livro"
    assert len(calls) == 1
    expired = Lookup()
    expired.deadline = 0
    assert expired.json("https://example.com/other", {}) == {} and len(calls) == 1


def test_invalid_image_port_and_own_cover_do_not_trigger_image_fetch(monkeypatch):
    from library.providers import Lookup, enrich_book

    def get(url, **kwargs):
        assert not url.startswith("https://res.cloudinary.com/")
        return httpx.Response(200, json={}, request=httpx.Request("GET", url))

    monkeypatch.setattr("library.providers.bounded_get", get)
    assert Lookup().image("https://covers.openlibrary.org:invalid/image") == ""
    own = {
        "title": "Livro",
        "authors": ["Autor"],
        "isbn": ISBN,
        "cover_url": "https://res.cloudinary.com/own.jpg",
        "provenance": {"cover_url": {"source": "manual"}},
    }
    assert enrich_book(own)["cover_url"] == own["cover_url"]


def test_cover_redirect_only_follows_known_image_hosts(monkeypatch):
    from library.providers import Lookup

    calls = []

    def get(url, **kwargs):
        calls.append(url)
        if len(calls) == 1:
            return httpx.Response(
                302,
                headers={"location": "https://books.googleusercontent.com/cover.jpg"},
                request=httpx.Request("GET", url),
            )
        return httpx.Response(
            200,
            content=b"jpeg" * 100,
            headers={"content-type": "image/jpeg"},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr("library.providers.bounded_get", get)
    assert (
        Lookup().image("https://books.google.com/books/content?id=cover")
        == "https://books.googleusercontent.com/cover.jpg"
    )
    assert len(calls) == 2


def test_openlibrary_archive_redirect_is_validated_at_every_hop(monkeypatch):
    from library.providers import Lookup

    calls = []

    def get(url, **kwargs):
        calls.append(url)
        if len(calls) == 1:
            return httpx.Response(
                302,
                headers={"location": "https://archive.org/download/cover/cover.jpg"},
                request=httpx.Request("GET", url),
            )
        if len(calls) == 2:
            return httpx.Response(
                302,
                headers={
                    "location": "https://ia800100.us.archive.org/view_archive.php?archive=/cover.zip&file=cover.jpg"
                },
                request=httpx.Request("GET", url),
            )
        return httpx.Response(
            200,
            content=b"jpeg" * 100,
            headers={"content-type": "image/jpeg"},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr("library.providers.bounded_get", get)
    assert (
        Lookup()
        .image("https://covers.openlibrary.org/b/id/42-L.jpg")
        .startswith("https://ia800100.us.archive.org/view_archive.php")
    )


def test_conflicting_fields_are_kept_as_alternatives_not_overwritten():
    from library.providers import Lookup, fill

    result = {
        "page_count": 55,
        "source": "google",
        "source_id": "g",
        "provenance": {"page_count": {"source": "google", "source_id": "g"}},
    }
    fill(
        result,
        {
            "page_count": 310,
            "source": "openlibrary",
            "provenance": {"page_count": {"source": "openlibrary"}},
        },
        Lookup(),
    )
    assert result["page_count"] == 55
    assert result["provenance"]["page_count"]["alternatives"] == ["openlibrary: 310"]


@pytest.mark.django_db
def test_enrichment_endpoint_only_reads_external_data(client, member, monkeypatch):
    from library import providers
    from library.models import Book, Library, Membership

    lib = Library.objects.create(name="Casa")
    Membership.objects.create(library=lib, user=member)
    monkeypatch.setattr(providers, "enrich_book", lambda data: {**data, "publisher": "Editora"})
    response = client.post(
        "/api/v1/search/enrich",
        {"title": "Livro", "authors": ["Autor"]},
        content_type="application/json",
    )
    assert response.status_code == 200 and response.json()["publisher"] == "Editora"
    assert Book.objects.count() == 0
