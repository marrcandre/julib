from datetime import date
from typing import Any
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import Book, Copy, Library, Location, Tag


def normalize_isbn(value: str) -> str:
    value = value.replace('-', '').replace(' ', '').strip().upper()
    if not value:
        return ''
    if len(value) == 10 and value[:9].isdigit() and (value[-1].isdigit() or value[-1] == 'X'):
        digits = [int(c) if c != 'X' else 10 for c in value]
        if sum((10-i)*d for i,d in enumerate(digits)) % 11 == 0:
            value = '978' + value[:9]
            value += str((-sum(int(c)*(1 if i%2 == 0 else 3) for i,c in enumerate(value)))%10)
            return value
    if len(value) == 13 and value.isdigit() and sum(int(c)*(1 if i%2 == 0 else 3) for i,c in enumerate(value))%10 == 0:
        return value
    raise ValidationError('ISBN inválido. Confira o código ou deixe em branco.')


def owned(model: Any, library: Library, pk: int, *, lock: bool = False) -> Any:
    qs = model.objects.filter(library=library)
    if lock:
        qs = qs.select_for_update()
    try:
        return qs.get(pk=pk)
    except model.DoesNotExist:
        raise ValidationError('Registro não encontrado nesta biblioteca.') from None


@transaction.atomic
def create_book(library: Library, data: dict[str, Any], book_id: int | None = None) -> Book:
    data = data.copy()
    tags = data.pop('tag_ids', None)
    if not data.get('title', '').strip() or not data.get('authors') or not all(str(a).strip() for a in data['authors']):
        raise ValidationError('Informe título e autor.')
    data['isbn'] = normalize_isbn(data.get('isbn',''))
    if Book.objects.filter(library=library, isbn=data['isbn']).exclude(pk=book_id).exists() and data['isbn']:
        raise ValidationError('Este ISBN já está cadastrado. Adicione um exemplar ao livro existente.')
    if data.get('cover_url') and not data['cover_url'].startswith('https://'):
        raise ValidationError('A capa deve usar HTTPS.')
    book = owned(Book, library, book_id, lock=True) if book_id else Book(library=library)
    for key, value in data.items():
        setattr(book, key, value)
    tag_objs = [owned(Tag, library, pk) for pk in tags] if tags is not None else None
    book.full_clean(); book.save()
    if tag_objs is not None:
        book.tags.set(tag_objs)
    return book


@transaction.atomic
def add_copy(library: Library, book_id: int, location_id: int | None = None, acquired_on: date | None = None) -> Copy:
    library = Library.objects.select_for_update().get(pk=library.pk)
    book = owned(Book, library, book_id)
    location = owned(Location, library, location_id) if location_id else None
    copy = Copy.objects.create(library=library, book=book, number=library.next_number, location=location, **({'acquired_on': acquired_on} if acquired_on else {}))
    library.next_number += 1; library.save(update_fields=['next_number'])
    return copy


@transaction.atomic
def save_location(library: Library, data: dict[str, Any], pk: int | None = None) -> Location:
    Library.objects.select_for_update().get(pk=library.pk)
    location = owned(Location, library, pk) if pk else Location(library=library)
    parent = owned(Location, library, data['parent_id']) if data.get('parent_id') else None
    ancestor = parent
    while ancestor:
        if ancestor.pk == location.pk:
            raise ValidationError('Um local não pode conter a si mesmo.')
        ancestor = ancestor.parent
    location.name = data['name'].strip(); location.parent = parent
    location.full_clean(); location.save()
    return location


@transaction.atomic
def locate_copies(library: Library, copy_ids: list[int], location_id: int | None) -> int:
    location = owned(Location, library, location_id) if location_id else None
    copies = [owned(Copy, library, pk, lock=True) for pk in sorted(set(copy_ids))]
    for copy in copies:
        copy.location = location; copy.save(update_fields=['location'])
    return len(copies)
