import pytest
from django.core.exceptions import ValidationError

from library import services
from library.imports import preview_csv, process_rows
from library.models import Book, Copy, Library, Membership, Person, Tag

pytestmark = pytest.mark.django_db


def test_admin_library_is_immutable_for_existing_entities():
    from django.contrib import admin
    from django.test import RequestFactory

    from library.models import Location

    a = Library.objects.create(name="A")
    b = Library.objects.create(name="B")
    book = services.create_book(a, {"title": "Livro", "authors": ["Autor"]})
    services.add_copy(a, book.pk)
    objects = [
        book,
        Tag.objects.create(library=a, name="Tag"),
        Person.objects.create(library=a, name="Ana", phone="123"),
        Location.objects.create(library=a, name="Casa"),
    ]
    request = RequestFactory().get("/admin/")
    for obj in objects:
        assert "library" in admin.site._registry[type(obj)].get_readonly_fields(request, obj)
        obj.library = b
        with pytest.raises(ValidationError):
            obj.full_clean()


def test_registration_retry_is_transactional_and_idempotent(client, member):
    lib = Library.objects.create(name="A")
    Membership.objects.create(user=member, library=lib)
    payload = {
        "key": "e569f515-08f2-4af3-9213-94007016faab",
        "book": {"title": "Sem ISBN", "authors": ["Autor"]},
        "location_id": None,
        "acquired_on": None,
    }
    first = client.post("/api/v1/registrations", payload, content_type="application/json")
    second = client.post("/api/v1/registrations", payload, content_type="application/json")
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert Book.objects.count() == Copy.objects.count() == 1
    payload["book"]["title"] = "Different operation"
    assert (
        client.post("/api/v1/registrations", payload, content_type="application/json").status_code
        == 400
    )


def test_excel_empty_isbn13_falls_back_to_valid_isbn10():
    lib = Library.objects.create(name="A")
    services.create_book(lib, {"title": "Hobbit", "authors": ["Tolkien"], "isbn": "9780261102217"})
    session = preview_csv(
        lib, b'Book Id,Title,Author,ISBN,ISBN13\n1,Hobbit,Tolkien,="0261102214",=""\n'
    )
    row = session.rows.get()
    assert row.data["isbn"] == "9780261102217"
    process_rows(lib, session.pk, [{"id": row.pk, "action": "import"}])
    assert Book.objects.count() == 1 and Copy.objects.count() == 0
