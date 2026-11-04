from typing import Any
from django.utils import timezone
from .models import Book, Copy, Loan


def book_data(book: Book, public: bool = False) -> dict[str, Any]:
    copies = list(book.copies.all())
    result = {k: getattr(book, k) for k in ['id','title','authors','isbn','publisher','edition','year','language','cover_url']}
    result['tags'] = [{'id': t.pk, 'name': t.name} for t in book.tags.all()]
    result['available'] = any(c.state == 'active' and not any(l.state == 'open' for l in c.loans.all()) for c in copies)
    if not public:
        result['copies'] = [copy_data(c) for c in copies]
        result['source'] = book.source; result['source_id'] = book.source_id
    return result


def copy_data(copy: Copy) -> dict[str, Any]:
    return {'id': copy.pk, 'book_id': copy.book_id, 'number': copy.number, 'location_id': copy.location_id, 'acquired_on': copy.acquired_on.isoformat(), 'state': copy.state, 'on_loan': any(l.state == 'open' for l in copy.loans.all())}


def loan_data(loan: Loan) -> dict[str, Any]:
    return {'id': loan.pk, 'copy_id': loan.copy_id, 'copy_number': loan.copy.number, 'title': loan.copy.book.title, 'person_id': loan.person_id, 'person_name': loan.person.name, 'started_on': loan.started_on.isoformat(), 'due_on': loan.due_on.isoformat(), 'returned_on': loan.returned_on.isoformat() if loan.returned_on else None, 'state': loan.state, 'overdue': loan.state == 'open' and loan.due_on < timezone.localdate()}
