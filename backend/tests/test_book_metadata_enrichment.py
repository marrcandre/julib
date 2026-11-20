import csv
import json
from io import StringIO

import httpx
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

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


def test_json_report_exports_per_field_preview_and_existing_statuses(tmp_path, monkeypatch):
    from library import providers

    library = Library.objects.create(name="Casa")
    book = make_book(library, subtitle="Subtítulo manual")
    calls = []
    monkeypatch.setattr(
        providers,
        "enrich_book",
        lambda data, lookup=None: (
            calls.append(data["isbn"]) or result(data, description="Descrição candidata")
        ),
    )
    report_path = tmp_path / "report.json"

    call_command(
        "enrich_books",
        library=library.pk,
        delay=0,
        report_format="json",
        report_file=str(report_path),
        stdout=StringIO(),
    )

    report = json.loads(report_path.read_text())
    assert report["mode"] == "preview"
    assert report["summary"]["books_analyzed"] == 1
    details = {row["field"]: row for row in report["details"] if row["book_id"] == book.pk}
    assert details["subtitle"]["status"] == "já preenchido"
    assert details["description"]["status"] == "seria preenchido"
    assert details["description"]["value"] == "Descrição candidata"
    assert details["description"]["provider"] == "cbl"
    assert calls == [book.isbn]
    book.refresh_from_db()
    assert book.description == ""


def test_csv_report_empty_no_results_has_header_and_summary(tmp_path, monkeypatch):
    from library import providers

    library = Library.objects.create(name="Casa")
    make_book(library)
    monkeypatch.setattr(providers, "enrich_book", lambda data, lookup=None: data)
    report_path = tmp_path / "report.csv"

    call_command(
        "enrich_books",
        library=library.pk,
        delay=0,
        report_format="csv",
        report_file=str(report_path),
        stdout=StringIO(),
    )

    with report_path.open(newline="") as report_file:
        rows = list(csv.DictReader(report_file))
    details = [row for row in rows if row["record_type"] == "detail"]
    assert len(details) == 11
    assert {row["status"] for row in details} == {"já preenchido", "não encontrado"}
    summary = next(row for row in rows if row["record_type"] == "summary")
    assert summary["mode"] == "preview"
    assert json.loads(summary["summary"])["books_without_new_metadata"] == 1


def test_csv_report_encodes_subject_lists_as_json(tmp_path, monkeypatch):
    from library import providers

    library = Library.objects.create(name="Casa")
    book = make_book(library)
    monkeypatch.setattr(
        providers,
        "enrich_book",
        lambda data, lookup=None: result(data, subjects=["História, crítica", "Ficção"]),
    )
    report_path = tmp_path / "report.csv"
    call_command(
        "enrich_books",
        library=library.pk,
        delay=0,
        report_format="csv",
        report_file=str(report_path),
        stdout=StringIO(),
    )

    with report_path.open(newline="") as report_file:
        rows = list(csv.DictReader(report_file))
    subjects = next(
        row
        for row in rows
        if row["record_type"] == "detail"
        and row["book_id"] == str(book.pk)
        and row["field"] == "subjects"
    )
    assert json.loads(subjects["value"]) == ["História, crítica", "Ficção"]


def test_report_format_and_file_must_be_supplied_together():
    library = Library.objects.create(name="Casa")
    with pytest.raises(CommandError, match="devem ser informados juntos"):
        call_command(
            "enrich_books",
            library=library.pk,
            delay=0,
            report_format="csv",
            stdout=StringIO(),
        )


def test_unknown_author_placeholder_is_eligible_but_never_a_fill(monkeypatch):
    from library import providers
    from library.management.commands.enrich_books import missing_fields

    library = Library.objects.create(name="Casa")
    book = make_book(library, authors=["Autoria desconhecida"])
    calls = []
    monkeypatch.setattr(
        providers,
        "enrich_book",
        lambda data, lookup=None: (
            calls.append(data["isbn"]) or result(data, authors=["Autoria desconhecida"])
        ),
    )

    call_command("enrich_books", library=library.pk, delay=0, apply=True, stdout=StringIO())

    book.refresh_from_db()
    assert calls == [book.isbn]
    assert "authors" in missing_fields(book)
    assert book.authors == ["Autoria desconhecida"]


def test_csv_report_neutralizes_formula_like_book_and_metadata_values(tmp_path, monkeypatch):
    from library import providers

    library = Library.objects.create(name="Casa")
    formula_title = '=HYPERLINK("https://example.invalid")'
    make_book(library, title=formula_title)
    monkeypatch.setattr(
        providers,
        "enrich_book",
        lambda data, lookup=None: result(data, description="=1+1"),
    )
    report_path = tmp_path / "report.csv"
    call_command(
        "enrich_books",
        library=library.pk,
        delay=0,
        report_format="csv",
        report_file=str(report_path),
        stdout=StringIO(),
    )

    with report_path.open(newline="") as report_file:
        rows = list(csv.DictReader(report_file))
    title = next(row for row in rows if row["record_type"] == "detail" and row["field"] == "title")
    description = next(
        row for row in rows if row["record_type"] == "detail" and row["field"] == "description"
    )
    assert title["title"] == "'" + formula_title
    assert description["value"] == "'=1+1"


def test_provider_http_429_is_counted_and_reported_as_error(tmp_path, monkeypatch):
    from library import providers

    library = Library.objects.create(name="Casa")
    book = make_book(library)

    def rate_limited(data, lookup=None):
        url = "https://www.googleapis.com/books/v1/volumes"
        monkeypatch.setattr(
            providers,
            "bounded_get",
            lambda request_url, **kwargs: httpx.Response(
                429, request=httpx.Request("GET", request_url)
            ),
        )
        lookup.json(url, {"q": f"isbn:{book.isbn}"})
        lookup.provider_outcomes["google"] = "failure"
        return data

    monkeypatch.setattr(providers, "enrich_book", rate_limited)
    report_path = tmp_path / "report.json"
    call_command(
        "enrich_books",
        library=library.pk,
        delay=0,
        report_format="json",
        report_file=str(report_path),
        stdout=StringIO(),
    )

    report = json.loads(report_path.read_text())
    assert report["summary"]["providers"]["google"]["failures"] == 1
    description = next(
        row
        for row in report["details"]
        if row["book_id"] == book.pk and row["field"] == "description"
    )
    assert description["status"] == "erro"
    assert description["provider"] == "google"


def test_report_contains_only_requested_library(tmp_path, monkeypatch):
    from library import providers

    library = Library.objects.create(name="Casa")
    other = Library.objects.create(name="Outra")
    book = make_book(library)
    foreign = make_book(other)
    monkeypatch.setattr(providers, "enrich_book", lambda data, lookup=None: data)
    report_path = tmp_path / "report.json"
    call_command(
        "enrich_books",
        library=library.pk,
        delay=0,
        report_format="json",
        report_file=str(report_path),
        stdout=StringIO(),
    )

    report = json.loads(report_path.read_text())
    ids = {row["book_id"] for row in report["details"]}
    assert ids == {book.pk}
    assert foreign.pk not in ids


def test_apply_report_counts_only_fields_persisted_after_locked_reread(tmp_path, monkeypatch):
    from library import providers

    library = Library.objects.create(name="Casa")
    book = make_book(library)

    def concurrent_edit(data, lookup=None):
        Book.objects.filter(pk=book.pk).update(description="Edição concorrente")
        return result(data, description="Candidata", subjects=["Ficção"])

    preview_path = tmp_path / "preview.json"
    monkeypatch.setattr(
        providers,
        "enrich_book",
        lambda data, lookup=None: result(data, description="Candidata", subjects=["Ficção"]),
    )
    call_command(
        "enrich_books",
        library=library.pk,
        delay=0,
        report_format="json",
        report_file=str(preview_path),
        stdout=StringIO(),
    )

    preview = json.loads(preview_path.read_text())
    preview_description = next(
        row
        for row in preview["details"]
        if row["book_id"] == book.pk and row["field"] == "description"
    )
    assert preview_description["status"] == "seria preenchido"
    book.refresh_from_db()
    assert book.description == ""

    monkeypatch.setattr(providers, "enrich_book", concurrent_edit)
    report_path = tmp_path / "report.json"

    call_command(
        "enrich_books",
        library=library.pk,
        delay=0,
        apply=True,
        report_format="json",
        report_file=str(report_path),
        stdout=StringIO(),
    )

    report = json.loads(report_path.read_text())
    details = {row["field"]: row for row in report["details"] if row["book_id"] == book.pk}
    assert report["mode"] == "apply"
    assert report["summary"]["fields_filled"]["description"] == 0
    assert report["summary"]["fields_filled"]["subjects"] == 1
    assert details["description"]["status"] == "erro"
    assert details["description"]["value"] is None
    assert details["subjects"]["status"] == "preenchido"
