from datetime import date

import pytest

from library import services
from library.models import Library, Membership

pytestmark = pytest.mark.django_db


def test_copy_acquisition_can_be_corrected_after_import(client, member):
    lib = Library.objects.create(name="Casa")
    Membership.objects.create(user=member, library=lib)
    book = services.create_book(lib, {"title": "Antigo", "authors": ["Autor"]})
    copy = services.add_copy(lib, book.pk)
    result = client.put(
        f"/api/v1/copies/{copy.pk}",
        {"location_id": None, "acquired_on": "2010-01-05"},
        content_type="application/json",
    )
    assert result.status_code == 200
    copy.refresh_from_db()
    assert copy.acquired_on == date(2010, 1, 5)
