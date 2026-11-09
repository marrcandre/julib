import time
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from library import providers
from library.models import Book, Library
from library.providers import normalized_identifier
from library.services import optional_page_count

FIELD_LABELS = {
    "title": "título",
    "authors": "autores",
    "publisher": "editora",
    "year": "ano",
    "language": "idioma",
    "page_count": "páginas",
    "edition": "edição",
    "cover_url": "capa",
}
ENRICHABLE_FIELDS = tuple(FIELD_LABELS)
MISSING_FIELDS_QUERY = (
    Q(title="")
    | Q(authors=[])
    | Q(publisher="")
    | Q(year="")
    | Q(language="")
    | Q(page_count__isnull=True)
    | Q(edition="")
    | Q(cover_url="", cover_id="")
)


def missing_fields(book: Book) -> set[str]:
    missing = {
        field
        for field in ("title", "publisher", "year", "language", "edition")
        if not getattr(book, field).strip()
    }
    if not book.authors:
        missing.add("authors")
    if book.page_count is None:
        missing.add("page_count")
    if not book.cover_url and not book.cover_id:
        missing.add("cover_url")
    return missing


def usable_value(field: str, value: Any) -> Any:
    if field == "page_count":
        return optional_page_count(value)
    if field == "authors":
        if (
            isinstance(value, list)
            and value
            and all(isinstance(a, str) and a.strip() for a in value)
        ):
            return [author.strip() for author in value]
        return None
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    if field == "cover_url" and not value.startswith("https://"):
        return None
    return value


def available_updates(
    book: Book, enriched: dict[str, Any], eligible_fields: set[str]
) -> dict[str, Any]:
    missing = missing_fields(book) & eligible_fields
    return {
        field: value
        for field in ENRICHABLE_FIELDS
        if field in missing
        if (value := usable_value(field, enriched.get(field))) is not None
    }


def save_missing_fields(
    book_id: int, library: Library, enriched: dict[str, Any], eligible_fields: set[str]
) -> list[str]:
    with transaction.atomic():
        try:
            book = Book.objects.select_for_update().get(pk=book_id, library=library)
        except Book.DoesNotExist:
            return []
        updates = available_updates(book, enriched, eligible_fields)
        if not updates:
            return []
        provenance = dict(book.provenance) if isinstance(book.provenance, dict) else {}
        sources = enriched.get("provenance")
        if isinstance(sources, dict):
            for field in updates:
                origin = sources.get(field)
                if isinstance(origin, dict) and isinstance(origin.get("source"), str):
                    provenance[field] = origin
        for field, value in updates.items():
            setattr(book, field, value)
        book.provenance = provenance
        book.save(update_fields=[*updates, "provenance"])
        return list(updates)


def candidate_data(book: Book) -> dict[str, Any]:
    return {
        field: getattr(book, field)
        for field in (
            "title",
            "authors",
            "isbn",
            "publisher",
            "year",
            "language",
            "page_count",
            "edition",
            "cover_url",
            "cover_id",
            "source",
            "source_id",
            "provenance",
        )
    }


def select_books(library: Library, limit: int) -> tuple[list[Book], int]:
    books = []
    skipped = 0
    queryset = (
        Book.objects.filter(library=library)
        .filter(MISSING_FIELDS_QUERY)
        .only(
            "pk",
            "title",
            "authors",
            "isbn",
            "publisher",
            "year",
            "language",
            "page_count",
            "edition",
            "cover_url",
            "cover_id",
            "source",
            "source_id",
            "provenance",
        )
        .order_by("pk")
    )
    for book in queryset.iterator(chunk_size=200):
        if not normalized_identifier(book.isbn):
            skipped += 1
            continue
        books.append(book)
        if len(books) == limit:
            break
    return books, skipped


class Command(BaseCommand):
    help = "Preenche campos bibliográficos ausentes sem substituir dados existentes."

    def add_arguments(self, parser):
        parser.add_argument("--library", type=int, required=True)
        parser.add_argument("--limit", type=int, default=5000)
        parser.add_argument("--delay", type=float, default=1.1)
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Grava os campos ausentes; sem esta opção, apenas mostra uma prévia.",
        )

    def handle(self, *args, **options):
        if options["limit"] < 1:
            raise CommandError("--limit deve ser maior que zero.")
        if options["delay"] < 0:
            raise CommandError("--delay não pode ser negativo.")
        try:
            library = Library.objects.get(pk=options["library"])
        except Library.DoesNotExist:
            raise CommandError("Biblioteca não encontrada.") from None

        books, skipped = select_books(library, options["limit"])
        mode = "Aplicação" if options["apply"] else "Prévia"
        self.stdout.write(f"{mode}: {len(books)} livros válidos para consulta nesta biblioteca.")
        filled = no_match = field_count = 0
        for index, book in enumerate(books, 1):
            eligible_fields = missing_fields(book)
            enriched = providers.enrich_book(candidate_data(book))
            updates = available_updates(book, enriched, eligible_fields)
            if not updates:
                no_match += 1
                self.stdout.write(f"{index}/{len(books)}: {book.title} — sem novos dados seguros.")
            elif options["apply"]:
                saved = save_missing_fields(book.pk, library, enriched, eligible_fields)
                if saved:
                    filled += 1
                    field_count += len(saved)
                    labels = ", ".join(FIELD_LABELS[field] for field in saved)
                    self.stdout.write(
                        f"{index}/{len(books)}: {book.title} — preenchidos: {labels}."
                    )
                else:
                    self.stdout.write(
                        f"{index}/{len(books)}: {book.title} — campos alterados durante a consulta; preservados."
                    )
            else:
                field_count += len(updates)
                labels = ", ".join(FIELD_LABELS[field] for field in updates)
                self.stdout.write(f"{index}/{len(books)}: {book.title} — preencheria: {labels}.")
            if options["delay"] > 0 and index < len(books):
                time.sleep(options["delay"])

        if not options["apply"]:
            self.stdout.write(
                f"Prévia concluída: {field_count} campos disponíveis; {no_match} sem resultado seguro; "
                f"{skipped} livros ignorados por ISBN inválido ou ausente. Use --apply para gravar."
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Concluído: {filled} livros atualizados ({field_count} campos); "
                    f"{no_match} sem resultado seguro; "
                    f"{skipped} livros ignorados por ISBN inválido ou ausente."
                )
            )
