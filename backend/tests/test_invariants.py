from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import Client

from library import services
from library.circulation import lend
from library.models import (
    Copy,
    ImportRow,
    ImportSession,
    Library,
    Loan,
    Location,
    Membership,
    Person,
    Tag,
    User,
)


@pytest.mark.django_db(transaction=True)
def test_simultaneous_loans_only_one_open():
    lib = Library.objects.create(name="Casa")
    book = services.create_book(lib, {"title": "Livro", "authors": ["Autor"]})
    copy = services.add_copy(lib, book.pk)
    person = Person.objects.create(library=lib, name="Ana", phone="123")

    def attempt():
        close_old_connections()
        try:
            lend(lib, copy.pk, person.pk, date.today())
            return True
        except ValidationError:
            return False
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: attempt(), range(2))) == [False, True]
    assert Loan.objects.filter(state="open").count() == 1


@pytest.mark.django_db
def test_foreign_relations_and_share_never_leak(client, member):
    lib = Library.objects.create(name="Casa")
    Membership.objects.create(user=member, library=lib)
    other = Library.objects.create(name="Segredo")
    loc = Location.objects.create(library=other, name="Cofre")
    result = client.post(
        "/api/v1/locations", {"name": "Novo", "parent_id": loc.pk}, content_type="application/json"
    )
    assert result.status_code == 400
    assert result.headers["Cache-Control"] == "no-store, private"
    assert (
        client.post(
            "/api/v1/people", {"name": "Ana", "phone": "  "}, content_type="application/json"
        ).status_code
        == 400
    )


@pytest.mark.django_db
def test_oauth_adapter_requires_verified_google_email():
    from types import SimpleNamespace

    from allauth.core.exceptions import ImmediateHttpResponse

    from library.auth import GoogleAdapter

    adapter = GoogleAdapter()
    login = SimpleNamespace(
        account=SimpleNamespace(provider="google"),
        user=User(email="ju@example.com"),
        email_addresses=[SimpleNamespace(email="ju@example.com", verified=False)],
    )
    with pytest.raises(ImmediateHttpResponse):
        adapter.pre_social_login(None, login)
    login.email_addresses[0].verified = True
    adapter.pre_social_login(None, login)


@pytest.mark.django_db
def test_database_rejects_copy_and_loan_relations_across_libraries():
    from library import services

    own = Library.objects.create(name="Pessoal")
    other = Library.objects.create(name="Família")
    own_book = services.create_book(own, {"title": "Meu livro", "authors": ["Autora"]})
    other_book = services.create_book(other, {"title": "Outro livro", "authors": ["Autor"]})
    foreign_copy = services.add_copy(other, other_book.pk)
    person = Person.objects.create(library=own, name="Ana", phone="123")

    with pytest.raises(IntegrityError), transaction.atomic():
        Copy.objects.create(library=own, book=other_book, number=own.next_number)
        with connection.cursor() as cursor:
            cursor.execute('SET CONSTRAINTS "copy_book_library_fk" IMMEDIATE')
    with pytest.raises(IntegrityError), transaction.atomic():
        Loan.objects.create(
            library=own,
            copy=foreign_copy,
            person=person,
            started_on=date(2026, 1, 1),
            due_on=date(2026, 2, 1),
        )
        with connection.cursor() as cursor:
            cursor.execute('SET CONSTRAINTS "loan_copy_library_fk" IMMEDIATE')
    assert not Copy.objects.filter(library=own, book=own_book).exists()


@pytest.mark.django_db
def test_database_rejects_tags_from_another_library():
    own = Library.objects.create(name="Pessoal")
    other = Library.objects.create(name="Família")
    book = services.create_book(own, {"title": "Meu livro", "authors": ["Autora"]})
    tag = Tag.objects.create(library=other, name="Privado")

    with pytest.raises(IntegrityError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                'INSERT INTO "library_book_tags" ("book_id", "tag_id") VALUES (%s, %s)',
                [book.pk, tag.pk],
            )
    own_tag = Tag.objects.create(library=own, name="Pessoal")
    book.tags.add(own_tag)
    with pytest.raises(IntegrityError), transaction.atomic():
        Tag.objects.filter(pk=own_tag.pk).update(library=other)


@pytest.mark.django_db
def test_database_rejects_import_row_copy_from_another_library():
    own = Library.objects.create(name="Pessoal")
    other = Library.objects.create(name="Família")
    session = ImportSession.objects.create(library=own)
    foreign_book = services.create_book(other, {"title": "Outro", "authors": ["Autor"]})
    foreign_copy = services.add_copy(other, foreign_book.pk)

    with pytest.raises(IntegrityError), transaction.atomic():
        ImportRow.objects.create(
            session=session, position=1, data={}, copy=foreign_copy, result="created"
        )
    own_book = services.create_book(own, {"title": "Meu", "authors": ["Autora"]})
    own_copy = services.add_copy(own, own_book.pk)
    ImportRow.objects.create(session=session, position=2, data={}, copy=own_copy, result="created")
    with pytest.raises(IntegrityError), transaction.atomic():
        ImportSession.objects.filter(pk=session.pk).update(library=other)


@pytest.mark.django_db
def test_authenticated_write_needs_csrf(member):
    client = Client(enforce_csrf_checks=True)
    client.force_login(member)
    assert (
        client.post(
            "/api/v1/locations", {"name": "Casa"}, content_type="application/json"
        ).status_code
        == 403
    )
