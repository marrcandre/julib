from concurrent.futures import ThreadPoolExecutor

import pytest
from django.core.exceptions import ValidationError
from django.db import close_old_connections

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


def test_admin_cannot_demote_the_last_library_administrator(rf, member):
    from django.contrib.admin.sites import site
    from django.core.exceptions import PermissionDenied

    from library.models import Membership

    member.is_superuser = True
    member.save(update_fields=["is_superuser"])
    library = Library.objects.create(name="Admin único")
    membership = Membership.objects.create(user=member, library=library, role="admin")
    admin = site._registry[Membership]
    request = rf.post("/admin/library/membership/change/")
    membership.role = "member"

    with pytest.raises(PermissionDenied):
        admin.save_model(request, membership, form=None, change=True)

    membership.refresh_from_db()
    assert membership.role == "admin"


def test_admin_cannot_bulk_delete_last_administrators(rf):
    from django.contrib.admin.sites import site
    from django.core.exceptions import PermissionDenied

    from library.models import Membership, User

    library = Library.objects.create(name="Admins em lote")
    first = User.objects.create_user(username="first", email="first@example.com")
    second = User.objects.create_user(username="second", email="second@example.com")
    first_membership = Membership.objects.create(user=first, library=library, role="admin")
    second_membership = Membership.objects.create(user=second, library=library, role="admin")
    admin = site._registry[Membership]
    request = rf.post("/admin/library/membership/")

    with pytest.raises(PermissionDenied):
        admin.delete_queryset(
            request, Membership.objects.filter(pk__in=[first_membership.pk, second_membership.pk])
        )

    assert Membership.objects.filter(library=library, role="admin").count() == 2


def test_admin_cannot_individually_delete_last_membership(rf):
    from django.contrib.admin.sites import site
    from django.core.exceptions import PermissionDenied

    from library.models import Membership, User

    library = Library.objects.create(name="Membership única")
    administrator = User.objects.create_user(username="only", email="only@example.com")
    membership = Membership.objects.create(user=administrator, library=library, role="admin")

    with pytest.raises(PermissionDenied):
        site._registry[Membership].delete_model(
            rf.post("/admin/library/membership/delete/"), membership
        )

    assert Membership.objects.filter(pk=membership.pk).exists()


def test_admin_cannot_delete_user_who_is_last_library_administrator(rf, member):
    from django.contrib.admin.sites import site
    from django.core.exceptions import PermissionDenied

    from library.models import User

    member.is_superuser = True
    member.save(update_fields=["is_superuser"])
    library = Library.objects.create(name="Exclusivo")
    Membership.objects.create(user=member, library=library, role="admin")
    admin = site._registry[User]
    request = rf.post("/admin/auth/user/delete/")

    with pytest.raises(PermissionDenied):
        admin.delete_model(request, member)

    assert User.objects.filter(pk=member.pk).exists()
    assert Membership.objects.filter(user=member, library=library).exists()


def test_admin_user_delete_model_preserves_another_library_administrator(rf):
    from django.contrib.admin.sites import site

    from library.models import Membership, User

    library = Library.objects.create(name="Admin remanescente")
    removed = User.objects.create_user(username="removed", email="removed@example.com")
    remaining = User.objects.create_user(username="remaining", email="remaining@example.com")
    Membership.objects.create(user=removed, library=library, role="admin")
    Membership.objects.create(user=remaining, library=library, role="admin")

    site._registry[User].delete_model(rf.post("/admin/auth/user/delete/"), removed)

    assert not User.objects.filter(pk=removed.pk).exists()
    assert Membership.objects.filter(library=library, role="admin").count() == 1


def test_admin_cannot_bulk_delete_all_users_who_administer_same_library(rf):
    from django.contrib.admin.sites import site
    from django.core.exceptions import PermissionDenied

    from library.models import Membership, User

    library = Library.objects.create(name="Admin cascade em lote")
    first = User.objects.create_user(username="first-cascade", email="first-cascade@example.com")
    second = User.objects.create_user(username="second-cascade", email="second-cascade@example.com")
    Membership.objects.create(user=first, library=library, role="admin")
    Membership.objects.create(user=second, library=library, role="admin")

    with pytest.raises(PermissionDenied):
        site._registry[User].delete_queryset(
            rf.post("/admin/auth/user/"), User.objects.filter(pk__in=[first.pk, second.pk])
        )

    assert User.objects.filter(pk__in=[first.pk, second.pk]).count() == 2
    assert Membership.objects.filter(library=library, role="admin").count() == 2


@pytest.mark.django_db(transaction=True)
def test_concurrent_admin_user_deletions_cannot_remove_both_administrators(rf):
    from django.contrib.admin.sites import site
    from django.core.exceptions import PermissionDenied

    from library.models import Membership, User

    library = Library.objects.create(name="Admin delete concorrente")
    first = User.objects.create_user(username="admin-delete-a", email="a-delete@example.com")
    second = User.objects.create_user(username="admin-delete-b", email="b-delete@example.com")
    Membership.objects.create(user=first, library=library, role="admin")
    Membership.objects.create(user=second, library=library, role="admin")
    user_admin = site._registry[User]

    def delete_other(index: int) -> bool:
        close_old_connections()
        target = second if index == 0 else first
        try:
            user_admin.delete_model(rf.post("/admin/auth/user/delete/"), target)
            return True
        except PermissionDenied:
            return False
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(delete_other, (0, 1)))

    assert sorted(results) == [False, True]
    assert Membership.objects.filter(library=library, role="admin").count() == 1
