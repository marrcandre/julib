"""Libib CSV parsing and import lifecycle, kept separate from Goodreads."""

import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass
from datetime import timedelta
from pathlib import PurePosixPath
from typing import Any, Sequence

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import (
    Book,
    ImportFile,
    ImportReceipt,
    ImportReceiptCopy,
    ImportRow,
    ImportSession,
    Library,
    Tag,
)
from .services import add_copy, create_book, normalize_isbn, owned

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_TOTAL_BYTES = 25 * 1024 * 1024
MAX_FILES = 5
MAX_ROWS_PER_FILE = 5_000
MAX_ROWS_PER_SESSION = 25_000
MAX_COPIES = 100
SESSION_RETENTION = timedelta(days=7)

REQUIRED_COLUMNS = {
    "item_type",
    "title",
    "creators",
    "collection",
    "ean_isbn13",
    "upc_isbn10",
    "tags",
    "length",
    "copies",
}
IGNORED_COLUMNS = {
    "id",
    "description",
    "notes",
    "price",
    "rating",
    "review",
    "review_date",
    "status",
    "began",
    "completed",
    "added",
    "group",
    "first_name",
    "last_name",
    "number_of_discs",
    "number_of_players",
    "age_group",
    "ensemble",
    "aspect_ratio",
    "esrb",
}


@dataclass
class ParsedFile:
    name: str
    collection: str
    sha256: str
    unknown_columns: list[str]
    rows: list[dict[str, Any]]
    errors: list[str]


@dataclass
class ParsedImport:
    files: list[ParsedFile]


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _page_count(value: str) -> int | None:
    if not value or not re.fullmatch(r"\d+", value):
        return None
    count = int(value)
    return count if 1 <= count <= 2_147_483_647 else None


def _year(value: str) -> str:
    match = re.search(r"(?<!\d)(\d{4})(?!\d)", value)
    return match.group(1) if match else ""


def _isbn(row: dict[str, str], warnings: list[str]) -> str:
    for column in ("ean_isbn13", "upc_isbn10"):
        candidate = _text(row.get(column))
        if not candidate:
            continue
        try:
            return normalize_isbn(candidate)
        except ValidationError:
            continue
    if _text(row.get("ean_isbn13")) or _text(row.get("upc_isbn10")):
        warnings.append("Os códigos ISBN informados são inválidos; o livro ficará sem ISBN.")
    else:
        warnings.append("Livro sem ISBN confiável; não haverá correspondência automática.")
    return ""


def _normalize_row(row: dict[str, str], unknown_columns: list[str]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    item_type = _text(row.get("item_type")).casefold()
    title = _text(row.get("title"))
    creator = _text(row.get("creators"))
    creators = [creator] if creator else []
    if ";" in creator:
        creators = [part.strip() for part in creator.split(";") if part.strip()]
    elif "," in creator:
        parts = [part.strip() for part in creator.split(",")]
        if len(parts) > 1 and all(len(part.split()) >= 2 for part in parts):
            creators = parts
        else:
            warnings.append(
                "O campo de criadores contém vírgulas ambíguas e foi preservado como um nome."
            )
    if not title:
        errors.append("Título ausente.")
    if not creator:
        errors.append("Autor ou criador ausente.")

    raw_copies = _text(row.get("copies"))
    copies = 0
    if re.fullmatch(r"[1-9]\d*", raw_copies):
        copies = int(raw_copies)
    if not copies or copies > MAX_COPIES:
        errors.append(f"Quantidade de exemplares deve ser um inteiro entre 1 e {MAX_COPIES}.")

    raw_year = _text(row.get("publish_date"))
    year = _year(raw_year)
    if raw_year:
        warnings.append("A data de publicação será reduzida ao ano.")
        if not year:
            warnings.append("Não foi possível identificar o ano da publicação.")

    raw_pages = _text(row.get("length"))
    page_count = _page_count(raw_pages)
    if raw_pages and page_count is None:
        warnings.append("Número de páginas inválido; esse campo será ignorado.")

    raw_tags = _text(row.get("tags"))
    tag_names = [tag.strip()[:60] for tag in raw_tags.split(",") if tag.strip()]
    ignored = sorted(
        name for name in (IGNORED_COLUMNS | set(unknown_columns)) if _text(row.get(name))
    )
    isbn = _isbn(row, warnings)
    normalized = {
        "title": title[:300],
        "authors": creators,
        "isbn": isbn,
        "publisher": _text(row.get("publisher"))[:200],
        "year": year,
        "page_count": page_count,
        "tag_names": tag_names,
        "copies": copies,
        "collection": _text(row.get("collection"))[:150],
        "not_imported_fields": ignored,
        "source_fields": row,
    }
    if item_type != "book":
        status = "incompatible"
        errors = [f"Tipo de mídia incompatível: {item_type or 'não informado'}. "]
    else:
        status = "invalid" if errors else "valid"
    return {"data": normalized, "status": status, "errors": errors, "warnings": warnings}


def parse_libib_files(
    files: Sequence[tuple[str, bytes] | tuple[str, bytes, str, str]],
) -> ParsedImport:
    if not files or len(files) > MAX_FILES:
        raise ValidationError(f"Selecione de 1 a {MAX_FILES} arquivos CSV.")
    total_size = sum(len(item[1]) for item in files)
    if total_size > MAX_TOTAL_BYTES:
        raise ValidationError("O tamanho total dos arquivos excede 25 MiB.")

    parsed_files: list[ParsedFile] = []
    total_rows = 0
    for upload in files:
        name, content = upload[0], upload[1]
        upload_error = upload[2] if len(upload) > 2 else ""
        uploaded_sha256 = upload[3] if len(upload) > 3 else ""
        digest = uploaded_sha256 or hashlib.sha256(content).hexdigest()
        errors: list[str] = [upload_error] if upload_error else []
        unknown: list[str] = []
        rows: list[dict[str, Any]] = []
        first_collection = ""
        if len(content) > MAX_FILE_BYTES and not errors:
            errors.append("Cada arquivo deve ter até 5 MiB.")
        try:
            if not errors:
                text = content.decode("utf-8-sig")
                reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
                headers = [header.strip() if header else "" for header in (reader.fieldnames or [])]
                if (
                    not headers
                    or len(headers) != len(set(headers))
                    or not REQUIRED_COLUMNS.issubset(headers)
                ):
                    raise ValidationError("Cabeçalho Libib inválido ou incompleto.")
                reader.fieldnames = headers
                unknown = sorted(
                    set(headers)
                    - REQUIRED_COLUMNS
                    - IGNORED_COLUMNS
                    - {
                        "id",
                        "first_name",
                        "last_name",
                        "ean_isbn13",
                        "upc_isbn10",
                        "publisher",
                        "publish_date",
                        "length",
                        "tags",
                        "copies",
                        "collection",
                        "creators",
                        "item_type",
                        "title",
                    }
                )
                for raw in reader:
                    if raw is None or None in raw or any(value is None for value in raw.values()):
                        raise ValidationError(
                            "CSV malformado: uma linha tem quantidade incorreta de colunas."
                        )
                    if len(rows) >= MAX_ROWS_PER_FILE:
                        raise ValidationError("Cada arquivo pode conter até 5.000 registros.")
                    source_row = {
                        key: _text(value) for key, value in raw.items() if key is not None
                    }
                    if not first_collection:
                        first_collection = _text(source_row.get("collection"))
                    rows.append(_normalize_row(source_row, unknown))
                if not rows:
                    raise ValidationError("O arquivo não contém registros.")
        except UnicodeDecodeError:
            errors.append("Arquivo inválido. Exporte o CSV em UTF-8.")
        except csv.Error:
            errors.append("CSV malformado. Confira o arquivo exportado pelo Libib.")
        except ValidationError as exc:
            errors.extend(exc.messages)
        if not errors:
            total_rows += len(rows)
            if total_rows > MAX_ROWS_PER_SESSION:
                errors.append("A sessão pode conter até 25.000 registros.")
        if errors:
            rows = []
        parsed_files.append(
            ParsedFile(
                name=name[:255],
                collection=first_collection,
                sha256=digest,
                unknown_columns=unknown,
                rows=rows,
                errors=errors,
            )
        )
    seen_hashes: set[str] = set()
    for item in parsed_files:
        if item.sha256 in seen_hashes:
            item.errors.append("O mesmo arquivo foi selecionado mais de uma vez.")
            item.rows = []
        seen_hashes.add(item.sha256)
    return ParsedImport(files=parsed_files)


@transaction.atomic
def preview_libib(
    library: Library, files: Sequence[tuple[str, bytes] | tuple[str, bytes, str, str]]
) -> ImportSession:
    parsed = parse_libib_files(files)
    session = ImportSession.objects.create(library=library, source=ImportSession.SOURCE_LIBIB)
    position = 0
    for file_position, parsed_file in enumerate(parsed.files, 1):
        clean_name = PurePosixPath(parsed_file.name.replace("\\", "/")).name or "arquivo.csv"
        import_file = ImportFile.objects.create(
            session=session,
            position=file_position,
            original_name=clean_name[:255],
            collection=parsed_file.collection,
            sha256=parsed_file.sha256,
            status="error" if parsed_file.errors else "ready",
            error=" ".join(parsed_file.errors)[:300],
            unknown_columns=parsed_file.unknown_columns,
            total_rows=len(parsed_file.rows),
        )
        rows_to_create = []
        fingerprint_occurrences: dict[str, int] = {}
        for file_row_number, item in enumerate(parsed_file.rows, 1):
            position += 1
            raw = item["data"]["source_fields"]
            identity_fields = {key: value for key, value in raw.items() if key != "id"}
            fingerprint = hashlib.sha256(
                json.dumps(
                    identity_fields, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
            ).hexdigest()
            occurrence = fingerprint_occurrences.get(fingerprint, 0) + 1
            fingerprint_occurrences[fingerprint] = occurrence
            source_key = hashlib.sha256(
                f"libib-v1:{fingerprint}:{occurrence}".encode("ascii")
            ).hexdigest()
            item["data"]["file_sha256"] = parsed_file.sha256
            item["data"]["file_row_number"] = file_row_number
            item["data"]["row_fingerprint"] = fingerprint
            item["data"]["source_key"] = source_key
            rows_to_create.append(
                ImportRow(
                    session=session,
                    import_file=import_file,
                    position=position,
                    file_row_number=file_row_number,
                    source_key=source_key,
                    row_fingerprint=fingerprint,
                    data=item,
                )
            )
        ImportRow.objects.bulk_create(rows_to_create, batch_size=500)
    return session


def libib_matching(library: Library, row: ImportRow) -> Book | None:
    isbn = row.data.get("data", {}).get("isbn", "")
    if not isbn:
        return None
    return Book.objects.filter(library=library, isbn=isbn).first()


def libib_details(library: Library, session_id: int) -> dict[str, Any]:
    session = owned(ImportSession, library, session_id)
    if session.source != ImportSession.SOURCE_LIBIB:
        raise ValidationError("Sessão de importação Libib não encontrada.")
    if session.created_at < timezone.now() - SESSION_RETENTION:
        raise ValidationError("Importação expirada. Envie os arquivos novamente.")
    rows = list(session.rows.select_related("import_file").order_by("position"))
    files = list(session.files.order_by("position"))
    file_data = [
        {
            "id": item.pk,
            "name": item.original_name,
            "collection": item.collection,
            "sha256": item.sha256,
            "status": item.status,
            "error": item.error,
            "total_rows": item.total_rows,
            "unknown_columns": item.unknown_columns,
            "completed": sum(bool(row.result) for row in rows if row.import_file_id == item.pk),
        }
        for item in files
    ]
    duplicate_groups: dict[str, list[int]] = {}
    source_keys = [row.source_key for row in rows if row.source_key]
    receipts = {
        receipt.source_key: receipt
        for receipt in ImportReceipt.objects.filter(library=library, source_key__in=source_keys)
    }
    isbns = {row.data["data"].get("isbn") for row in rows if row.data["data"].get("isbn")}
    existing_books = {
        book.isbn: book
        for book in Book.objects.filter(library=library, isbn__in=isbns).only(
            "id", "isbn", "title", "authors", "publisher", "year"
        )
    }
    candidate_titles = sorted(
        {row.data["data"].get("title", "") for row in rows if row.data["status"] == "valid"}
    )
    existing_metadata: set[tuple[str, str, str, str]] = set()
    for start in range(0, len(candidate_titles), 500):
        for book in Book.objects.filter(
            library=library, title__in=candidate_titles[start : start + 500]
        ).only("title", "authors", "publisher", "year"):
            signature = (
                book.title.casefold().strip(),
                "|".join(author.casefold().strip() for author in book.authors),
                book.publisher.casefold().strip(),
                book.year.casefold().strip(),
            )
            existing_metadata.add(signature)
    duplicate_ids: set[int] = set()
    for row in rows:
        data = row.data["data"]
        if row.data["status"] != "valid":
            continue
        if (
            not data.get("isbn")
            and (
                data["title"].casefold().strip(),
                "|".join(author.casefold().strip() for author in data["authors"]),
                data["publisher"].casefold().strip(),
                data["year"].casefold().strip(),
            )
            in existing_metadata
        ):
            duplicate_ids.add(row.pk)
        if data.get("isbn"):
            key = f"isbn:{data['isbn']}"
        else:
            title = data.get("title", "").casefold().strip()
            authors = "|".join(data.get("authors", [])).casefold().strip()
            key = f"metadata:{title}:{authors}:{data.get('publisher', '').casefold()}:{data.get('year', '')}"
        duplicate_groups.setdefault(key, []).append(row.pk)
    duplicate_ids.update(pk for ids in duplicate_groups.values() if len(ids) > 1 for pk in ids)
    row_data = []
    for row in rows:
        receipt = receipts.get(row.source_key)
        item = row.data["data"].copy()
        matching_book = existing_books.get(item.get("isbn", "")) if item.get("isbn") else None
        item.update(
            {
                "status": row.data["status"],
                "errors": row.data["errors"],
                "warnings": row.data["warnings"],
                "existing": matching_book is not None,
                "already_imported": receipt is not None,
                "possible_duplicate": row.pk in duplicate_ids,
                "processing_error": row.data.get("processing_error", ""),
                "copies_added": receipt.added_copies
                if receipt and row.result in {"created", "copied"}
                else 0,
            }
        )
        row_data.append(
            {
                "id": row.pk,
                "file_id": row.import_file_id,
                "file_row_number": row.file_row_number,
                "data": item,
                "result": row.result,
            }
        )
    return {"id": session.pk, "files": file_data, "rows": row_data}


def _create_libib_book(library: Library, data: dict[str, Any]) -> Book:
    tags = []
    for name in data.get("tag_names", []):
        tag, _ = Tag.objects.get_or_create(library=library, name=name[:60])
        tags.append(tag.pk)
    return create_book(
        library,
        {
            "title": data["title"],
            "authors": data["authors"],
            "isbn": data["isbn"],
            "publisher": data["publisher"],
            "year": data["year"],
            "page_count": data["page_count"],
            "source": "libib",
            "source_id": "",
            "tag_ids": tags,
        },
    )


def _process_libib_row(
    library: Library, session: ImportSession, row_id: int, action: str
) -> dict[str, Any]:
    with transaction.atomic():
        Library.objects.select_for_update().get(pk=library.pk)
        row = ImportRow.objects.select_for_update().get(session=session, pk=row_id)
        if row.result and row.result != "error":
            return {"id": row.pk, "result": row.result}
        if action == "skip":
            row.result = "skipped"
            row.save(update_fields=["result"])
            return {"id": row.pk, "result": row.result}
        if row.data["status"] != "valid":
            return {"id": row.pk, "result": row.data["status"], "errors": row.data["errors"]}

        receipt = ImportReceipt.objects.filter(library=library, source_key=row.source_key).first()
        if receipt:
            row.result = "already_imported"
            row.save(update_fields=["result"])
            return {"id": row.pk, "result": row.result}

        data = row.data["data"]
        book = libib_matching(library, row)
        if book and action != "copy":
            return {"id": row.pk, "result": "existing"}
        created_book = book is None
        book = book or _create_libib_book(library, data)
        copies = [add_copy(library, book.pk) for _ in range(data["copies"])]
        receipt = ImportReceipt.objects.create(
            library=library,
            source_key=row.source_key,
            file_sha256=data["file_sha256"],
            row_fingerprint=row.row_fingerprint,
            collection=data["collection"],
            desired_copies=data["copies"],
            added_copies=len(copies),
            decision="import" if created_book else "copy",
            state="completed",
            book=book,
        )
        ImportReceiptCopy.objects.bulk_create(
            [ImportReceiptCopy(library=library, receipt=receipt, copy=copy) for copy in copies],
            batch_size=100,
        )
        row.result = "created" if created_book else "copied"
        row.copy = copies[0]
        row.save(update_fields=["copy", "result"])
        return {"id": row.pk, "result": row.result, "copies_added": len(copies)}


def process_libib_rows(
    library: Library, session_id: int, actions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    session = owned(ImportSession, library, session_id)
    if session.source != ImportSession.SOURCE_LIBIB:
        raise ValidationError("Sessão de importação Libib não encontrada.")
    if session.created_at < timezone.now() - SESSION_RETENTION:
        raise ValidationError("Importação expirada. Envie os arquivos novamente.")
    if len(actions) > 25:
        raise ValidationError("Envie até 25 registros por lote.")
    if any(action.get("action") not in {"import", "copy", "skip"} for action in actions):
        raise ValidationError("Ação de importação inválida.")

    results = []
    for action in actions:
        try:
            row_id = int(action["id"])
        except (KeyError, TypeError, ValueError):
            raise ValidationError("Registro não encontrado nesta sessão.") from None
        try:
            results.append(_process_libib_row(library, session, row_id, action["action"]))
        except ImportRow.DoesNotExist:
            raise ValidationError("Registro não encontrado nesta sessão.") from None
        except ValidationError as exc:
            row = ImportRow.objects.filter(session=session, pk=row_id).first()
            if row:
                row.result = "error"
                row.data["processing_error"] = "; ".join(exc.messages)
                row.save(update_fields=["data", "result"])
                results.append(
                    {
                        "id": row.pk,
                        "result": "error",
                        "message": "Não foi possível processar este registro.",
                    }
                )
            else:
                raise ValidationError("Registro não encontrado nesta sessão.") from None
    return results
