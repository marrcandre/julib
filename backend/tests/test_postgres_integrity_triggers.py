import importlib.util
from contextlib import contextmanager
from pathlib import Path

import pytest
from django.db import DatabaseError, IntegrityError, connection
from django.db.transaction import atomic

from library import services
from library.models import Book, ImportRow, ImportSession, Library, Tag

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
        "julib_check_import_row_copy_library",
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
