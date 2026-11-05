from datetime import date

import pytest
from django.core.exceptions import ValidationError

from library import services
from library.circulation import lend, retire_copy, return_loan
from library.models import Library, Loan, Person

pytestmark = pytest.mark.django_db


@pytest.fixture
def setup_loan():
    lib = Library.objects.create(name="Casa")
    book = services.create_book(lib, {"title": "Livro", "authors": ["Autor"]})
    copy = services.add_copy(lib, book.pk)
    person = Person.objects.create(library=lib, name="Ana", phone="47999999999")
    return lib, copy, person


def test_month_end_and_one_open_loan(setup_loan):
    lib, copy, person = setup_loan
    loan = lend(lib, copy.pk, person.pk, date(2024, 1, 31))
    assert loan.due_on == date(2024, 2, 29)
    with pytest.raises(ValidationError):
        lend(lib, copy.pk, person.pk, date(2024, 2, 1))
    return_loan(lib, loan.pk, date(2024, 2, 20))
    loan.refresh_from_db()
    assert loan.state == "returned"
    assert Loan.objects.filter(person=person).count() == 1


def test_loss_preserves_history_and_no_fake_return(setup_loan):
    lib, copy, person = setup_loan
    loan = lend(lib, copy.pk, person.pk, date(2026, 10, 1))
    with pytest.raises(ValidationError):
        retire_copy(lib, copy.pk, "donated")
    retire_copy(lib, copy.pk, "lost")
    loan.refresh_from_db()
    copy.refresh_from_db()
    assert loan.state == "lost" and loan.returned_on is None
    assert copy.state == "lost"
    with pytest.raises(ValidationError):
        lend(lib, copy.pk, person.pk, date.today())


def test_foreign_person_and_invalid_dates(setup_loan):
    lib, copy, person = setup_loan
    other = Library.objects.create(name="Other")
    person.library = other
    person.save()
    with pytest.raises(ValidationError):
        lend(lib, copy.pk, person.pk, date.today())


def test_loan_cover_is_in_list_and_dashboard(client, member, setup_loan):
    from library.models import Membership

    lib, copy, person = setup_loan
    Membership.objects.create(library=lib, user=member)
    copy.book.cover_url = "https://example.com/cover.jpg"
    copy.book.save(update_fields=["cover_url"])
    lend(lib, copy.pk, person.pk, date.today())
    for loan in [
        client.get("/api/v1/loans").json()[0],
        client.get("/api/v1/dashboard").json()["attention"][0],
    ]:
        assert loan["cover_url"] == copy.book.cover_url
        assert loan["attribution_name"] == ""
        assert loan["attribution_url"] == ""
