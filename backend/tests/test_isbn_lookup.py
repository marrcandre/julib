import httpx
import pytest

from library.providers import search_books


def response(url, data, status=200):
    return httpx.Response(status, json=data, request=httpx.Request("GET", url))


@pytest.mark.parametrize(
    ("query", "isbn", "returned"),
    [
        ("9788570550156", "9788570550156", "8570550154"),
        ("isbn:9786583581112", "9786583581112", "9786583581112"),
        ("978-85-7055-015-6", "9788570550156", "8570550154"),
    ],
)
def test_brazilian_isbn_fallback_normalizes_and_matches(monkeypatch, query, isbn, returned):
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs.get("params", {})))
        if "googleapis" in url:
            return response(url, {"items": []})
        if "openlibrary" in url:
            return response(url, {"docs": []})
        return response(
            url,
            {
                "isbn": returned,
                "title": "Título brasileiro",
                "authors": ["Autor"],
                "publisher": "Editora",
                "page_count": 656,
                "year": 2025,
                "provider": "cbl",
                "cover_url": None,
            },
        )

    monkeypatch.setattr("library.providers.bounded_get", get)
    books = search_books(query)
    assert len(books) == 1
    assert books[0]["isbn"] == isbn
    assert books[0]["title"] == "Título brasileiro"
    assert books[0]["source"] == "brasilapi"
    assert books[0]["page_count"] == 656
    assert calls[0][1]["q"] == "isbn:" + isbn
    assert any(
        url == "https://brasilapi.com.br/api/isbn/v1/" + isbn and params.get("providers") == "cbl"
        for url, params in calls
    )
    assert any(params.get("providers") == "mercado-editorial" for _, params in calls)


def test_isbn_search_rejects_wrong_editions_and_preserves_text_search(monkeypatch):
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        if "googleapis" in url:
            return response(
                url,
                {
                    "items": [
                        {
                            "id": "wrong",
                            "volumeInfo": {
                                "title": "Outra edição",
                                "authors": ["Autor"],
                                "industryIdentifiers": [
                                    {"type": "ISBN_13", "identifier": "9780261102217"}
                                ],
                            },
                        }
                    ]
                },
            )
        if "openlibrary" in url:
            return response(url, {"docs": []})
        return response(url, {"isbn": "9780261102217", "title": "Errado", "authors": ["Autor"]})

    monkeypatch.setattr("library.providers.bounded_get", get)
    assert search_books("9788570550156") == []
    calls.clear()
    assert search_books("Outra edição")[0]["title"] == "Outra edição"
    assert len(calls) == 1


def test_missing_isbn_is_not_found_and_network_failure_is_honest(monkeypatch):
    from django.core.exceptions import ValidationError

    def get(url, **kwargs):
        if "googleapis" in url:
            return response(url, {"items": []})
        if "openlibrary" in url:
            return response(url, {"docs": []})
        return response(url, {}, 404)

    monkeypatch.setattr("library.providers.bounded_get", get)
    assert search_books("9788570550156") == []

    def fail(url, **kwargs):
        raise httpx.ReadTimeout("unavailable")

    monkeypatch.setattr("library.providers.bounded_get", fail)
    with pytest.raises(ValidationError):
        search_books("9788570550156")


def test_brasilapi_attribution_and_google_cover_provenance():
    from library.models import Book
    from library.presentation import cover_attribution

    book = Book(title="Livro", source="brasilapi", source_id="9788570550156")
    assert cover_attribution(book)["attribution_name"] == ""
    book.cover_url = "https://books.google.com/books/content?id=test&img=1"
    assert cover_attribution(book)["attribution_name"] == "Google Books"
