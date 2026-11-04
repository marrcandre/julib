import httpx
import pytest
from django.core.management import call_command

from library.cover_lookup import lookup_cover
from library.models import Book, Library
from library.presentation import book_data

pytestmark = pytest.mark.django_db
ISBN = "9780140328721"
GOOGLE_COVER = "https://books.google.com/books/content?id=match&img=1"


def test_exact_isbn_cover_and_openlibrary_fallback():
    def handler(request):
        if request.url.host == "www.googleapis.com":
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "wrong",
                            "volumeInfo": {
                                "industryIdentifiers": [{"identifier": "9780261103573"}],
                                "imageLinks": {"thumbnail": GOOGLE_COVER},
                            },
                        }
                    ]
                },
            )
        if request.url.path == "/api/books":
            return httpx.Response(
                200,
                json={
                    f"ISBN:{ISBN}": {
                        "cover": {"large": "https://covers.openlibrary.org/b/id/123-L.jpg"}
                    }
                },
            )
        return httpx.Response(200, content=b"image", headers={"content-type": "image/jpeg"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert lookup_cover(client, ISBN, "Title", ["Author"]) == (
            "https://covers.openlibrary.org/b/id/123-L.jpg"
        )


def test_ambiguous_title_and_author_does_not_choose_a_cover():
    def handler(request):
        if request.url.host == "www.googleapis.com":
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": str(i),
                            "volumeInfo": {
                                "title": "Title",
                                "authors": ["Author"],
                                "imageLinks": {"thumbnail": GOOGLE_COVER + str(i)},
                            },
                        }
                        for i in range(2)
                    ]
                },
            )
        return httpx.Response(200, json={"docs": []})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert lookup_cover(client, "", "Title", ["Author"]) == ""


def test_command_preserves_import_identity_existing_covers_and_library_scope(monkeypatch):
    from library.management.commands import enrich_covers

    lib = Library.objects.create(name="Casa")
    book = Book.objects.create(
        library=lib, title="Title", authors=["Author"], source="goodreads", source_id="goodreads-1"
    )
    existing = Book.objects.create(
        library=lib, title="Existing", cover_url="https://example.com/own.jpg"
    )
    other = Book.objects.create(library=Library.objects.create(name="Other"), title="Other")
    monkeypatch.setattr(enrich_covers, "lookup_cover", lambda *args: GOOGLE_COVER)
    call_command("enrich_covers", library=lib.pk, delay=0)
    book.refresh_from_db()
    existing.refresh_from_db()
    other.refresh_from_db()
    assert (book.source, book.source_id) == ("goodreads", "goodreads-1")
    assert book.cover_url == GOOGLE_COVER
    assert existing.cover_url == "https://example.com/own.jpg"
    assert other.cover_url == ""
    data = book_data(book)
    assert data["attribution_name"] == "Google Books"
    assert data["attribution_url"] == "https://books.google.com/books?id=match"
