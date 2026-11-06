from datetime import date

import pytest

from library.models import Book, Copy, Library, Loan, Location, Membership, Person

pytestmark = pytest.mark.django_db


def test_situations_match_the_same_copy_as_location_and_never_duplicate(client, member):
    lib = Library.objects.create(name="Casa")
    Membership.objects.create(library=lib, user=member)
    home = Location.objects.create(library=lib, name="Casa")
    work = Location.objects.create(library=lib, name="Trabalho")
    book = Book.objects.create(library=lib, title="Dois", authors=["Autor"])
    Copy.objects.create(library=lib, book=book, number=1, location=home)
    borrowed = Copy.objects.create(library=lib, book=book, number=2, location=work)
    person = Person.objects.create(library=lib, name="Pessoa", phone="123")
    Loan.objects.create(
        library=lib, copy=borrowed, person=person, started_on=date.today(), due_on=date.today()
    )
    wish = Book.objects.create(library=lib, title="Desejado", authors=["Autor"], is_desired=True)
    lost = Book.objects.create(library=lib, title="Perdido", authors=["Autor"])
    Copy.objects.create(library=lib, book=lost, number=3, state="lost", location=work)

    def ids(query):
        response = client.get("/api/v1/books?" + query)
        assert response.status_code == 200
        return [b["id"] for b in response.json()["items"]]

    assert ids("statuses=available,loaned") == [book.pk]
    assert ids("statuses=available&location_id=" + str(work.pk)) == []
    assert ids("statuses=loaned&location_id=" + str(work.pk)) == [book.pk]
    assert ids("statuses=wishlist,lost") == [lost.pk, wish.pk]
    assert ids("statuses=lost") == [lost.pk]
    assert ids("statuses=wishlist&location_id=" + str(home.pk)) == []


def test_sorting_is_stable_and_missing_values_last(client, member):
    lib = Library.objects.create(name="Casa")
    Membership.objects.create(library=lib, user=member)
    first = Book.objects.create(library=lib, title="Zulu", authors=["Ana"], year="1990")
    second = Book.objects.create(library=lib, title="Alpha", authors=["Zeca"], year="2020")
    third = Book.objects.create(
        library=lib, title="Meio", authors=["Bia"], year="s.d.", is_desired=True
    )
    Copy.objects.create(library=lib, book=first, number=1, acquired_on=date(2024, 1, 1))
    Copy.objects.create(library=lib, book=second, number=2, acquired_on=date(2020, 1, 1))
    Copy.objects.create(library=lib, book=second, number=3, acquired_on=date(2025, 1, 1))

    def ids(order):
        return [
            b["id"]
            for b in client.get(
                "/api/v1/books", {"statuses": "available,wishlist", "order": order}
            ).json()["items"]
        ]

    assert ids("newest") == [third.pk, second.pk, first.pk]
    assert ids("oldest") == [first.pk, second.pk, third.pk]
    assert ids("title_asc") == [second.pk, third.pk, first.pk]
    assert ids("title_desc") == [first.pk, third.pk, second.pk]
    assert ids("author") == [first.pk, third.pk, second.pk]
    assert ids("acquired_desc") == [second.pk, first.pk, third.pk]
    assert ids("acquired_asc") == [first.pk, second.pk, third.pk]
    assert ids("year_desc") == [second.pk, first.pk, third.pk]
    assert ids("year_asc") == [first.pk, second.pk, third.pk]


def test_catalog_filters_do_not_leak_other_libraries_or_include_retired_copies(client, member):
    lib = Library.objects.create(name="Casa")
    other = Library.objects.create(name="Outra")
    Membership.objects.create(library=lib, user=member)
    foreign = Book.objects.create(library=other, title="Privado", authors=["Autor"])
    Copy.objects.create(library=other, book=foreign, number=1)
    retired = Book.objects.create(library=lib, title="Doado", authors=["Autor"])
    Copy.objects.create(library=lib, book=retired, number=1, state="donated")
    for statuses in ["", "available,loaned,wishlist,lost", "lost", "wishlist"]:
        response = client.get("/api/v1/books", {"statuses": statuses})
        assert response.status_code == 200
        assert response.json()["items"] == []
    assert client.get("/api/v1/books", {"statuses": "sold"}).status_code == 400
    assert client.get("/api/v1/books", {"order": "invalid"}).status_code == 422


def test_lost_copy_stays_filterable_after_book_moves_to_wishlist(client, member):
    lib = Library.objects.create(name="Casa")
    Membership.objects.create(library=lib, user=member)
    book = Book.objects.create(library=lib, title="Reposição", authors=["Autor"], is_desired=True)
    Copy.objects.create(library=lib, book=book, number=1, state="lost")
    for status in ["wishlist", "lost", "wishlist,lost"]:
        response = client.get("/api/v1/books", {"statuses": status})
        assert [b["id"] for b in response.json()["items"]] == [book.pk]
