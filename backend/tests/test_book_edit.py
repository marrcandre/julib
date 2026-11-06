import pytest

from library import media, services
from library.models import Book, Library, Membership

pytestmark = pytest.mark.django_db


def test_book_edit_commits_metadata_and_verified_cover_together(client, member, monkeypatch):
    lib = Library.objects.create(name="Casa")
    Membership.objects.create(library=lib, user=member)
    book = services.create_book(lib, {"title": "Antes", "authors": ["Autor"]})
    monkeypatch.setattr(
        media,
        "verify_upload",
        lambda library, public_id: {
            "cover_id": public_id,
            "cover_url": "https://res.cloudinary.com/new.jpg",
        },
    )
    response = client.put(
        f"/api/v1/books/{book.pk}",
        {
            "title": "Depois",
            "authors": ["Autora"],
            "page_count": 320,
            "cover_public_id": f"julib/{lib.pk}/new",
        },
        content_type="application/json",
    )
    assert response.status_code == 200
    book.refresh_from_db()
    assert book.title == "Depois" and book.cover_id.endswith("/new") and book.page_count == 320
    assert response.json()["cover_url"] == "https://res.cloudinary.com/new.jpg"
    response = client.put(
        f"/api/v1/books/{book.pk}",
        {"title": "", "authors": ["Autora"], "cover_public_id": f"julib/{lib.pk}/other"},
        content_type="application/json",
    )
    assert response.status_code in [400, 422]
    book.refresh_from_db()
    assert book.title == "Depois" and book.cover_id.endswith("/new")
    # Service-level failure after verification must roll back all book/tag changes.
    response = client.put(
        f"/api/v1/books/{book.pk}",
        {
            "title": "Falha",
            "authors": ["Autora"],
            "isbn": "invalid",
            "cover_public_id": f"julib/{lib.pk}/other",
        },
        content_type="application/json",
    )
    assert response.status_code == 400
    book.refresh_from_db()
    assert book.title == "Depois" and book.cover_id.endswith("/new")


def test_book_edit_cover_isolation_and_manual_url(client, member, monkeypatch):
    lib = Library.objects.create(name="Casa")
    Membership.objects.create(library=lib, user=member)
    book = services.create_book(
        lib,
        {"title": "Livro", "authors": ["Autor"], "cover_url": "https://res.cloudinary.com/old.jpg"},
    )
    Book.objects.filter(pk=book.pk).update(cover_id=f"julib/{lib.pk}/old")
    # Real verifier rejects foreign IDs before any provider call.
    response = client.put(
        f"/api/v1/books/{book.pk}",
        {"title": "Alterado", "authors": ["Autor"], "cover_public_id": "another-library/id"},
        content_type="application/json",
    )
    assert response.status_code == 400
    book.refresh_from_db()
    assert book.title == "Livro" and book.cover_id.endswith("/old")
    other = Library.objects.create(name="Outra")
    foreign = services.create_book(other, {"title": "Privado", "authors": ["Autor"]})
    assert (
        client.put(
            f"/api/v1/books/{foreign.pk}",
            {"title": "Alterado", "authors": ["Autor"]},
            content_type="application/json",
        ).status_code
        == 400
    )
    assert client.get(f"/api/v1/books/{foreign.pk}").status_code == 404
    response = client.put(
        f"/api/v1/books/{book.pk}",
        {"title": "Livro", "authors": ["Autor"], "cover_url": "https://example.com/manual.jpg"},
        content_type="application/json",
    )
    assert response.status_code == 200
    book.refresh_from_db()
    assert book.cover_id == "" and book.cover_url == "https://example.com/manual.jpg"
