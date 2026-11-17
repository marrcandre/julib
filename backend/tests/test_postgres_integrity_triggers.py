import importlib.util
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path

import pytest
from django.db import DatabaseError, IntegrityError, connection
from django.db.transaction import atomic

from library import services
from library.models import (
    Book,
    Copy,
    ImportFile,
    ImportReceipt,
    ImportReceiptCopy,
    ImportRow,
    ImportSession,
    Library,
    Tag,
)

backup_spec = importlib.util.spec_from_file_location(
    "backup", Path(__file__).resolve().parents[2] / "scripts/backup.py"
)
backup_module = importlib.util.module_from_spec(backup_spec)
backup_spec.loader.exec_module(backup_module)

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(connection.vendor != "postgresql", reason="requires PostgreSQL 17"),
]

TEMP_TABLE_COLUMNS = {
    "library_book": "id bigint, library_id bigint",
    "library_tag": "id bigint, library_id bigint",
    "library_copy": "id bigint, library_id bigint",
    "library_importsession": "id bigint, library_id bigint",
    "library_book_tags": "book_id bigint, tag_id bigint",
    "library_importrow": "session_id bigint, copy_id bigint",
}


@pytest.fixture(autouse=True)
def require_postgresql_17():
    with connection.cursor() as cursor:
        cursor.execute("SHOW server_version_num")
        version = int(cursor.fetchone()[0])
    assert 170000 <= version < 180000


@contextmanager
def _shadow_relations(*names: str):
    with connection.cursor() as cursor:
        for name in names:
            cursor.execute(f'CREATE TEMP TABLE "{name}" ({TEMP_TABLE_COLUMNS[name]})')
        cursor.execute("SET search_path = pg_temp, public, pg_catalog")
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute("RESET search_path")
            for name in reversed(names):
                cursor.execute(f'DROP TABLE pg_temp."{name}"')


def _two_books_and_tags():
    left = Library.objects.create(name="Esquerda")
    right = Library.objects.create(name="Direita")
    left_book = services.create_book(left, {"title": "Livro A", "authors": ["Autora"]})
    right_book = services.create_book(right, {"title": "Livro B", "authors": ["Autor"]})
    left_tag = Tag.objects.create(library=left, name="Tag A")
    right_tag = Tag.objects.create(library=right, name="Tag B")
    return left, right, left_book, right_book, left_tag, right_tag


def test_book_tag_trigger_rejects_cross_library_relation_with_temp_shadows():
    _, _, left_book, _, _, right_tag = _two_books_and_tags()
    with _shadow_relations("library_book", "library_tag"):
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO pg_temp.library_book VALUES (%s, 99)", [left_book.pk])
            cursor.execute("INSERT INTO pg_temp.library_tag VALUES (%s, 99)", [right_tag.pk])
        with pytest.raises(IntegrityError), atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO public.library_book_tags (book_id, tag_id) VALUES (%s, %s)",
                    [left_book.pk, right_tag.pk],
                )


@pytest.mark.parametrize("parent", ["book", "tag"])
def test_book_tag_parent_trigger_rejects_library_move_with_temp_shadows(parent):
    left, right, book, _, tag, _ = _two_books_and_tags()
    book.tags.add(tag)
    table = "public.library_book" if parent == "book" else "public.library_tag"
    pk = book.pk if parent == "book" else tag.pk
    with _shadow_relations("library_book_tags", "library_tag", "library_book"):
        with pytest.raises(IntegrityError), atomic():
            with connection.cursor() as cursor:
                cursor.execute(f"UPDATE {table} SET library_id = %s WHERE id = %s", [right.pk, pk])

    assert Book.objects.filter(pk=book.pk, library=left).exists()


def test_import_row_trigger_rejects_cross_library_copy_with_temp_shadows():
    left, right, _, right_book, _, _ = _two_books_and_tags()
    session = ImportSession.objects.create(library=left)
    copy = services.add_copy(right, right_book.pk)
    with _shadow_relations("library_importsession", "library_copy"):
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO pg_temp.library_importsession VALUES (%s, 99)", [session.pk]
            )
            cursor.execute("INSERT INTO pg_temp.library_copy VALUES (%s, 99)", [copy.pk])
        with pytest.raises(IntegrityError), atomic():
            ImportRow.objects.create(session=session, position=1, data={}, copy=copy)


def test_import_row_parent_trigger_rejects_library_move_with_temp_shadows():
    left, right, _, _, _, _ = _two_books_and_tags()
    session = ImportSession.objects.create(library=left)
    book = services.create_book(left, {"title": "Importado", "authors": ["Autora"]})
    copy = services.add_copy(left, book.pk)
    ImportRow.objects.create(session=session, position=1, data={}, copy=copy)
    with _shadow_relations("library_importrow", "library_copy"):
        with pytest.raises(IntegrityError), atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE public.library_importsession SET library_id = %s WHERE id = %s",
                    [right.pk, session.pk],
                )

    assert ImportSession.objects.filter(pk=session.pk, library=left).exists()


def test_import_row_copy_parent_trigger_rejects_library_move_with_temp_shadows():
    left, right, _, _, _, _ = _two_books_and_tags()
    session = ImportSession.objects.create(library=left)
    book = services.create_book(left, {"title": "Importado", "authors": ["Autora"]})
    copy = services.add_copy(left, book.pk)
    ImportRow.objects.create(session=session, position=1, data={}, copy=copy)
    with _shadow_relations("library_importrow", "library_importsession"):
        with pytest.raises(IntegrityError) as error:
            with atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE public.library_book SET library_id = %s WHERE id = %s",
                        [right.pk, book.pk],
                    )
                    cursor.execute(
                        "UPDATE public.library_copy SET library_id = %s WHERE id = %s",
                        [right.pk, copy.pk],
                    )

    assert error.value.__cause__.sqlstate == "23514"
    assert Book.objects.filter(pk=book.pk, library=left).exists()
    assert ImportRow.objects.get(session=session).copy_id == copy.pk


def test_import_receipt_copy_trigger_rejects_cross_library_copy():
    left, right, _, _, _, _ = _two_books_and_tags()
    receipt = ImportReceipt.objects.create(
        library=left,
        source_key="b" * 64,
        file_sha256="a" * 64,
        row_fingerprint="c" * 64,
        desired_copies=1,
        added_copies=1,
        decision="import",
    )
    book = services.create_book(right, {"title": "Outro", "authors": ["Autor"]})
    copy = services.add_copy(right, book.pk)

    with pytest.raises(IntegrityError) as error:
        with atomic():
            ImportReceiptCopy.objects.bulk_create(
                [ImportReceiptCopy(library=left, receipt=receipt, copy=copy)]
            )

    assert error.value.__cause__.sqlstate == "23514"


def test_import_receipt_accepts_multiple_copies_of_its_book():
    library, _, book, _, _, _ = _two_books_and_tags()
    receipt = ImportReceipt.objects.create(
        library=library,
        source_key="1" * 64,
        file_sha256="2" * 64,
        row_fingerprint="3" * 64,
        desired_copies=2,
        added_copies=2,
        decision="import",
        book=book,
    )
    copies = [services.add_copy(library, book.pk) for _ in range(2)]

    ImportReceiptCopy.objects.bulk_create(
        [ImportReceiptCopy(library=library, receipt=receipt, copy=copy) for copy in copies]
    )

    assert receipt.copies.count() == 2


def test_deleting_imported_copies_and_book_keeps_durable_receipt_valid():
    library, _, book, _, _, _ = _two_books_and_tags()
    receipt = ImportReceipt.objects.create(
        library=library,
        source_key="0" * 64,
        file_sha256="1" * 64,
        row_fingerprint="2" * 64,
        desired_copies=1,
        added_copies=1,
        decision="import",
        book=book,
    )
    copy = services.add_copy(library, book.pk)
    relation = ImportReceiptCopy.objects.create(library=library, receipt=receipt, copy=copy)

    copy.delete()
    book.delete()

    relation.refresh_from_db()
    receipt.refresh_from_db()
    assert relation.copy_id is None
    assert receipt.book_id is None
    assert ImportReceipt.objects.filter(pk=receipt.pk).exists()


def test_import_receipt_copy_trigger_rejects_another_book_in_same_library():
    library, _, book, _, _, _ = _two_books_and_tags()
    other_book = services.create_book(library, {"title": "Outro", "authors": ["Autora"]})
    receipt = ImportReceipt.objects.create(
        library=library,
        source_key="4" * 64,
        file_sha256="5" * 64,
        row_fingerprint="6" * 64,
        desired_copies=1,
        added_copies=1,
        decision="import",
        book=book,
    )
    other_copy = services.add_copy(library, other_book.pk)

    with pytest.raises(IntegrityError) as error:
        with atomic():
            ImportReceiptCopy.objects.bulk_create(
                [ImportReceiptCopy(library=library, receipt=receipt, copy=other_copy)]
            )

    assert error.value.__cause__.sqlstate == "23514"


def test_import_receipt_copy_update_rejects_another_book_in_same_library():
    library, _, book, _, _, _ = _two_books_and_tags()
    other_book = services.create_book(library, {"title": "Outro", "authors": ["Autora"]})
    receipt = ImportReceipt.objects.create(
        library=library,
        source_key="7" * 64,
        file_sha256="8" * 64,
        row_fingerprint="9" * 64,
        desired_copies=1,
        added_copies=1,
        decision="import",
        book=book,
    )
    copy = services.add_copy(library, book.pk)
    relation = ImportReceiptCopy.objects.create(library=library, receipt=receipt, copy=copy)
    other_copy = services.add_copy(library, other_book.pk)

    with pytest.raises(IntegrityError) as error:
        with atomic():
            ImportReceiptCopy.objects.filter(pk=relation.pk).update(copy=other_copy)

    assert error.value.__cause__.sqlstate == "23514"


def test_import_receipt_and_copy_book_updates_reject_existing_mismatched_relations():
    library, _, book, _, _, _ = _two_books_and_tags()
    other_book = services.create_book(library, {"title": "Outro", "authors": ["Autora"]})
    receipt = ImportReceipt.objects.create(
        library=library,
        source_key="a" * 64,
        file_sha256="b" * 64,
        row_fingerprint="c" * 64,
        desired_copies=1,
        added_copies=1,
        decision="import",
        book=book,
    )
    copy = services.add_copy(library, book.pk)
    ImportReceiptCopy.objects.create(library=library, receipt=receipt, copy=copy)

    with pytest.raises(IntegrityError) as receipt_error:
        with atomic():
            ImportReceipt.objects.filter(pk=receipt.pk).update(book=other_book)
    with pytest.raises(IntegrityError) as copy_error:
        with atomic():
            Copy.objects.filter(pk=copy.pk).update(book=other_book)

    assert receipt_error.value.__cause__.sqlstate == "23514"
    assert copy_error.value.__cause__.sqlstate == "23514"


@pytest.mark.django_db(transaction=True)
def test_concurrent_copy_reassignment_cannot_race_receipt_link_creation():
    from django.db import close_old_connections, connection

    library, _, book, _, _, _ = _two_books_and_tags()
    other_book = services.create_book(library, {"title": "Outro", "authors": ["Autora"]})
    receipt = ImportReceipt.objects.create(
        library=library,
        source_key="d" * 64,
        file_sha256="e" * 64,
        row_fingerprint="f" * 64,
        desired_copies=1,
        added_copies=1,
        decision="import",
        book=book,
    )
    copy = services.add_copy(library, book.pk)
    reassigned = threading.Event()
    relation_attempting = threading.Event()
    release_reassignment = threading.Event()

    def reassign_copy():
        close_old_connections()
        try:
            with atomic():
                Copy.objects.filter(pk=copy.pk).update(book=other_book)
                reassigned.set()
                assert release_reassignment.wait(timeout=5)
        finally:
            close_old_connections()

    def create_receipt_link():
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET application_name = 'libib-review-relation-race'")
            assert reassigned.wait(timeout=5)
            try:
                with atomic():
                    relation_attempting.set()
                    ImportReceiptCopy.objects.create(library=library, receipt=receipt, copy=copy)
                return "accepted"
            except IntegrityError:
                return "rejected"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        reassign_future = pool.submit(reassign_copy)
        link_future = pool.submit(create_receipt_link)
        assert relation_attempting.wait(timeout=5)
        deadline = time.monotonic() + 5
        waiting_for_lock = False
        while time.monotonic() < deadline:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT wait_event_type FROM pg_stat_activity "
                    "WHERE application_name = 'libib-review-relation-race'"
                )
                row = cursor.fetchone()
            if row and row[0] == "Lock":
                waiting_for_lock = True
                break
            time.sleep(0.01)
        release_reassignment.set()
        reassign_future.result(timeout=5)
        result = link_future.result(timeout=5)

    assert waiting_for_lock
    assert result == "rejected"
    assert not ImportReceiptCopy.objects.filter(receipt=receipt).exists()


def test_import_row_trigger_rejects_file_from_another_session():
    left, _, _, _, _, _ = _two_books_and_tags()
    session = ImportSession.objects.create(library=left, source="libib")
    other_session = ImportSession.objects.create(library=left, source="libib")
    file = ImportFile.objects.create(
        session=other_session, position=1, original_name="a.csv", sha256="d" * 64
    )

    with pytest.raises(IntegrityError) as error:
        with atomic():
            ImportRow.objects.create(session=session, import_file=file, position=1, data={})

    assert error.value.__cause__.sqlstate == "23514"


def test_import_receipt_trigger_rejects_book_from_another_library():
    left, right, _, _, _, _ = _two_books_and_tags()
    receipt = ImportReceipt.objects.create(
        library=left,
        source_key="f" * 64,
        file_sha256="e" * 64,
        row_fingerprint="d" * 64,
        desired_copies=1,
        added_copies=0,
        decision="import",
    )
    foreign_book = services.create_book(right, {"title": "Alheio", "authors": ["Autor"]})

    with pytest.raises(IntegrityError) as error:
        with atomic():
            ImportReceipt.objects.filter(pk=receipt.pk).update(book=foreign_book)

    assert error.value.__cause__.sqlstate == "23514"


def test_import_file_trigger_rejects_parent_session_move():
    left, _, _, _, _, _ = _two_books_and_tags()
    first = ImportSession.objects.create(library=left, source="libib")
    second = ImportSession.objects.create(library=left, source="libib")
    file = ImportFile.objects.create(
        session=first, position=1, original_name="a.csv", sha256="c" * 64
    )
    ImportRow.objects.create(session=first, import_file=file, position=1, data={})

    with pytest.raises(IntegrityError) as error:
        with atomic():
            ImportFile.objects.filter(pk=file.pk).update(session=second)

    assert error.value.__cause__.sqlstate == "23514"


def test_all_integrity_triggers_have_fixed_search_path():
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT p.proname, p.proconfig
            FROM pg_catalog.pg_proc p
            JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'public' AND p.proname LIKE 'julib_check_%'
            ORDER BY p.proname
            """
        )
        configs = {name: config for name, config in cursor.fetchall()}

    assert set(configs) == {
        "julib_check_book_tag_library",
        "julib_check_book_tag_parent_library",
        "julib_check_import_receipt_copy_library",
        "julib_check_import_receipt_copy_book_parent",
        "julib_check_import_receipt_copy_book",
        "julib_check_import_receipt_copy_parent_library",
        "julib_check_import_receipt_library",
        "julib_check_import_row_file_parent_session",
        "julib_check_import_row_copy_library",
        "julib_check_import_row_file_session",
        "julib_check_import_row_parent_library",
    }
    assert all(config == ["search_path=pg_catalog, public, pg_temp"] for config in configs.values())


def test_backup_read_scope_rejects_application_table_writes():
    library = Library.objects.create(name="Não alterar")

    with pytest.raises(DatabaseError, match="read-only"):
        with backup_module.read_only_transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE public.library_library SET name = 'Alterada' WHERE id = %s",
                    [library.pk],
                )

    assert Library.objects.get(pk=library.pk).name == "Não alterar"
