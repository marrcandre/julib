from datetime import date
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Book, Copy, Library, Location, Tag


def optional_page_count(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None
    try:
        count = int(value)
    except (ValueError, TypeError):
        return None
    return count if 1 <= count <= 2147483647 else None


def normalize_isbn(value: str) -> str:
    value = value.replace("-", "").replace(" ", "").strip().upper()
    if not value:
        return ""
    if len(value) == 10 and value[:9].isdigit() and (value[-1].isdigit() or value[-1] == "X"):
        digits = [int(c) if c != "X" else 10 for c in value]
        if sum((10 - i) * d for i, d in enumerate(digits)) % 11 == 0:
            value = "978" + value[:9]
            value += str(
                (-sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(value))) % 10
            )
            return value
    if (
        len(value) == 13
        and value.isdigit()
        and sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(value)) % 10 == 0
    ):
        return value
    raise ValidationError("ISBN inválido. Confira o código ou deixe em branco.")


def owned(model: Any, library: Library, pk: int, *, lock: bool = False) -> Any:
    qs = model.objects.filter(library=library)
    if lock:
        qs = qs.select_for_update()
    try:
        return qs.get(pk=pk)
    except model.DoesNotExist:
        raise ValidationError("Registro não encontrado nesta biblioteca.") from None


@transaction.atomic
def create_book(library: Library, data: dict[str, Any], book_id: int | None = None) -> Book:
    data = data.copy()
    if data.get("provenance") is None:
        data.pop("provenance", None)
    if not set(data.get("provenance", {})) <= {
        "title",
        "authors",
        "publisher",
        "year",
        "language",
        "page_count",
        "edition",
        "cover_url",
    }:
        raise ValidationError("Origem de dados inválida.")
    tags = data.pop("tag_ids", None)
    if (
        not data.get("title", "").strip()
        or not data.get("authors")
        or not all(str(a).strip() for a in data["authors"])
    ):
        raise ValidationError("Informe título e autor.")
    data["isbn"] = normalize_isbn(data.get("isbn", ""))
    if (
        Book.objects.filter(library=library, isbn=data["isbn"]).exclude(pk=book_id or 0).exists()
        and data["isbn"]
    ):
        raise ValidationError(
            "Este ISBN já está cadastrado. Adicione um exemplar ao livro existente."
        )
    if data.get("cover_url") and not data["cover_url"].startswith("https://"):
        raise ValidationError("A capa deve usar HTTPS.")
    book = owned(Book, library, book_id, lock=True) if book_id else Book(library=library)
    for key, value in data.items():
        setattr(book, key, value)
    tag_objs = [owned(Tag, library, pk) for pk in tags] if tags is not None else None
    book.full_clean()
    book.save()
    if tag_objs is not None:
        book.tags.set(tag_objs)
    return book


def edit_book(library: Library, book_id: int, data: dict[str, Any]) -> Book:
    from .media import verify_upload

    owned(Book, library, book_id)
    data = data.copy()
    public_id = data.pop("cover_public_id", None)
    # Provider reads happen before acquiring a database lock. The verified attachment
    # and every bibliographic change are then committed together or not at all.
    verified = verify_upload(library, public_id) if public_id else None
    with transaction.atomic():
        import copy

        book = owned(Book, library, book_id, lock=True)
        origins = copy.deepcopy(book.provenance)
        for field in ("title", "authors", "publisher", "year", "language", "page_count", "edition"):
            if field in data and data[field] != getattr(book, field):
                origins.pop(field, None)
        if not data.get("source"):
            data["source"], data["source_id"] = book.source, book.source_id
        if verified:
            data.update(verified)
            origins["cover_url"] = {"source": "manual", "source_id": "", "url": data["cover_url"]}
        elif data.get("cover_url", "") != book.cover_url:
            data["cover_id"] = ""
            origins["cover_url"] = {
                "source": "manual",
                "source_id": "",
                "url": data.get("cover_url", ""),
            }
        data["provenance"] = origins
        return create_book(library, data, book_id)


@transaction.atomic
def add_copy(
    library: Library, book_id: int, location_id: int | None = None, acquired_on: date | None = None
) -> Copy:
    library = Library.objects.select_for_update().get(pk=library.pk)
    book = owned(Book, library, book_id, lock=True)
    if book.is_desired:
        book.is_desired = False
        book.save(update_fields=["is_desired"])
    location = owned(Location, library, location_id) if location_id else None
    copy = Copy.objects.create(
        library=library,
        book=book,
        number=library.next_number,
        location=location,
        **({"acquired_on": acquired_on} if acquired_on else {}),
    )
    library.next_number += 1
    library.save(update_fields=["next_number"])
    return copy


@transaction.atomic
def save_location(library: Library, data: dict[str, Any], pk: int | None = None) -> Location:
    Library.objects.select_for_update().get(pk=library.pk)
    location = owned(Location, library, pk) if pk else Location(library=library)
    parent = owned(Location, library, data["parent_id"]) if data.get("parent_id") else None
    ancestor = parent
    while ancestor:
        if ancestor.pk == location.pk:
            raise ValidationError("Um local não pode conter a si mesmo.")
        ancestor = ancestor.parent
    location.name = data["name"].strip()
    location.parent = parent
    location.full_clean()
    location.save()
    return location


@transaction.atomic
def locate_copies(library: Library, copy_ids: list[int], location_id: int | None) -> int:
    location = owned(Location, library, location_id) if location_id else None
    copies = [owned(Copy, library, pk, lock=True) for pk in sorted(set(copy_ids))]
    for copy in copies:
        copy.location = location
        copy.save(update_fields=["location"])
    return len(copies)


@transaction.atomic
def register_copy(library: Library, data: dict[str, Any]) -> dict[str, int | None]:
    """One confirmed intent creates at most one edition/copy, even after a lost response."""
    import hashlib
    import json

    from .models import Registration

    Library.objects.select_for_update().get(pk=library.pk)
    canonical = data.copy()
    if isinstance(canonical.get("book"), dict) and not canonical["book"].get("provenance"):
        canonical["book"] = {k: v for k, v in canonical["book"].items() if k != "provenance"}
    target = canonical.pop("target", "collection")
    if target not in {"collection", "wishlist"}:
        raise ValidationError("Destino inválido.")
    if target != "collection":
        canonical["target"] = target
    fingerprint = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, default=str).encode()
    ).hexdigest()
    receipt = Registration.objects.filter(library=library, key=data["key"]).first()
    if receipt:
        if receipt.fingerprint != fingerprint:
            raise ValidationError(
                "Esta operação já foi concluída com outros dados. Abra um novo cadastro."
            )
        if receipt.book_id is None or (target == "collection" and receipt.copy_id is None):
            raise ValidationError("Este cadastro foi excluído ou movido. Abra um novo cadastro.")
        return {
            "book_id": receipt.book_id,
            "copy_id": receipt.copy_id,
            "number": receipt.copy.number if receipt.copy else None,
        }
    book = (
        owned(Book, library, data["existing_book_id"])
        if data.get("existing_book_id")
        else create_book(library, data["book"])
    )
    if target == "wishlist":
        if book.copies.filter(state="active").exists():
            raise ValidationError("Este livro está no acervo. Use a ação Mover para desejados.")
        book.is_desired = True
        book.save(update_fields=["is_desired"])
        copy = None
    else:
        copy = add_copy(library, book.pk, data.get("location_id"), data.get("acquired_on"))
    Registration.objects.create(
        library=library, key=data["key"], fingerprint=fingerprint, book=book, copy=copy
    )
    return {
        "book_id": book.pk,
        "copy_id": copy.pk if copy else None,
        "number": copy.number if copy else None,
    }


@transaction.atomic
def delete_book(library: Library, book_id: int) -> None:
    """Serialize with acquisition, reclassification and lending; preserve all loan history."""
    Library.objects.select_for_update().get(pk=library.pk)
    book = owned(Book, library, book_id, lock=True)
    copies = list(book.copies.select_for_update().order_by("pk"))
    if any(copy.loans.exists() for copy in copies):
        raise ValidationError("Não é possível excluir: este livro possui histórico de empréstimos.")
    book.copies.all().delete()
    book.delete()


@transaction.atomic
def move_to_wishlist(library: Library, book_id: int) -> Book:
    Library.objects.select_for_update().get(pk=library.pk)
    book = owned(Book, library, book_id, lock=True)
    copies = list(book.copies.select_for_update().filter(state="active").order_by("pk"))
    if any(copy.loans.exists() for copy in copies):
        raise ValidationError(
            "Exemplar com histórico de empréstimos: registre a baixa antes de mover para desejados."
        )
    book.copies.filter(pk__in=[copy.pk for copy in copies]).delete()
    book.is_desired = True
    book.save(update_fields=["is_desired"])
    return book
