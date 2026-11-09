from io import StringIO

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


def test_cover_redirect_cannot_fetch_an_untrusted_destination():
    from library.cover_lookup import usable

    hosts = []

    def handler(request):
        hosts.append(request.url.host)
        if request.url.host == "books.google.com":
            return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})
        return httpx.Response(200, content=b"private", headers={"content-type": "image/jpeg"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert usable(client, GOOGLE_COVER) == ""
    assert hosts == ["books.google.com"]


def test_bulk_enrichment_defaults_to_preview_without_saving(monkeypatch):
    from library import providers

    lib = Library.objects.create(name="Casa")
    book = Book.objects.create(
        library=lib,
        title="Livro",
        authors=["Autora"],
        isbn=ISBN,
        source="goodreads",
        source_id="g-123",
    )
    monkeypatch.setattr(
        providers,
        "enrich_book",
        lambda data: {
            **data,
            "page_count": 280,
            "cover_url": GOOGLE_COVER,
            "provenance": {
                "page_count": {"source": "google", "source_id": "g-123"},
                "cover_url": {
                    "source": "openlibrary",
                    "source_id": "ol-123",
                    "url": GOOGLE_COVER,
                },
            },
        },
    )
    output = StringIO()

    call_command("enrich_books", library=lib.pk, delay=0, stdout=output)

    book.refresh_from_db()
    assert book.page_count is None
    assert book.cover_url == ""
    assert book.provenance == {}
    assert "Prévia" in output.getvalue()
    assert "páginas, capa" in output.getvalue()


def test_bulk_enrichment_apply_fills_only_blank_fields_and_merges_provenance(monkeypatch):
    from library import providers

    lib = Library.objects.create(name="Casa")
    book = Book.objects.create(
        library=lib,
        title="Título manual",
        authors=["Autora manual"],
        isbn=ISBN,
        publisher="Editora manual",
        page_count=400,
        cover_url="https://res.cloudinary.com/julib/manual.jpg",
        cover_id="julib/manual",
        source="goodreads",
        source_id="g-123",
        provenance={"publisher": {"source": "manual"}},
    )
    other = Book.objects.create(
        library=Library.objects.create(name="Outra"),
        title="Outro livro",
        authors=["Autor"],
        isbn="9780306406157",
    )
    calls = []

    def enrich(data):
        calls.append(data["isbn"])
        return {
            **data,
            "publisher": "Editora API",
            "year": "2001",
            "page_count": 999,
            "cover_url": GOOGLE_COVER,
            "provenance": {
                "publisher": {"source": "google"},
                "year": {"source": "google", "source_id": "g"},
                "page_count": {"source": "google", "source_id": "g"},
                "cover_url": {"source": "google", "source_id": "g", "url": GOOGLE_COVER},
            },
        }

    monkeypatch.setattr(providers, "enrich_book", enrich)

    call_command("enrich_books", library=lib.pk, delay=0, apply=True, stdout=StringIO())

    book.refresh_from_db()
    other.refresh_from_db()
    assert (book.title, book.authors, book.publisher, book.page_count) == (
        "Título manual",
        ["Autora manual"],
        "Editora manual",
        400,
    )
    assert book.year == "2001"
    assert book.cover_url == "https://res.cloudinary.com/julib/manual.jpg"
    assert book.cover_id == "julib/manual"
    assert book.source == "goodreads" and book.source_id == "g-123"
    assert book.provenance == {
        "publisher": {"source": "manual"},
        "year": {"source": "google", "source_id": "g"},
    }
    assert calls == [ISBN]
    assert other.year == "" and other.page_count is None


def test_bulk_enrichment_rechecks_fields_after_provider_lookup(monkeypatch):
    from library import providers

    lib = Library.objects.create(name="Casa")
    book = Book.objects.create(
        library=lib,
        title="Livro",
        authors=["Autora"],
        isbn=ISBN,
        source="goodreads",
        source_id="g-123",
    )

    def concurrent_edit(data):
        Book.objects.filter(pk=book.pk).update(page_count=310)
        return {**data, "page_count": 280}

    monkeypatch.setattr(providers, "enrich_book", concurrent_edit)

    call_command("enrich_books", library=lib.pk, delay=0, apply=True, stdout=StringIO())

    book.refresh_from_db()
    assert book.page_count == 310


def test_bulk_enrichment_does_not_refill_a_field_that_was_not_missing_at_start(monkeypatch):
    from library import providers

    lib = Library.objects.create(name="Casa")
    book = Book.objects.create(
        library=lib,
        title="Livro",
        authors=["Autora"],
        isbn=ISBN,
        publisher="Editora cadastrada",
    )

    def concurrent_edit(data):
        Book.objects.filter(pk=book.pk).update(publisher="")
        return {**data, "publisher": "Editora cadastrada", "page_count": 280}

    monkeypatch.setattr(providers, "enrich_book", concurrent_edit)

    call_command("enrich_books", library=lib.pk, delay=0, apply=True, stdout=StringIO())

    book.refresh_from_db()
    assert book.publisher == ""
    assert book.page_count == 280


def test_bulk_enrichment_skips_books_without_a_valid_isbn(monkeypatch):
    from library import providers

    lib = Library.objects.create(name="Casa")
    no_isbn = Book.objects.create(library=lib, title="Sem ISBN", authors=["Autora"])
    bad_isbn = Book.objects.create(
        library=lib, title="ISBN inválido", authors=["Autor"], isbn="9780000000000"
    )
    calls = []
    monkeypatch.setattr(providers, "enrich_book", lambda data: calls.append(data) or data)
    output = StringIO()

    call_command("enrich_books", library=lib.pk, delay=0, apply=True, stdout=output)

    no_isbn.refresh_from_db()
    bad_isbn.refresh_from_db()
    assert calls == []
    assert no_isbn.provenance == {} and bad_isbn.provenance == {}
    assert "ISBN inválido ou ausente" in output.getvalue()


def test_bulk_enrichment_leaves_book_unchanged_when_sources_return_no_new_fields(monkeypatch):
    from library import providers

    lib = Library.objects.create(name="Casa")
    book = Book.objects.create(
        library=lib,
        title="Livro",
        authors=["Autora"],
        isbn=ISBN,
        source="goodreads",
        source_id="g-123",
    )
    monkeypatch.setattr(providers, "enrich_book", lambda data: data)

    call_command("enrich_books", library=lib.pk, delay=0, apply=True, stdout=StringIO())

    book.refresh_from_db()
    assert book.page_count is None
    assert book.cover_url == ""
    assert book.provenance == {}


def test_bulk_enrichment_is_resumable_after_fields_are_filled(monkeypatch):
    from library import providers

    lib = Library.objects.create(name="Casa")
    book = Book.objects.create(
        library=lib,
        title="Livro",
        authors=["Autora"],
        isbn=ISBN,
        publisher="Editora",
        edition="1ª edição",
        year="2000",
        language="pt",
        cover_url=GOOGLE_COVER,
    )
    calls = []

    def enrich(data):
        calls.append(data["isbn"])
        return {**data, "page_count": 280}

    monkeypatch.setattr(providers, "enrich_book", enrich)
    call_command("enrich_books", library=lib.pk, delay=0, apply=True, stdout=StringIO())
    call_command("enrich_books", library=lib.pk, delay=0, apply=True, stdout=StringIO())

    book.refresh_from_db()
    assert book.page_count == 280
    assert calls == [ISBN]


def test_bulk_enrichment_limit_counts_valid_isbn_books_not_skipped_records(monkeypatch):
    from library import providers

    lib = Library.objects.create(name="Casa")
    Book.objects.create(library=lib, title="Sem ISBN", authors=["Autora"])
    valid = Book.objects.create(
        library=lib,
        title="Livro com ISBN",
        authors=["Autora"],
        isbn=ISBN,
        publisher="Editora",
        edition="1ª edição",
        year="2000",
        language="pt",
        cover_url=GOOGLE_COVER,
    )
    calls = []
    monkeypatch.setattr(
        providers,
        "enrich_book",
        lambda data: calls.append(data["isbn"]) or {**data, "page_count": 280},
    )

    call_command("enrich_books", library=lib.pk, limit=1, delay=0, stdout=StringIO())

    valid.refresh_from_db()
    assert calls == [ISBN]
    assert valid.page_count is None
