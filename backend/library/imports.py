import csv
import io
from datetime import timedelta
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Book, ImportRow, ImportSession, Library
from .services import add_copy, create_book, normalize_isbn, owned


@transaction.atomic
def preview_csv(library: Library, content: bytes) -> ImportSession:
    if len(content) > 3 * 1024 * 1024:
        raise ValidationError("O CSV deve ter até 3 MB.")
    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
        if not {"Title", "Author"}.issubset(reader.fieldnames or []):
            raise ValidationError("Use o CSV exportado pelo Goodreads, com Title e Author.")
        session = ImportSession.objects.create(library=library)
        rows = []
        for i, row in enumerate(reader, 1):
            if i > 5000:
                raise ValidationError("Limite de 5.000 linhas por importação.")
            isbn = ""
            for column in ("ISBN13", "ISBN"):
                raw = (row.get(column) or "").strip().strip('="')
                try:
                    isbn = normalize_isbn(raw)
                except ValidationError:
                    continue
                if isbn:
                    break
            data = {
                "title": (row.get("Title") or "").strip(),
                "authors": [(row.get("Author") or "").strip() or "Autoria desconhecida"],
                "isbn": isbn,
                "publisher": (row.get("Publisher") or "")[:200],
                "year": (row.get("Year Published") or "")[:20],
                "source": "goodreads",
                "source_id": (row.get("Book Id") or "")[:150],
            }
            rows.append(ImportRow(session=session, position=i, data=data))
        if not rows:
            raise ValidationError("O arquivo não contém livros.")
        ImportRow.objects.bulk_create(rows)
        return session
    except (UnicodeError, csv.Error):
        raise ValidationError("Arquivo inválido. Exporte um CSV UTF-8 do Goodreads.") from None


def matching(library: Library, data: dict[str, Any]) -> Book | None:
    if data.get("isbn"):
        book = Book.objects.filter(library=library, isbn=data["isbn"]).first()
        if book:
            return book
    if data.get("source_id"):
        return Book.objects.filter(
            library=library, source="goodreads", source_id=data["source_id"]
        ).first()
    return None


def process_rows(
    library: Library, session_id: int, actions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    session = owned(ImportSession, library, session_id)
    if session.created_at < timezone.now() - timedelta(days=7):
        raise ValidationError("Importação expirada. Envie o arquivo novamente.")
    if len(actions) > 25:
        raise ValidationError("Envie até 25 livros por lote.")
    results = []
    for action in actions:
        with transaction.atomic():
            Library.objects.select_for_update().get(pk=library.pk)
            try:
                row = ImportRow.objects.select_for_update().get(session=session, pk=action["id"])
            except ImportRow.DoesNotExist:
                raise ValidationError("Linha não encontrada.") from None
            if row.result:
                results.append({"id": row.pk, "result": row.result})
                continue
            if action.get("action") not in {"import", "copy", "skip"}:
                raise ValidationError("Ação de importação inválida.")
            if action["action"] == "skip":
                row.result = "skipped"
            else:
                book = matching(library, row.data)
                if book and action["action"] != "copy":
                    row.result = "existing"
                else:
                    book = book or create_book(library, row.data)
                    row.copy = add_copy(library, book.pk)
                    row.result = "created"
            row.save(update_fields=["copy", "result"])
            results.append({"id": row.pk, "result": row.result})
    return results
