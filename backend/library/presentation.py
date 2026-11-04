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
            "cover_url",
        ]
    }
    result["tags"] = [{"id": t.pk, "name": t.name} for t in book.tags.all()]
    result["attribution_name"] = ""
    result["attribution_url"] = ""
    if book.source == "google" and book.source_id:
        result["attribution_name"] = "Google Books"
        result["attribution_url"] = "https://books.google.com/books?id=" + quote(
            book.source_id, safe=""
        )
    elif book.source == "openlibrary" and book.source_id:
        result["attribution_name"] = "Open Library"
        result["attribution_url"] = "https://openlibrary.org" + "/" + book.source_id.lstrip("/")
    # Cover provenance can differ from Goodreads metadata provenance.
    cover = urlsplit(book.cover_url)
    if book.source not in {"google", "openlibrary"}:
        if cover.hostname in {"books.google.com", "books.googleusercontent.com"}:
            volume = parse_qs(cover.query).get("id", [""])[0]
            if volume:
                result["attribution_name"] = "Google Books"
                result["attribution_url"] = "https://books.google.com/books?id=" + quote(
                    volume, safe=""
                )
        elif cover.hostname == "covers.openlibrary.org":
            result["attribution_name"] = "Open Library"
            result["attribution_url"] = (
                "https://openlibrary.org/isbn/" + quote(book.isbn, safe="")
                if book.isbn
                else "https://openlibrary.org"
            )
    result["available"] = any(
        c.state == "active" and not any(loan.state == "open" for loan in c.loans.all())
        for c in copies
    )
    if not public:
        result["copies"] = [copy_data(c) for c in copies]
        result["source"] = book.source
        result["source_id"] = book.source_id
    return result


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
        "person_id": loan.person_id,
        "person_name": loan.person.name,
        "started_on": loan.started_on.isoformat(),
        "due_on": loan.due_on.isoformat(),
        "returned_on": loan.returned_on.isoformat() if loan.returned_on else None,
        "state": loan.state,
        "overdue": loan.state == "open" and loan.due_on < timezone.localdate(),
    }
