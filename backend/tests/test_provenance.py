import pytest

from library import media, services
from library.models import Book, Library, Membership
from library.presentation import book_data

pytestmark = pytest.mark.django_db


def test_registration_retains_sources_and_upload_replaces_only_cover_source(
    client, member, monkeypatch
):
    lib = Library.objects.create(name="Casa")
    Membership.objects.create(library=lib, user=member)
    book = services.create_book(
        lib,
        {
            "title": "Livro",
            "authors": ["Autor"],
            "publisher": "Editora",
            "source": "brasilapi",
            "source_id": "123",
            "cover_url": "https://books.google.com/books/content?id=cover",
            "provenance": {
                "publisher": {"source": "google", "source_id": "data"},
                "cover_url": {
                    "source": "google",
                    "source_id": "cover",
                    "url": "https://books.google.com/books/content?id=cover",
                },
            },
        },
    )
    assert Book.objects.get(pk=book.pk).provenance["publisher"]["source"] == "google"
    assert book_data(book)["metadata_attribution_name"] == "Google Books"
    monkeypatch.setattr(
        media,
        "verify_upload",
        lambda *args: {
            "cover_id": f"julib/{lib.pk}/own",
            "cover_url": "https://res.cloudinary.com/own.jpg",
        },
    )
    response = client.put(
        f"/api/v1/books/{book.pk}",
        {
            "title": "Livro",
            "authors": ["Autor"],
            "publisher": "Editora",
            "source": "brasilapi",
            "source_id": "123",
            "cover_public_id": f"julib/{lib.pk}/own",
        },
        content_type="application/json",
    )
    assert response.status_code == 200
    book.refresh_from_db()
    assert book.provenance["publisher"]["source"] == "google"
    assert book.provenance["cover_url"]["source"] == "manual"
    assert book_data(book)["attribution_name"] == ""


def test_old_registration_retry_with_new_empty_provenance_is_idempotent(client, member):
    from uuid import uuid4

    lib = Library.objects.create(name="Casa")
    Membership.objects.create(library=lib, user=member)
    payload = {"key": str(uuid4()), "book": {"title": "Livro", "authors": ["Autor"]}}
    first = client.post("/api/v1/registrations", payload, content_type="application/json")
    assert first.status_code == 200
    payload["book"]["provenance"] = {}
    second = client.post("/api/v1/registrations", payload, content_type="application/json")
    assert second.json() == first.json() and Book.objects.count() == 1


def test_additive_migration_accepts_old_writer_without_provenance():
    from django.db import connection
    from django.db.migrations.loader import MigrationLoader

    old_apps = (
        MigrationLoader(connection)
        .project_state([("library", "0007_book_is_desired_alter_importrow_copy_and_more")])
        .apps
    )
    lib = Library.objects.create(name="Casa")
    old_book = old_apps.get_model("library", "Book").objects.create(
        library_id=lib.pk, title="Old writer", authors=["Autor"]
    )
    assert Book.objects.get(pk=old_book.pk).provenance == {}
