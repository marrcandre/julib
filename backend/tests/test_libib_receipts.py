import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from library.models import (
    Book,
    Copy,
    ImportFile,
    ImportReceipt,
    ImportReceiptCopy,
    ImportSession,
    Library,
)

pytestmark = pytest.mark.django_db


def test_import_receipt_is_unique_per_library_and_source_row():
    library = Library.objects.create(name="Casa")
    session = ImportSession.objects.create(library=library, source="libib")
    ImportFile.objects.create(session=session, position=1, original_name="a.csv", sha256="a" * 64)
    ImportReceipt.objects.create(
        library=library,
        source_key="b" * 64,
        file_sha256="a" * 64,
        row_fingerprint="c" * 64,
        desired_copies=2,
        added_copies=2,
        decision="import",
        state="completed",
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        ImportReceipt.objects.create(
            library=library,
            source_key="b" * 64,
            file_sha256="d" * 64,
            row_fingerprint="e" * 64,
            desired_copies=1,
            added_copies=1,
            decision="copy",
            state="completed",
        )


def test_import_receipts_outlive_expired_session_rows():
    library = Library.objects.create(name="Casa")
    session = ImportSession.objects.create(library=library, source="libib")
    ImportFile.objects.create(session=session, position=1, original_name="a.csv", sha256="a" * 64)
    receipt = ImportReceipt.objects.create(
        library=library,
        source_key="b" * 64,
        file_sha256="a" * 64,
        row_fingerprint="c" * 64,
        desired_copies=1,
        added_copies=1,
        decision="import",
        state="completed",
    )

    session.delete()

    assert ImportReceipt.objects.get(pk=receipt.pk).source_key == "b" * 64


def test_receipt_copy_relation_rejects_a_copy_from_another_library():
    first = Library.objects.create(name="Casa A")
    second = Library.objects.create(name="Casa B")
    receipt = ImportReceipt.objects.create(
        library=first,
        source_key="b" * 64,
        file_sha256="a" * 64,
        row_fingerprint="c" * 64,
        desired_copies=1,
        added_copies=1,
        decision="import",
        state="completed",
    )
    book = Book.objects.create(library=second, title="Livro", authors=["Autora"])
    copy = Copy.objects.create(library=second, book=book, number=1)

    with pytest.raises((IntegrityError, ValidationError)), transaction.atomic():
        ImportReceiptCopy.objects.create(library=first, receipt=receipt, copy=copy)
