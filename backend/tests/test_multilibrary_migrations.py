from datetime import date

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

pytestmark = pytest.mark.django_db(transaction=True)


def test_multilibrary_migrations_preserve_data_and_do_not_grant_create_capability(request):
    targets = MigrationExecutor(connection).loader.graph.leaf_nodes()
    request.addfinalizer(lambda: MigrationExecutor(connection).migrate(targets))
    legacy_target = [("library", "0009_alter_library_name")]
    executor = MigrationExecutor(connection)
    executor.migrate(legacy_target)
    old_apps = MigrationExecutor(connection).loader.project_state(legacy_target).apps

    User = old_apps.get_model("library", "User")
    Library = old_apps.get_model("library", "Library")
    Membership = old_apps.get_model("library", "Membership")
    Book = old_apps.get_model("library", "Book")
    Copy = old_apps.get_model("library", "Copy")
    Person = old_apps.get_model("library", "Person")
    Loan = old_apps.get_model("library", "Loan")

    admin = User.objects.create(
        username="legacy-admin",
        email="marco@example.com",
        password="!",
        is_staff=True,
        is_superuser=True,
    )
    staff = User.objects.create(
        username="legacy-staff",
        email="staff@example.com",
        password="!",
        is_staff=True,
        is_superuser=False,
    )
    member_user = User.objects.create(
        username="legacy-member",
        email="member@example.com",
        password="!",
        is_staff=False,
        is_superuser=False,
    )
    library = Library.objects.create(name="Biblioteca preservada", next_number=2)
    Membership.objects.create(user=admin, library=library)
    Membership.objects.create(user=staff, library=library)
    Membership.objects.create(user=member_user, library=library)
    book = Book.objects.create(
        library=library,
        title="Livro preservado",
        authors=["Autora"],
        cover_id="julib/legacy/capa",
    )
    copy = Copy.objects.create(library=library, book=book, number=1)
    person = Person.objects.create(library=library, name="Ana", phone="123")
    Loan.objects.create(
        library=library,
        copy=copy,
        person=person,
        started_on=date(2026, 1, 1),
        due_on=date(2026, 2, 1),
    )
    original_ids = (library.pk, admin.pk, book.pk, copy.pk)

    MigrationExecutor(connection).migrate(targets)

    from library.models import Book as CurrentBook
    from library.models import Copy as CurrentCopy
    from library.models import Library as CurrentLibrary
    from library.models import Loan as CurrentLoan
    from library.models import Membership as CurrentMembership
    from library.models import User as CurrentUser

    migrated_library = CurrentLibrary.objects.get(pk=original_ids[0])
    migrated_book = CurrentBook.objects.get(pk=original_ids[2])
    migrated_copy = CurrentCopy.objects.get(pk=original_ids[3])
    migrated_user = CurrentUser.objects.get(pk=original_ids[1])

    assert migrated_library.name == "Biblioteca preservada"
    assert migrated_library.next_number == 2
    assert migrated_book.title == "Livro preservado"
    assert migrated_book.cover_id == "julib/legacy/capa"
    assert migrated_copy.book_id == migrated_book.pk
    assert CurrentLoan.objects.filter(library_id=migrated_library.pk).count() == 1
    membership = CurrentMembership.objects.get(user_id=migrated_user.pk)
    assert membership.library_id == migrated_library.pk
    assert membership.role == CurrentMembership.ROLE_ADMIN
    assert migrated_user.can_create_libraries is False
    assert CurrentMembership.objects.get(user__username="legacy-staff").role == "admin"
    assert CurrentMembership.objects.get(user__username="legacy-member").role == "member"
    assert not CurrentUser.objects.exclude(can_create_libraries=False).exists()
