import calendar
from datetime import date
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from .models import Copy, Library, Loan, Person
from .services import owned


def next_month(day: date) -> date:
    year, month = (day.year + 1, 1) if day.month == 12 else (day.year, day.month + 1)
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


@transaction.atomic
def lend(library: Library, copy_id: int, person_id: int, started_on: date | None = None, due_on: date | None = None) -> Loan:
    copy = owned(Copy, library, copy_id, lock=True)
    person = owned(Person, library, person_id)
    if copy.state != 'active' or copy.loans.filter(state='open').exists() or person.archived:
        raise ValidationError('Exemplar ou pessoa indisponível para empréstimo.')
    start = started_on or timezone.localdate()
    loan = Loan(library=library, copy=copy, person=person, started_on=start, due_on=due_on or next_month(start))
    loan.full_clean(); loan.save()
    return loan


@transaction.atomic
def return_loan(library: Library, loan_id: int, returned_on: date) -> Loan:
    loan = owned(Loan, library, loan_id)
    owned(Copy, library, loan.copy_id, lock=True)
    loan = owned(Loan, library, loan_id, lock=True)
    if loan.state != 'open':
        raise ValidationError('Este empréstimo já foi encerrado.')
    loan.state = 'returned'; loan.returned_on = returned_on
    loan.full_clean(); loan.save()
    return loan


@transaction.atomic
def retire_copy(library: Library, copy_id: int, reason: str) -> Copy:
    if reason not in {'sold','donated','lost','active'}:
        raise ValidationError('Motivo inválido.')
    copy = owned(Copy, library, copy_id, lock=True)
    loans = copy.loans.filter(state='open')
    if loans.exists() and reason != 'lost':
        raise ValidationError('Registre a devolução antes de dar baixa.')
    if reason == 'lost':
        loans.update(state='lost')
    copy.state = reason; copy.retired_on = None if reason == 'active' else timezone.localdate()
    copy.save(update_fields=['state','retired_on'])
    return copy
