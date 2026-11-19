import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

pytestmark = pytest.mark.django_db(transaction=True)


def test_additive_metadata_migration_preserves_existing_book_values():
    executor = MigrationExecutor(connection)
    target = ("library", "0018_import_receipt_copy_book_integrity")
    executor.migrate([target])
    old_apps = executor.loader.project_state([target]).apps
    OldLibrary = old_apps.get_model("library", "Library")
    OldBook = old_apps.get_model("library", "Book")
    library = OldLibrary.objects.create(name="Migração descartável")
    book = OldBook.objects.create(
        library_id=library.pk,
        title="Livro existente",
        authors=["Autora"],
        isbn="9788535914849",
        publisher="Editora existente",
        page_count=321,
    )

    executor = MigrationExecutor(connection)
    executor.migrate([("library", "0019_book_bibliographic_metadata")])
    new_apps = (
        MigrationExecutor(connection)
        .loader.project_state([("library", "0019_book_bibliographic_metadata")])
        .apps
    )
    NewBook = new_apps.get_model("library", "Book")
    migrated = NewBook.objects.get(pk=book.pk)

    assert migrated.title == "Livro existente"
    assert migrated.isbn == "9788535914849"
    assert migrated.publisher == "Editora existente"
    assert migrated.page_count == 321
    assert migrated.subtitle == ""
    assert migrated.description == ""
    assert migrated.subjects == []

    MigrationExecutor(connection).migrate(MigrationExecutor(connection).loader.graph.leaf_nodes())
