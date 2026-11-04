import pytest
from django.core.exceptions import ValidationError

from library import services
from library.models import Copy, Library, Loan, Location, Membership, Person

pytestmark = pytest.mark.django_db


def test_admin_forms_reject_foreign_relations_and_cycles():
    from library.admin import LocationAdminForm

    a = Library.objects.create(name="A")
    Library.objects.create(name="B")
    root = Location.objects.create(library=a, name="Casa")
    child = Location.objects.create(library=a, name="Estante", parent=root)
    form = LocationAdminForm(
        data={"library": a.pk, "name": "Casa", "parent": child.pk}, instance=root
    )
    assert not form.is_valid()
    person = Person(library=a, name=" ", phone=" ")
    with pytest.raises(ValidationError):
        person.full_clean()


def test_admin_can_add_copies_and_loans_without_bypassing_services(client, member):
    member.is_superuser = True
    member.save()
    lib = Library.objects.create(name="Casa")
    Membership.objects.create(user=member, library=lib)
    book = services.create_book(lib, {"title": "Livro", "authors": ["Autor"]})
    result = client.post(
        "/admin/library/copy/add/",
        {"library": lib.pk, "book": book.pk, "acquired_on": "2026-11-04", "_save": "Save"},
    )
    assert result.status_code == 302
    copy = Copy.objects.get(book=book)
    assert copy.number == 1
    person = Person.objects.create(library=lib, name="Ana", phone="123")
    result = client.post(
        "/admin/library/loan/add/",
        {
            "library": lib.pk,
            "copy": copy.pk,
            "person": person.pk,
            "started_on": "2026-11-04",
            "due_on": "2026-12-04",
            "_save": "Save",
        },
    )
    assert result.status_code == 302
    assert Loan.objects.filter(copy=copy, state="open").count() == 1
