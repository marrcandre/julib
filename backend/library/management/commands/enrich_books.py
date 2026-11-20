import csv
import json
import os
import time
from typing import Any

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from library import providers
from library.metadata import (
    DESCRIPTION_MAX_LENGTH,
    SUBTITLE_MAX_LENGTH,
    normalize_subjects,
    validate_subjects,
)
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
    "subtitle": "subtítulo",
    "description": "descrição",
    "subjects": "assuntos",
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
    | Q(subtitle="")
    | Q(description="")
    | Q(subjects=[])
)


def missing_fields(book: Book) -> set[str]:
    missing = {
        field
        for field in (
            "title",
            "publisher",
            "year",
            "language",
            "edition",
            "subtitle",
            "description",
        )
        if not getattr(book, field).strip()
    }
    if not book.authors:
        missing.add("authors")
    if book.page_count is None:
        missing.add("page_count")
    if not book.cover_url and not book.cover_id:
        missing.add("cover_url")
    if not book.subjects:
        missing.add("subjects")
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
    if field == "subjects":
        try:
            validate_subjects(value)
        except ValidationError:
            return None
        normalized = normalize_subjects(value)
        return normalized or None
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    max_length = {
        "subtitle": SUBTITLE_MAX_LENGTH,
        "description": DESCRIPTION_MAX_LENGTH,
    }.get(field)
    if max_length and len(value) > max_length:
        return None
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
            "subtitle",
            "description",
            "subjects",
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
            "subtitle",
            "description",
            "subjects",
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
        parser.add_argument(
            "--report-format",
            choices=("csv", "json"),
            help="Formato do relatório detalhado opcional.",
        )
        parser.add_argument("--report-file", help="Caminho do arquivo de relatório detalhado.")

    def handle(self, *args, **options):
        if options["limit"] < 1:
            raise CommandError("--limit deve ser maior que zero.")
        if options["delay"] < 0:
            raise CommandError("--delay não pode ser negativo.")
        if bool(options.get("report_format")) != bool(options.get("report_file")):
            raise CommandError("--report-format e --report-file devem ser informados juntos.")
        try:
            library = Library.objects.get(pk=options["library"])
        except Library.DoesNotExist:
            raise CommandError("Biblioteca não encontrada.") from None

        books, skipped = select_books(library, options["limit"])
        mode = "Aplicação" if options["apply"] else "Prévia"
        self.stdout.write(f"{mode}: {len(books)} livros válidos para consulta nesta biblioteca.")
        filled = no_match = field_count = 0
        matched_books = 0
        mismatch_count = 0
        field_stats = {
            field: {"found": 0, "filled": 0, "preserved": 0} for field in ENRICHABLE_FIELDS
        }
        provider_stats: dict[str, dict[str, int]] = {}
        report_details: list[dict[str, Any]] = []

        def provider_stat(name: str) -> dict[str, int]:
            return provider_stats.setdefault(
                name,
                {"queried": 0, "matches": 0, "no_match": 0, "isbn_mismatches": 0, "failures": 0},
            )

        def source_for(enriched: dict[str, Any], field: str) -> str:
            origins = enriched.get("provenance")
            origin = origins.get(field) if isinstance(origins, dict) else None
            return str(origin.get("source") or "") if isinstance(origin, dict) else ""

        def display_value(field: str, value: Any) -> str:
            if field == "description" and isinstance(value, str) and len(value) > 160:
                return value[:160] + "… [prévia resumida]"
            if isinstance(value, list):
                return ", ".join(str(item) for item in value)
            return str(value)

        for index, book in enumerate(books, 1):
            eligible_fields = missing_fields(book)
            lookup = providers.Lookup()
            enriched = providers.enrich_book(candidate_data(book), lookup)
            if normalized_identifier(enriched.get("isbn")) != book.isbn:
                enriched = {**enriched, "_isbn_mismatch": True}
            updates = (
                available_updates(book, enriched, eligible_fields)
                if not enriched.get("_isbn_mismatch")
                else {}
            )
            found_fields = {
                field: source_for(enriched, field)
                for field in eligible_fields
                if not enriched.get("_isbn_mismatch")
                if source_for(enriched, field)
                and usable_value(field, enriched.get(field)) is not None
            }
            if updates:
                matched_books += 1
            matched_sources = set(found_fields.values())
            queried = set(getattr(lookup, "providers_queried", []))
            outcomes = dict(getattr(lookup, "provider_outcomes", {}))
            failures = getattr(lookup, "provider_failures", {})
            mismatches = set(getattr(lookup, "isbn_mismatches", set()))
            if enriched.get("_isbn_mismatch"):
                mismatch_count += 1
            for source in queried:
                stats = provider_stat(source)
                stats["queried"] += 1
                if source in matched_sources or outcomes.get(source) == "match":
                    stats["matches"] += 1
                elif outcomes.get(source) == "isbn_mismatch" or source in mismatches:
                    stats["isbn_mismatches"] += 1
                elif outcomes.get(source) == "no_match":
                    stats["no_match"] += 1
            for source, count in failures.items():
                provider_stat(source)["failures"] += count

            for field in ENRICHABLE_FIELDS:
                if field in updates:
                    field_stats[field]["found"] += 1
                if field in updates:
                    field_count += 1
                elif (
                    field not in eligible_fields
                    and usable_value(field, getattr(book, field)) is not None
                ):
                    field_stats[field]["preserved"] += 1
            persisted: list[str] = []
            if not updates:
                no_match += 1
                state = (
                    "divergência de ISBN; preservado"
                    if enriched.get("_isbn_mismatch")
                    else "sem novos dados seguros"
                )
                self.stdout.write(f"{index}/{len(books)}: {book.title} — {state}.")
            elif options["apply"]:
                persisted = save_missing_fields(book.pk, library, enriched, eligible_fields)
                if persisted:
                    filled += 1
                    for field in persisted:
                        field_stats[field]["filled"] += 1
                    labels = ", ".join(FIELD_LABELS[field] for field in persisted)
                    status = f"preenchidos: {labels}"
                else:
                    status = "campos alterados durante a consulta; preservados"
            else:
                labels = ", ".join(FIELD_LABELS[field] for field in updates)
                status = f"preencheria: {labels}"
            if updates:
                details = "; ".join(
                    f"{FIELD_LABELS[field]} ({source_for(enriched, field)}): {display_value(field, value)}"
                    for field, value in updates.items()
                )
                self.stdout.write(
                    f"{index}/{len(books)}: {book.title} — {status}. Valores: {details}."
                )
            if found_fields:
                found = ", ".join(
                    f"{FIELD_LABELS[field]} ({source})" for field, source in found_fields.items()
                )
                self.stdout.write(f"  Encontrados: {found}.")
            for field in ENRICHABLE_FIELDS:
                existing = field not in eligible_fields
                candidate = field in updates
                provider = source_for(enriched, field) if candidate else ""
                value: Any = None
                if existing:
                    status = "já preenchido"
                    value = getattr(book, field)
                    origin = (
                        (book.provenance or {}).get(field, {})
                        if isinstance(book.provenance, dict)
                        else {}
                    )
                    provider = str(origin.get("source") or "") if isinstance(origin, dict) else ""
                elif candidate and not options["apply"]:
                    status = "seria preenchido"
                    value = updates[field]
                elif candidate and field in persisted:
                    status = "preenchido"
                    value = updates[field]
                elif candidate:
                    status = "erro"
                    provider = source_for(enriched, field)
                elif enriched.get("_isbn_mismatch") or failures:
                    status = "erro"
                    error_providers = sorted(mismatches or failures)
                    provider = ", ".join(error_providers)
                else:
                    status = "não encontrado"
                report_details.append(
                    {
                        "book_id": book.pk,
                        "isbn": book.isbn,
                        "title": book.title,
                        "field": field,
                        "status": status,
                        "value": value,
                        "provider": provider,
                    }
                )
            preserved = [
                FIELD_LABELS[field]
                for field in ENRICHABLE_FIELDS
                if field not in eligible_fields
                and usable_value(field, getattr(book, field)) is not None
            ]
            if preserved:
                self.stdout.write(f"  Preservados: {', '.join(preserved)}.")
            if queried:
                provider_line = ", ".join(
                    f"{source}={outcomes.get(source, 'correspondência' if source in matched_sources else 'consultado')}"
                    for source in sorted(queried)
                )
                self.stdout.write(f"  Provedores: {provider_line}.")
            if mismatches:
                self.stdout.write(f"  ISBN divergente em: {', '.join(sorted(mismatches))}.")
            if failures:
                self.stdout.write(
                    "  Falhas de consulta: "
                    + ", ".join(f"{source} ({count})" for source, count in sorted(failures.items()))
                    + "."
                )
            if options["delay"] > 0 and index < len(books):
                time.sleep(options["delay"])

        if options["apply"]:
            summary = (
                f"Aplicação concluída: {filled} livros atualizados ({sum(item['filled'] for item in field_stats.values())} campos); "
                f"{no_match} sem preenchimento; {skipped} livros ignorados por ISBN inválido ou ausente."
            )
        else:
            self.stdout.write(
                f"Prévia concluída: {field_count} campos disponíveis; {no_match} sem resultado seguro; "
                f"{skipped} livros ignorados por ISBN inválido ou ausente. Use --apply para gravar."
            )
            summary = ""
        if summary:
            self.stdout.write(summary)
        report_summary = {
            "books_analyzed": len(books),
            "books_with_new_metadata": matched_books,
            "books_without_new_metadata": max(0, len(books) - matched_books),
            "invalid_isbn_skipped": skipped,
            "isbn_mismatch_books": mismatch_count,
            "fields_found": {field: values["found"] for field, values in field_stats.items()},
            "fields_filled": {field: values["filled"] for field, values in field_stats.items()},
            "fields_preserved": {
                field: values["preserved"] for field, values in field_stats.items()
            },
            "providers": provider_stats,
        }
        if not options["apply"]:
            report_summary["fields_would_fill"] = report_summary["fields_found"]
        if options.get("report_file"):
            report = {
                "mode": "apply" if options["apply"] else "preview",
                "summary": report_summary,
                "details": report_details,
            }
            try:
                descriptor = os.open(
                    options["report_file"],
                    os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
                    0o600,
                )
                os.chmod(options["report_file"], 0o600)
                with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as report_file:
                    if options["report_format"] == "json":
                        json.dump(report, report_file, ensure_ascii=False, indent=2)
                        report_file.write("\n")
                    else:
                        writer = csv.DictWriter(
                            report_file,
                            fieldnames=(
                                "record_type",
                                "mode",
                                "book_id",
                                "isbn",
                                "title",
                                "field",
                                "status",
                                "value",
                                "provider",
                                "summary",
                            ),
                        )
                        writer.writeheader()
                        writer.writerow(
                            {
                                "record_type": "summary",
                                "mode": report["mode"],
                                "summary": json.dumps(
                                    report_summary, ensure_ascii=False, sort_keys=True
                                ),
                            }
                        )
                        writer.writerows(
                            {
                                "record_type": "detail",
                                "mode": report["mode"],
                                **row,
                                "value": json.dumps(row["value"], ensure_ascii=False)
                                if isinstance(row["value"], list)
                                else row["value"] or "",
                            }
                            for row in report_details
                        )
            except OSError as exc:
                raise CommandError(f"Não foi possível gravar o relatório: {exc}") from None
        self.stdout.write(
            f"Resumo ({mode.lower()}): {len(books)} analisados; {matched_books} com novos metadados; "
            f"{max(0, len(books) - matched_books)} sem novos dados; "
            f"{sum(item['filled'] for item in field_stats.values())} campos gravados."
        )
        self.stdout.write(
            "JSON: "
            + json.dumps(
                {
                    **report_summary,
                    "mode": "apply" if options["apply"] else "preview",
                    "books_with_match": matched_books,
                    "books_without_fill": no_match,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
