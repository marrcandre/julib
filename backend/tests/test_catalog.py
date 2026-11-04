from datetime import date
import pytest
from django.core.exceptions import ValidationError
from library.models import Library, Membership, Book, Copy, Location, Tag
from library import services
pytestmark = pytest.mark.django_db

def test_catalog_isolation_isbn_and_copy_number(client, member):
    lib = Library.objects.create(name='Nossa biblioteca')
    Membership.objects.create(user=member, library=lib)
    data = {'title': 'O Hobbit', 'authors': ['Tolkien'], 'isbn': '0-261-10221-4'}
    book = services.create_book(lib, data)
    assert book.isbn == '9780261102217'
    with pytest.raises(ValidationError):
        services.create_book(lib, {**data, 'isbn': '9780261102217'})
    a = services.add_copy(lib, book.pk)
    b = services.add_copy(lib, book.pk)
    assert (a.number, b.number) == (1, 2)
    assert a.acquired_on == date.today()
    foreign = Library.objects.create(name='Outra')
    foreign_book = services.create_book(foreign, {'title': 'Privado', 'authors': ['Outro']})
    assert client.get(f'/api/v1/books/{foreign_book.pk}').status_code == 404
    assert len(client.get('/api/v1/books').json()['items']) == 1

def test_locations_cycles_and_atomic_bulk():
    lib = Library.objects.create(name='Casa')
    other = Library.objects.create(name='Outra')
    root = Location.objects.create(library=lib, name='Casa')
    child = Location.objects.create(library=lib, name='Estante', parent=root)
    with pytest.raises(ValidationError):
        services.save_location(lib, {'name': 'Casa', 'parent_id': child.pk}, root.pk)
    book = services.create_book(lib, {'title': 'Livro', 'authors': ['Autor']})
    copy = services.add_copy(lib, book.pk)
    outsider = Location.objects.create(library=other, name='Segredo')
    with pytest.raises(ValidationError):
        services.locate_copies(lib, [copy.pk], outsider.pk)
    copy.refresh_from_db()
    assert copy.location_id is None
    services.locate_copies(lib, [copy.pk], child.pk)
    copy.refresh_from_db()
    assert copy.location_id == child.pk

def test_tag_filter_and_required_fields(client, member):
    lib = Library.objects.create(name='Casa')
    Membership.objects.create(user=member, library=lib)
    tag = Tag.objects.create(library=lib, name='História')
    book = services.create_book(lib, {'title': 'História do Brasil', 'authors': ['Autor'], 'tag_ids': [tag.pk]})
    services.add_copy(lib, book.pk)
    assert client.get(f'/api/v1/books?tag_id={tag.pk}').json()['total'] == 1
    assert client.post('/api/v1/books', data={'title': '', 'authors': []}, content_type='application/json').status_code in (400, 422)
