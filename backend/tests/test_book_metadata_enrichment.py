import json
from io import StringIO

import pytest
from django.core.management import call_command

from library import services
from library.models import Book, Library

pytestmark = pytest.mark.django_db
ISBN = "9788535914849"


def make_book(library=None, **fields):
    return services.create_book(
        library or Library.objects.create(name="Casa"),
        {
            "title": "Livro",
            "authors": ["Autora"],
            "isbn": ISBN,
            "publisher": "Editora",
            "year": "2020",
            "language": "pt",
            "page_count": 200,
            "edition": "1ª edição",
            **fields,
        },
    )


def result(data, **values):
    provenance = {
        key: {"source": "cbl", "source_id": ISBN}
        for key, value in values.items()
        if value not in (None, "", [])
    }
    return {**data, **values, "provenance": provenance}


def test_metadata_enrichment_defaults_to_preview_with_values_and_sources(monkeypatch):
    from library import providers

    library = Library.objects.create(name="Casa")
    book = make_book(library)
    monkeypatch.setattr(
        providers,
        "enrich_book",
        lambda data, lookup=None: result(
            data,
            subtitle="Subtítulo",
            description="Uma sinopse extensa com texto seguro.",
            subjects=["História", "Literatura"],
        ),
    )
    output = StringIO()

    call_command("enrich_books", library=library.pk, delay=0, stdout=output)

    book.refresh_from_db()
    assert (book.subtitle, book.description, book.subjects) == ("", "", [])
    assert "subtítulo" in output.getvalue().lower()
    assert "cbl" in output.getvalue()
    assert "Uma sinopse extensa" in output.getvalue()
    assert "JSON:" in output.getvalue()


def test_apply_fills_only_empty_metadata_and_preserves_manual_provenance(monkeypatch):
    from library import providers

    library = Library.objects.create(name="Casa")
    book = make_book(
        library,
        subtitle="Subtítulo manual",
        provenance={"subtitle": {"source": "manual", "source_id": ""}},
    )
    monkeypatch.setattr(
        providers,
        "enrich_book",
        lambda data, lookup=None: result(
            data,
            subtitle="Subtítulo da API",
            description="Descrição da API",
            subjects=["História", " história ", "Literatura"],
        ),
    )

    call_command("enrich_books", library=library.pk, delay=0, apply=True, stdout=StringIO())

    book.refresh_from_db()
    assert book.subtitle == "Subtítulo manual"
    assert book.description == "Descrição da API"
    assert book.subjects == ["História", "Literatura"]
    assert book.provenance["subtitle"]["source"] == "manual"
    assert book.provenance["description"]["source"] == "cbl"


def test_apply_rechecks_concurrent_description_edit_under_lock(monkeypatch):
    from library import providers

    library = Library.objects.create(name="Casa")
    book = make_book(
        library,
        cover_url="https://res.cloudinary.com/julib/manual.jpg",
        cover_id="julib/manual",
    )

    def concurrent_edit(data, lookup=None):
        Book.objects.filter(pk=book.pk).update(description="Edição manual concorrente")
        return result(data, description="Descrição da API", subjects=["Ficção"])

    monkeypatch.setattr(providers, "enrich_book", concurrent_edit)
    call_command("enrich_books", library=library.pk, delay=0, apply=True, stdout=StringIO())

    book.refresh_from_db()
    assert book.description == "Edição manual concorrente"
    assert book.subjects == ["Ficção"]
    assert "description" not in book.provenance


def test_wrong_isbn_result_is_reported_and_never_applied(monkeypatch):
    from library import providers

    library = Library.objects.create(name="Casa")
    book = make_book(library)
    monkeypatch.setattr(
        providers,
        "enrich_book",
        lambda data, lookup=None: result(
            {**data, "isbn": "9780261102217"}, description="ISBN divergente"
        ),
    )
    output = StringIO()

    call_command("enrich_books", library=library.pk, delay=0, apply=True, stdout=output)

    book.refresh_from_db()
    assert book.description == ""
    assert "divergência" in output.getvalue().lower()


def test_repeated_apply_is_idempotent_and_library_scoped(monkeypatch):
    from library import providers

    library = Library.objects.create(name="Casa")
    other = Library.objects.create(name="Outra")
    book = make_book(
        library,
        cover_url="https://res.cloudinary.com/julib/manual.jpg",
        cover_id="julib/manual",
    )
    foreign = make_book(other)
    calls = []
    monkeypatch.setattr(
        providers,
        "enrich_book",
        lambda data, lookup=None: (
            calls.append(data["isbn"])
            or result(
                data,
                subtitle="Subtítulo",
                description="Descrição",
                subjects=["Ficção"],
            )
        ),
    )

    call_command("enrich_books", library=library.pk, delay=0, apply=True, stdout=StringIO())
    call_command("enrich_books", library=library.pk, delay=0, apply=True, stdout=StringIO())

    book.refresh_from_db()
    foreign.refresh_from_db()
    assert calls == [ISBN]
    assert book.description == "Descrição"
    assert foreign.description == ""


def test_preview_emits_machine_readable_aggregate_metrics(monkeypatch):
    from library import providers

    library = Library.objects.create(name="Casa")
    make_book(library)

    def enrich(data, lookup=None):
        lookup.providers_queried.append("cbl")
        lookup.provider_outcomes["cbl"] = "match"
        return result(data, subjects=["Ficção"])

    monkeypatch.setattr(providers, "enrich_book", enrich)
    output = StringIO()

    call_command("enrich_books", library=library.pk, delay=0, stdout=output)

    line = next(
        line.removeprefix("JSON: ")
        for line in output.getvalue().splitlines()
        if line.startswith("JSON: ")
    )
    report = json.loads(line)
    assert report["books_analyzed"] == 1
    assert report["fields_found"]["subjects"] == 1
    assert report["providers"]["cbl"]["matches"] == 1


def test_existing_provenance_is_not_reported_as_a_current_provider_match(monkeypatch):
    from library import providers

    library = Library.objects.create(name="Casa")
    make_book(
        library,
        description="Descrição existente",
        provenance={"description": {"source": "cbl", "source_id": ISBN}},
    )

    def enrich(data, lookup=None):
        lookup.providers_queried.append("cbl")
        lookup.provider_outcomes["cbl"] = "match"
        return data

    monkeypatch.setattr(providers, "enrich_book", enrich)
    output = StringIO()

    call_command("enrich_books", library=library.pk, delay=0, stdout=output)

    line = next(
        line.removeprefix("JSON: ")
        for line in output.getvalue().splitlines()
        if line.startswith("JSON: ")
    )
    report = json.loads(line)
    assert report["fields_found"]["description"] == 0
    assert report["providers"]["cbl"]["queried"] == 1
    assert report["providers"]["cbl"]["matches"] == 1
