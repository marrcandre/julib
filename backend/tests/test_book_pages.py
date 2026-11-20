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


def test_new_metadata_roundtrips_privately_and_publicly_without_provenance_leak(client, member):
    from library.sharing import public_books, renew_link

    lib = Library.objects.create(name="Casa")
    Membership.objects.create(user=member, library=lib)
    response = client.post(
        "/api/v1/books",
        {
            "title": "Livro",
            "authors": ["Autora"],
            "subtitle": "Uma edição especial",
            "description": "Sinopse em texto simples.",
            "subjects": ["História", " história ", "Literatura"],
            "provenance": {
                "subtitle": {"source": "google", "source_id": "volume-1"},
                "description": {
                    "source": "openlibrary",
                    "source_id": "/works/OL1W",
                    "record_type": "work",
                },
            },
        },
        content_type="application/json",
    )

    assert response.status_code == 200
    book = response.json()
    assert book["subtitle"] == "Uma edição especial"
    assert book["description"] == "Sinopse em texto simples."
    assert book["subjects"] == ["História", "Literatura"]
    assert "description" in book["provenance"]
    services.add_copy(lib, book["id"])
    public = public_books(renew_link(lib))["items"][0]
    assert public["subtitle"] == "Uma edição especial"
    assert public["description"] == "Sinopse em texto simples."
    assert public["subjects"] == ["História", "Literatura"]
    assert "provenance" not in public
    assert "tags" in public and public["tags"] == []


def test_manual_metadata_edit_clears_only_edited_field_provenance(client, member):
    lib = Library.objects.create(name="Casa")
    Membership.objects.create(user=member, library=lib)
    book = services.create_book(
        lib,
        {
            "title": "Livro",
            "authors": ["Autora"],
            "subtitle": "Subtítulo",
            "description": "Descrição antiga",
            "subjects": ["História"],
            "provenance": {
                "subtitle": {"source": "google", "source_id": "v1"},
                "description": {
                    "source": "openlibrary",
                    "source_id": "/works/OL1W",
                    "record_type": "work",
                },
                "subjects": {"source": "cbl", "source_id": "isbn"},
            },
        },
    )

    response = client.put(
        f"/api/v1/books/{book.pk}",
        {
            "title": "Livro",
            "authors": ["Autora"],
            "subtitle": "Subtítulo",
            "description": "Descrição manual",
            "subjects": ["História"],
        },
        content_type="application/json",
    )

    assert response.status_code == 200
    provenance = response.json()["provenance"]
    assert "description" not in provenance
    assert provenance["subtitle"]["source"] == "google"
    assert provenance["subjects"]["source"] == "cbl"


def test_new_metadata_limits_reject_values_instead_of_truncating(client, member):
    lib = Library.objects.create(name="Casa")
    Membership.objects.create(user=member, library=lib)
    base = {"title": "Livro", "authors": ["Autora"]}
    for extra in (
        {"subtitle": "x" * 501},
        {"description": "x" * 20_001},
        {"subjects": ["x"] * 51},
        {"subjects": ["x" * 201]},
    ):
        response = client.post("/api/v1/books", {**base, **extra}, content_type="application/json")
        assert response.status_code == 422


def test_pages_from_google_and_goodreads(monkeypatch):
    monkeypatch.setattr(
        "library.providers.bounded_get",
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
