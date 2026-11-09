from typing import Any
from urllib.parse import parse_qs, quote, urlsplit

from django.utils import timezone

from .models import Book, Copy, Loan


def book_data(book: Book, public: bool = False) -> dict[str, Any]:
    copies = list(book.copies.all())
    result = {
        k: getattr(book, k)
        for k in [
            "id",
            "title",
            "authors",
            "isbn",
            "publisher",
            "edition",
            "year",
            "language",
            "page_count",
            "cover_url",
        ]
    }
    result["tags"] = [{"id": t.pk, "name": t.name} for t in book.tags.all()]
    result.update(cover_attribution(book))
    result.update(metadata_attribution(book))
    result["available"] = any(
        c.state == "active" and not any(loan.state == "open" for loan in c.loans.all())
        for c in copies
    )
    if not public:
        result["is_desired"] = book.is_desired
        result["can_delete"] = not any(list(c.loans.all()) for c in copies)
        result["copies"] = [copy_data(c) for c in copies]
        result["source"] = book.source
        result["source_id"] = book.source_id
        result["provenance"] = book.provenance
    return result


def metadata_attribution(book: Book) -> dict[str, str]:
    identifier = (
        book.source_id
        if book.source == "google"
        else next(
            (
                entry.get("source_id", "")
                for field, entry in book.provenance.items()
                if field != "cover_url"
                and isinstance(entry, dict)
                and entry.get("source") == "google"
            ),
            "",
        )
    )
    if identifier:
        return {
            "metadata_attribution_name": "Google Books",
            "metadata_attribution_url": "https://books.google.com/books?id="
            + quote(identifier, safe=""),
        }
    return {"metadata_attribution_name": "", "metadata_attribution_url": ""}


def cover_attribution(book: Book) -> dict[str, str]:
    # Only the actual current image determines its credit. The metadata origin
    # remains independent, including after the user uploads their own cover.
    cover = urlsplit(book.cover_url)
    if cover.hostname in {"books.google.com", "books.googleusercontent.com"}:
        volume = parse_qs(cover.query).get("id", [""])[0]
        if volume:
            return {
                "attribution_name": "Google Books",
                "attribution_url": "https://books.google.com/books?id=" + quote(volume, safe=""),
            }
    origin = book.provenance.get("cover_url", {})
    if (
        isinstance(origin, dict)
        and origin.get("source") == "google"
        and origin.get("url") == book.cover_url
        and origin.get("source_id")
    ):
        return {
            "attribution_name": "Google Books",
            "attribution_url": "https://books.google.com/books?id="
            + quote(origin["source_id"], safe=""),
        }
    return {"attribution_name": "", "attribution_url": ""}


def candidate_credits(data: dict[str, Any]) -> dict[str, Any]:
    book = Book(
        **{
            key: data[key]
            for key in ("source", "source_id", "cover_url", "provenance")
            if key in data
        }
    )
    return {**data, **metadata_attribution(book), **cover_attribution(book)}


def copy_data(copy: Copy) -> dict[str, Any]:
    return {
        "id": copy.pk,
        "book_id": copy.book_id,
        "number": copy.number,
        "location_id": copy.location_id,
        "acquired_on": copy.acquired_on.isoformat(),
        "state": copy.state,
        "on_loan": any(loan.state == "open" for loan in copy.loans.all()),
    }


def loan_data(loan: Loan) -> dict[str, Any]:
    return {
        "id": loan.pk,
        "copy_id": loan.copy_id,
        "copy_number": loan.copy.number,
        "title": loan.copy.book.title,
        "cover_url": loan.copy.book.cover_url,
        **cover_attribution(loan.copy.book),
        **metadata_attribution(loan.copy.book),
        "person_id": loan.person_id,
        "person_name": loan.person.name,
        "started_on": loan.started_on.isoformat(),
        "due_on": loan.due_on.isoformat(),
        "returned_on": loan.returned_on.isoformat() if loan.returned_on else None,
        "state": loan.state,
        "overdue": loan.state == "open" and loan.due_on < timezone.localdate(),
    }
