from datetime import date

import httpx
import pytest

from library import services
from library.imports import preview_csv, process_rows
from library.models import Library, Membership
from library.providers import search_books

pytestmark = pytest.mark.django_db


def test_optional_pages_roundtrip_validation_and_public_catalog(client, member):
    from library.sharing import public_books, renew_link

    lib = Library.objects.create(name="Casa")
    Membership.objects.create(user=member, library=lib)
    payload = {"title": "Livro", "authors": ["Autor"], "page_count": 320}
    response = client.post("/api/v1/books", payload, content_type="application/json")
    assert response.status_code == 200
    book = response.json()
    assert book["page_count"] == 320
    services.add_copy(lib, book["id"])
    assert public_books(renew_link(lib))["items"][0]["page_count"] == 320
    for invalid in [0, -1, 2147483648]:
        assert (
            client.put(
                f"/api/v1/books/{book['id']}",
                {**payload, "page_count": invalid},
                content_type="application/json",
            ).status_code
            == 422
        )
    assert (
        client.put(
            f"/api/v1/books/{book['id']}",
            {**payload, "page_count": None},
            content_type="application/json",
        ).json()["page_count"]
        is None
    )


def test_pages_from_google_and_goodreads(monkeypatch):
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *a, **kw: httpx.Response(
            200,
            request=httpx.Request("GET", "https://example.com"),
            json={"items": [{"id": "test", "volumeInfo": {"title": "Livro", "pageCount": 200}}]},
        ),
    )
    assert search_books("Livro")[0]["page_count"] == 200
    lib = Library.objects.create(name="Casa")
    session = preview_csv(
        lib,
        b"Book Id,Title,Author,Number of Pages\n1,Livro,Autor,321\n2,Outro,Autor,0\n3,Terceiro,Autor,invalid\n",
    )
    rows = list(session.rows.all())
    assert [row.data["page_count"] for row in rows] == [321, None, None]
    process_rows(lib, session.pk, [{"id": rows[0].pk, "action": "import"}])
    assert lib.book_set.get().page_count == 321


def test_recent_acquisitions_have_five_distinct_books_in_date_order(client, member):
    lib = Library.objects.create(name="Casa")
    Membership.objects.create(user=member, library=lib)
    books = [
        services.create_book(lib, {"title": f"Livro {i}", "authors": ["Autor"]}) for i in range(7)
    ]
    for i, book in enumerate(books):
        services.add_copy(lib, book.pk, acquired_on=date(2026, 1, i + 1))
    services.add_copy(lib, books[0].pk, acquired_on=date(2026, 2, 1))
    services.add_copy(lib, books[0].pk, acquired_on=date(2026, 3, 1))
    recent = client.get("/api/v1/dashboard").json()["recent"]
    assert [row["book"]["id"] for row in recent] == [books[i].pk for i in [0, 6, 5, 4, 3]]


def test_fill_existing_goodreads_pages_only_changes_empty_exact_matches():
    from library.imports import fill_goodreads_pages

    lib = Library.objects.create(name="Casa")
    other = Library.objects.create(name="Outra")

    def book(library, source_id, pages=None, source="goodreads"):
        return services.create_book(
            library,
            {
                "title": "Livro",
                "authors": ["Autor"],
                "source": source,
                "source_id": source_id,
                "page_count": pages,
            },
        )

    empty = book(lib, "1")
    known = book(lib, "2", 400)
    foreign = book(other, "1")
    different_source = book(lib, "1", source="google")
    csv = b"Book Id,Number of Pages\n1,300\n2,222\n3,0\n"
    assert fill_goodreads_pages(lib, csv) == 1
    empty.refresh_from_db()
    assert empty.page_count is None
    assert fill_goodreads_pages(lib, csv, apply=True) == 1
    assert fill_goodreads_pages(lib, csv, apply=True) == 0
    for obj, count in [(empty, 300), (known, 400), (foreign, None), (different_source, None)]:
        obj.refresh_from_db()
        assert obj.page_count == count
