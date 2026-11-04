import pytest
from django.core.exceptions import ValidationError
from django.test import override_settings
from library.models import Library, Membership, Book, Copy
from library import services
from library.imports import preview_csv, process_rows
from library.sharing import renew_link, public_books
from library.providers import search_books

pytestmark = pytest.mark.django_db
CSV = b'Book Id,Title,Author,ISBN,ISBN13\n1,The Hobbit,Tolkien,,="9780261102217"\n2,Another,Author,,\n'

def test_import_selected_and_idempotent():
    lib = Library.objects.create(name='Casa')
    session = preview_csv(lib, CSV)
    rows = list(session.rows.all())
    process_rows(lib, session.pk, [{'id': rows[0].pk, 'action':'import'}])
    process_rows(lib, session.pk, [{'id': rows[0].pk, 'action':'import'}])
    assert Book.objects.count() == Copy.objects.count() == 1
    assert Book.objects.first().isbn == '9780261102217'
    again = preview_csv(lib, CSV)
    row = again.rows.first()
    process_rows(lib, again.pk, [{'id':row.pk, 'action':'import'}])
    assert Copy.objects.count() == 1
    final = preview_csv(lib, CSV)
    process_rows(lib, final.pk, [{'id':final.rows.first().pk, 'action':'copy'}])
    assert Copy.objects.count() == 2
    with pytest.raises(ValidationError): preview_csv(lib, b'bad,csv\nx,y')

def test_share_revocation_and_privacy():
    lib = Library.objects.create(name='Casa')
    book = services.create_book(lib, {'title':'Public title','authors':['Autor']})
    services.add_copy(lib, book.pk)
    token = renew_link(lib)
    data = public_books(token)
    assert data['items'][0]['available'] is True
    assert 'copies' not in data['items'][0] and 'source_id' not in data['items'][0]
    renew_link(lib)
    with pytest.raises(ValidationError): public_books(token)

def test_provider_timeout_is_honest(monkeypatch):
    import httpx
    def timeout(*args, **kwargs): raise httpx.ReadTimeout('slow')
    monkeypatch.setattr(httpx, 'get', timeout)
    with pytest.raises(ValidationError): search_books('O Hobbit')
