from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier
from uuid import uuid4

import pytest
from django.core.exceptions import ValidationError
from django.db import close_old_connections
from django.test import Client

from library import services
from library.circulation import lend, retire_copy, return_loan
from library.imports import preview_csv, process_rows
from library.models import Book, Copy, Library, Membership, Person, Registration
from library.sharing import public_books, renew_link

pytestmark = pytest.mark.django_db


def intent(**kwargs):
    return {"key": uuid4(), "book": {"title": "Desejado", "authors": ["Autor"]}, **kwargs}


def test_wish_acquire_and_legacy_retry(client, member):
    lib = Library.objects.create(name="Casa")
    Membership.objects.create(library=lib, user=member)
    data = intent(target="wishlist")
    result = services.register_copy(lib, data)
    book = Book.objects.get(pk=result["book_id"])
    assert book.is_desired and result["copy_id"] is None and not Copy.objects.exists()
    assert services.register_copy(lib, data) == result
    assert client.get("/api/v1/books").json()["total"] == 0
    assert client.get("/api/v1/books?scope=wishlist").json()["total"] == 1
    assert public_books(renew_link(lib))["total"] == 0
    acquire = intent(existing_book_id=book.pk)
    acquired = services.register_copy(lib, acquire)
    assert services.register_copy(lib, {**acquire, "target": "collection"}) == acquired
    book.refresh_from_db()
    assert not book.is_desired and book.copies.count() == 1


def test_deletion_preserves_receipts_and_import_completion():
    lib = Library.objects.create(name="Casa")
    data = intent()
    result = services.register_copy(lib, data)
    services.delete_book(lib, result["book_id"])
    receipt = Registration.objects.get(key=data["key"])
    assert receipt.book_id is None and receipt.copy_id is None
    with pytest.raises(ValidationError, match="excluído"):
        services.register_copy(lib, data)
    session = preview_csv(lib, b"Book Id,Title,Author,ISBN,ISBN13\n1,Imported,Author,,\n")
    row = session.rows.get()
    actions = [{"id": row.pk, "action": "import"}]
    process_rows(lib, session.pk, actions)
    row.refresh_from_db()
    services.delete_book(lib, row.copy.book_id)
    process_rows(lib, session.pk, actions)
    assert not Book.objects.exists() and not Copy.objects.exists()
    row.refresh_from_db()
    assert row.copy_id is None and row.result


@pytest.mark.parametrize("returned", [False, True])
def test_any_loan_history_blocks_delete_and_reclassification(returned):
    lib = Library.objects.create(name="Casa")
    result = services.register_copy(lib, intent())
    person = Person.objects.create(library=lib, name="Ana", phone="123")
    loan = lend(lib, result["copy_id"], person.pk)
    if returned:
        return_loan(lib, loan.pk, date.today())
    with pytest.raises(ValidationError, match="histórico"):
        services.delete_book(lib, result["book_id"])
    with pytest.raises(ValidationError, match="histórico"):
        services.move_to_wishlist(lib, result["book_id"])
    if returned:
        retire_copy(lib, result["copy_id"], "donated")
        services.move_to_wishlist(lib, result["book_id"])
        assert Book.objects.get(pk=result["book_id"]).is_desired
        assert loan.__class__.objects.filter(pk=loan.pk).exists()
        with pytest.raises(ValidationError):
            retire_copy(lib, result["copy_id"], "active")


def test_move_to_wishlist_is_explicit_and_foreign_library_is_rejected(client, member):
    lib = Library.objects.create(name="Casa")
    Membership.objects.create(library=lib, user=member)
    data = intent()
    result = services.register_copy(lib, data)
    services.move_to_wishlist(lib, result["book_id"])
    assert not Copy.objects.exists()
    with pytest.raises(ValidationError):
        services.register_copy(lib, data)
    foreign = Library.objects.create(name="Outra")
    book = services.create_book(foreign, {"title": "Privado", "authors": ["Autor"]})
    assert client.delete(f"/api/v1/books/{book.pk}").status_code == 400
    assert client.post(f"/api/v1/books/{book.pk}/wishlist").status_code == 400
    assert Book.objects.filter(pk=book.pk).exists()


def test_wishlist_api_validates_target_and_requires_csrf(client, member):
    lib = Library.objects.create(name="Casa")
    Membership.objects.create(library=lib, user=member)
    payload = intent(target="wishlist")
    payload["key"] = str(payload["key"])
    response = client.post("/api/v1/registrations", payload, content_type="application/json")
    assert response.status_code == 200
    book_id = response.json()["book_id"]
    data = client.get(f"/api/v1/books/{book_id}").json()
    assert data["is_desired"] and data["can_delete"] and data["copies"] == []
    strict = Client(enforce_csrf_checks=True)
    strict.force_login(member)
    assert strict.delete(f"/api/v1/books/{book_id}").status_code == 403
    assert strict.post(f"/api/v1/books/{book_id}/wishlist").status_code == 403
    assert (
        client.post(
            "/api/v1/registrations", {**payload, "target": "bad"}, content_type="application/json"
        ).status_code
        == 422
    )
    assert client.delete(f"/api/v1/books/{book_id}").status_code == 200
    assert client.get(f"/api/v1/books/{book_id}").status_code == 404


@pytest.mark.django_db(transaction=True)
def test_lending_and_deletion_serialize_without_losing_history():
    lib = Library.objects.create(name="Casa")
    result = services.register_copy(lib, intent())
    person = Person.objects.create(library=lib, name="Ana", phone="123")
    barrier = Barrier(2)

    def attempt(action):
        close_old_connections()
        try:
            barrier.wait(timeout=5)
            if action == "lend":
                lend(lib, result["copy_id"], person.pk)
            else:
                services.delete_book(lib, result["book_id"])
            return action
        except ValidationError:
            return None
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, ["lend", "delete"]))
    assert len([item for item in outcomes if item]) == 1
    if "lend" in outcomes:
        assert Book.objects.filter(pk=result["book_id"]).exists()
        assert Person.objects.get(pk=person.pk).loans.count() == 1
    else:
        assert not Book.objects.filter(pk=result["book_id"]).exists()


def test_importing_a_wish_acquires_it_without_duplicating_edition():
    lib = Library.objects.create(name="Casa")
    result = services.register_copy(
        lib,
        intent(
            target="wishlist",
            book={"title": "The Hobbit", "authors": ["Tolkien"], "isbn": "9780261102217"},
        ),
    )
    session = preview_csv(
        lib, b"Book Id,Title,Author,ISBN,ISBN13\n1,The Hobbit,Tolkien,,9780261102217\n"
    )
    process_rows(lib, session.pk, [{"id": session.rows.get().pk, "action": "import"}])
    book = Book.objects.get(pk=result["book_id"])
    assert not book.is_desired and book.copies.count() == 1 and Book.objects.count() == 1


def test_schema_reverse_refuses_to_discard_wishes_or_deletion_receipts():
    from importlib import import_module
    from types import SimpleNamespace

    from django.apps import apps

    preflight = import_module(
        "library.migrations.0007_book_is_desired_alter_importrow_copy_and_more"
    ).preflight_reverse
    editor = SimpleNamespace(connection=SimpleNamespace(alias="default"))
    preflight(apps, editor)
    lib = Library.objects.create(name="Casa")
    result = services.register_copy(lib, intent(target="wishlist"))
    with pytest.raises(RuntimeError, match="Reversão bloqueada"):
        preflight(apps, editor)
    services.delete_book(lib, result["book_id"])
    with pytest.raises(RuntimeError, match="Reversão bloqueada"):
        preflight(apps, editor)
