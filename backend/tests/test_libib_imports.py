import csv
import io
from concurrent.futures import ThreadPoolExecutor

import pytest
from django.core.exceptions import ValidationError

from library.libib_imports import (
    libib_details,
    parse_libib_files,
    preview_libib,
    process_libib_rows,
)
from library.models import Book, Copy, ImportReceipt, Library, Tag

pytestmark = pytest.mark.django_db

HEADER = (
    "id,item_type,title,creators,first_name,last_name,collection,ean_isbn13,upc_isbn10,"
    "description,publisher,publish_date,group,tags,notes,price,length,number_of_discs,"
    "number_of_players,age_group,ensemble,aspect_ratio,esrb,rating,review,review_date,"
    "status,began,completed,added,copies"
)


def libib_csv(rows, *, bom=False):
    content = HEADER + "\n" + "\n".join(rows) + "\n"
    return ("\ufeff" + content if bom else content).encode("utf-8")


def test_parser_maps_book_and_preserves_complex_creator_names():
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(HEADER.split(","))
    row = [""] * 31
    row[0:4] = ["1", "book", "The, Book", "Doe, Jane"]
    row[6:9] = ["Reading", "9780306406157", ""]
    row[9:14] = ["summary", "Press", "1999-02-03", "Group", "History, Reference"]
    row[14:17] = ["private notes", "12", "321"]
    row[30] = "2"
    writer.writerow(row)
    result = parse_libib_files([("library.csv", output.getvalue().encode())])

    row = result.files[0].rows[0]
    assert row["data"]["title"] == "The, Book"
    assert row["data"]["authors"] == ["Doe, Jane"]
    assert row["data"]["isbn"] == "9780306406157"
    assert row["data"]["year"] == "1999"
    assert row["data"]["page_count"] == 321
    assert row["data"]["copies"] == 2
    assert row["data"]["collection"] == "Reading"
    assert row["data"]["tag_names"] == ["History", "Reference"]
    assert "notes" in row["data"]["not_imported_fields"]


def test_parser_accepts_utf8_bom_multiline_fields_unknown_columns_and_empty_cells():
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(HEADER.split(",") + ["custom_field"])
    row = [""] * 31
    row[1] = "book"
    row[2] = "A title"
    row[3] = "Author"
    row[6] = "Collection"
    row[9] = "First line\nsecond line, with comma"
    row[30] = "1"
    writer.writerow(row + ["extra"])

    result = parse_libib_files([("export.csv", ("\ufeff" + output.getvalue()).encode())])

    data = result.files[0].rows[0]["data"]
    assert result.files[0].unknown_columns == ["custom_field"]
    assert data["title"] == "A title"
    assert data["isbn"] == ""
    assert data["copies"] == 1
    assert "description" in data["not_imported_fields"]


def test_invalid_utf8_is_a_friendly_validation_error():
    parsed = parse_libib_files([("bad.csv", b"\xff")])
    assert "UTF-8" in parsed.files[0].errors[0]


def test_comma_separated_creators_are_split_only_when_names_are_unambiguous():
    content = _valid_export(creators="Jane Doe, John Smith")
    parsed = parse_libib_files([("authors.csv", content)])

    assert parsed.files[0].rows[0]["data"]["authors"] == ["Jane Doe", "John Smith"]


def test_invalid_isbn13_falls_back_to_valid_isbn10():
    content = _valid_export(isbn="9780306406158")
    text = content.decode().replace(",9780306406158,,", ",9780306406158,0306406152,")
    parsed = parse_libib_files([("isbn.csv", text.encode())])

    assert parsed.files[0].rows[0]["data"]["isbn"] == "9780306406157"


def test_valid_isbn10_is_normalized_and_invalid_isbns_fall_back_to_blank():
    valid = _valid_export(isbn="", isbn10="0306406152")
    normalized = parse_libib_files([("ten.csv", valid)]).files[0].rows[0]["data"]["isbn"]
    invalid = _valid_export(isbn="1234567890123", isbn10="1234567890")
    invalid_row = parse_libib_files([("bad-isbn.csv", invalid)]).files[0].rows[0]
    invalid_data = invalid_row["data"]

    assert normalized == "9780306406157"
    assert invalid_data["isbn"] == ""
    assert any("inválidos" in warning for warning in invalid_row["warnings"])


def test_invalid_dates_and_page_counts_are_omitted_with_warnings():
    content = _valid_export(publish_date="not-a-date", length="not-pages")
    parsed = parse_libib_files([("date.csv", content)]).files[0].rows[0]
    data = parsed["data"]

    assert data["year"] == ""
    assert data["page_count"] is None
    assert any("ano" in warning for warning in parsed["warnings"])
    assert any("páginas inválido" in warning for warning in parsed["warnings"])


def test_file_count_size_duplicate_content_and_record_limits_are_enforced():
    content = _valid_export()
    with pytest.raises(ValidationError, match="5 arquivos"):
        parse_libib_files([(str(index), content) for index in range(6)])
    oversized = parse_libib_files([("large.csv", b"x" * (5 * 1024 * 1024 + 1))])
    assert "5 MiB" in oversized.files[0].errors[0]
    duplicated = parse_libib_files([("one.csv", content), ("renamed.csv", content)])
    assert duplicated.files[0].errors == []
    assert "mais de uma vez" in duplicated.files[1].errors[0]
    row = content.splitlines()[1]
    oversized = parse_libib_files(
        [("large-rows.csv", HEADER.encode() + b"\n" + (row + b"\n") * 5001)]
    )
    assert "5.000 registros" in oversized.files[0].errors[0]


def test_short_truncated_record_is_rejected():
    parsed = parse_libib_files([("short.csv", (HEADER + "\nbook,Title\n").encode())])
    assert "quantidade incorreta" in parsed.files[0].errors[0]


def test_invalid_header_is_rejected_without_technical_error():
    parsed = parse_libib_files([("bad.csv", b"Title,Author\nBook,Writer\n")])
    assert "Cabeçalho" in parsed.files[0].errors[0]


def test_malformed_csv_and_truncated_records_are_rejected():
    parsed = parse_libib_files([("bad.csv", (HEADER + '\n1,book,"unterminated').encode())])
    assert "CSV" in parsed.files[0].errors[0]


def test_a_bad_file_does_not_discard_valid_sibling_files():
    parsed = parse_libib_files(
        [
            ("bad.csv", (HEADER + '\n1,book,"unterminated').encode()),
            ("good.csv", _valid_export(copies="1")),
        ]
    )

    assert parsed.files[0].errors
    assert parsed.files[0].rows == []
    assert parsed.files[1].errors == []
    assert len(parsed.files[1].rows) == 1


def test_preview_and_processing_continue_for_valid_files_when_another_file_fails():
    library = Library.objects.create(name="Casa")
    session = preview_libib(
        library,
        [
            ("bad.csv", (HEADER + '\n1,book,"unterminated').encode()),
            ("good.csv", _valid_export(copies="1")),
        ],
    )
    details = libib_details(library, session.pk)
    valid_row = session.rows.get()

    assert details["files"][0]["error"]
    assert details["files"][0]["total_rows"] == 0
    assert details["files"][1]["error"] == ""
    assert len(details["rows"]) == 1
    result = process_libib_rows(library, session.pk, [{"id": valid_row.pk, "action": "import"}])

    assert result[0]["result"] == "created"


@pytest.mark.parametrize("copies", ["", "0", "-1", "1.5", "101", "many"])
def test_invalid_copy_count_marks_record_unimportable(copies):
    row = [""] * 31
    row[1], row[2], row[3], row[6], row[30] = "book", "Title", "Author", "Shelf", copies
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(HEADER.split(","))
    writer.writerow(row)

    parsed = parse_libib_files([("export.csv", output.getvalue().encode())])

    assert parsed.files[0].rows[0]["status"] == "invalid"
    assert parsed.files[0].rows[0]["errors"]


def test_non_book_and_missing_title_are_visible_as_incompatible_or_invalid():
    rows = []
    for kind, title in [("dvd", "Film"), ("book", "")]:
        row = [""] * 31
        row[1], row[2], row[3], row[30] = kind, title, "Author", "1"
        rows.append(row)
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(HEADER.split(","))
    writer.writerows(rows)

    parsed = parse_libib_files([("export.csv", output.getvalue().encode())])

    assert [item["status"] for item in parsed.files[0].rows] == ["incompatible", "invalid"]


def _valid_export(
    *,
    libib_id="",
    title="Book",
    creators="Author",
    copies="2",
    collection="Shelf",
    isbn="9780306406157",
    isbn10="",
    publish_date="",
    length="",
):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(HEADER.split(","))
    row = [""] * 31
    row[0], row[1:4] = libib_id, ["book", title, creators]
    row[6], row[7], row[8], row[11], row[16], row[30] = (
        collection,
        isbn,
        isbn10,
        publish_date,
        length,
        copies,
    )
    row[13] = "New tag"
    writer.writerow(row)
    return output.getvalue().encode()


def test_preview_persists_multiple_files_and_processing_creates_requested_copies_and_tags():
    library = Library.objects.create(name="Casa")
    session = preview_libib(
        library,
        [
            ("one.csv", _valid_export()),
            ("two.csv", _valid_export(title="Other", collection="Study")),
        ],
    )
    rows = list(session.rows.select_related("import_file").order_by("position"))

    assert session.source == "libib"
    assert [row.import_file.collection for row in rows] == ["Shelf", "Study"]
    assert len({row.source_key for row in rows}) == 2
    assert Book.objects.count() == Copy.objects.count() == Tag.objects.count() == 0

    results = process_libib_rows(
        library, session.pk, [{"id": row.pk, "action": "import"} for row in rows]
    )

    assert [result["result"] for result in results] == ["created", "existing"]
    assert Book.objects.filter(library=library).count() == 1
    assert Copy.objects.filter(library=library).count() == 2
    assert Tag.objects.filter(library=library, name="New tag").count() == 1
    assert ImportReceipt.objects.filter(library=library).count() == 1


def test_same_file_different_name_and_session_does_not_add_copies_again():
    library = Library.objects.create(name="Casa")
    content = _valid_export(copies="2")
    first = preview_libib(library, [("first.csv", content)])
    first_row = first.rows.get()
    process_libib_rows(library, first.pk, [{"id": first_row.pk, "action": "import"}])
    second = preview_libib(library, [("renamed.csv", content)])
    second_row = second.rows.get()

    results = process_libib_rows(library, second.pk, [{"id": second_row.pk, "action": "import"}])

    assert results == [{"id": second_row.pk, "result": "already_imported"}]
    assert Copy.objects.filter(library=library).count() == 2
    assert ImportReceipt.objects.filter(library=library).count() == 1


def test_receipt_identity_does_not_depend_on_libib_id_or_filename():
    library = Library.objects.create(name="Casa")
    first = preview_libib(library, [("first.csv", _valid_export(libib_id="unstable-1"))])
    first_row = first.rows.get()
    process_libib_rows(library, first.pk, [{"id": first_row.pk, "action": "import"}])
    second = preview_libib(library, [("renamed.csv", _valid_export(libib_id="unstable-2"))])
    second_row = second.rows.get()

    result = process_libib_rows(library, second.pk, [{"id": second_row.pk, "action": "import"}])

    assert first.files.get().sha256 != second.files.get().sha256
    assert first_row.row_fingerprint == second_row.row_fingerprint
    assert first_row.source_key == second_row.source_key
    assert result == [{"id": second_row.pk, "result": "already_imported"}]
    assert Copy.objects.filter(library=library).count() == 2


def test_receipt_identity_is_stable_when_rows_are_reordered():
    library = Library.objects.create(name="Casa")
    first_export = _valid_export(title="Primeiro", isbn="", copies="1")
    second_export = _valid_export(title="Segundo", isbn="", copies="1")
    first_lines = first_export.decode().splitlines()
    second_lines = second_export.decode().splitlines()
    first = preview_libib(
        library,
        [
            (
                "first.csv",
                (first_lines[0] + "\n" + first_lines[1] + "\n" + second_lines[1] + "\n").encode(),
            )
        ],
    )
    first_rows = list(first.rows.order_by("position"))
    process_libib_rows(
        library,
        first.pk,
        [{"id": row.pk, "action": "import"} for row in first_rows],
    )
    reordered = preview_libib(
        library,
        [
            (
                "reordered.csv",
                (first_lines[0] + "\n" + second_lines[1] + "\n" + first_lines[1] + "\n").encode(),
            )
        ],
    )
    reordered_rows = list(reordered.rows.order_by("position"))

    assert {row.data["data"]["title"]: row.source_key for row in first_rows} == {
        row.data["data"]["title"]: row.source_key for row in reordered_rows
    }
    results = process_libib_rows(
        library,
        reordered.pk,
        [{"id": row.pk, "action": "import"} for row in reordered_rows],
    )

    assert [result["result"] for result in results] == ["already_imported", "already_imported"]
    assert Book.objects.filter(library=library).count() == 2
    assert Copy.objects.filter(library=library).count() == 2


def test_identical_repeated_records_keep_distinct_occurrences_without_duplicate_copies():
    library = Library.objects.create(name="Casa")
    export = _valid_export(copies="2")
    header, row = export.splitlines()
    repeated = preview_libib(
        library, [("repeated.csv", header + b"\n" + row + b"\n" + row + b"\n")]
    )
    rows = list(repeated.rows.order_by("position"))

    assert rows[0].source_key != rows[1].source_key
    first_result = process_libib_rows(
        library, repeated.pk, [{"id": item.pk, "action": "import"} for item in rows]
    )
    later = preview_libib(
        library, [("repeated-renamed.csv", header + b"\n" + row + b"\n" + row + b"\n")]
    )
    later_rows = list(later.rows.order_by("position"))
    later_results = process_libib_rows(
        library, later.pk, [{"id": item.pk, "action": "import"} for item in later_rows]
    )

    assert [item["result"] for item in first_result] == ["created", "existing"]
    assert [item["result"] for item in later_results] == ["already_imported", "existing"]
    assert Book.objects.filter(library=library).count() == 1
    assert Copy.objects.filter(library=library).count() == 2


def test_identical_repeated_records_without_isbn_are_warned_and_idempotent_on_reimport():
    library = Library.objects.create(name="Casa")
    export = _valid_export(isbn="", copies="1")
    header, row = export.splitlines()
    content = header + b"\n" + row + b"\n" + row + b"\n"
    first = preview_libib(library, [("same.csv", content)])
    first_rows = list(first.rows.order_by("position"))
    preview = libib_details(library, first.pk)

    assert first_rows[0].source_key != first_rows[1].source_key
    assert all(item["data"]["possible_duplicate"] for item in preview["rows"])
    created = process_libib_rows(
        library, first.pk, [{"id": item.pk, "action": "import"} for item in first_rows]
    )
    second = preview_libib(library, [("renamed.csv", content)])
    second_rows = list(second.rows.order_by("position"))
    replay = process_libib_rows(
        library, second.pk, [{"id": item.pk, "action": "import"} for item in second_rows]
    )

    assert [item["result"] for item in created] == ["created", "created"]
    assert [item["result"] for item in replay] == ["already_imported", "already_imported"]
    assert Book.objects.filter(library=library).count() == 2
    assert Copy.objects.filter(library=library).count() == 2
    assert ImportReceipt.objects.filter(library=library).count() == 2


def test_changed_file_matching_isbn_needs_explicit_copy_decision():
    library = Library.objects.create(name="Casa")
    first = preview_libib(library, [("one.csv", _valid_export(copies="2"))])
    process_libib_rows(library, first.pk, [{"id": first.rows.get().pk, "action": "import"}])
    changed = preview_libib(library, [("changed.csv", _valid_export(title="Updated", copies="3"))])
    changed_row = changed.rows.get()

    result = process_libib_rows(library, changed.pk, [{"id": changed_row.pk, "action": "copy"}])

    assert result[0]["result"] == "copied"
    assert Copy.objects.filter(library=library).count() == 5
    assert ImportReceipt.objects.filter(library=library).count() == 2


def test_isbn_match_is_scoped_to_the_current_library():
    library = Library.objects.create(name="Casa")
    other = Library.objects.create(name="Outra")
    Book.objects.create(library=other, title="Book", authors=["Author"], isbn="9780306406157")
    session = preview_libib(library, [("one.csv", _valid_export(copies="1"))])
    row = session.rows.get()

    assert libib_details(library, session.pk)["rows"][0]["data"]["existing"] is False
    result = process_libib_rows(library, session.pk, [{"id": row.pk, "action": "import"}])

    assert result[0]["result"] == "created"
    assert Book.objects.filter(library=library, isbn="9780306406157").count() == 1
    assert Book.objects.filter(library=other, isbn="9780306406157").count() == 1


def test_metadata_only_match_is_a_suggestion_and_never_an_automatic_merge():
    library = Library.objects.create(name="Casa")
    Book.objects.create(library=library, title="Book", authors=["Author"])
    session = preview_libib(library, [("one.csv", _valid_export(isbn="", copies="1"))])
    row = session.rows.get()

    preview = libib_details(library, session.pk)["rows"][0]["data"]
    assert preview["existing"] is False
    assert preview["possible_duplicate"] is True

    result = process_libib_rows(library, session.pk, [{"id": row.pk, "action": "import"}])

    assert result[0]["result"] == "created"
    assert Book.objects.filter(library=library, title="Book").count() == 2


def test_failed_copy_creation_rolls_back_book_copies_and_receipt(monkeypatch):
    library = Library.objects.create(name="Casa")
    session = preview_libib(library, [("one.csv", _valid_export(copies="2"))])
    row = session.rows.get()
    original_add_copy = __import__("library.libib_imports", fromlist=["add_copy"]).add_copy
    calls = 0

    def fail_after_one_copy(*args, **kwargs):
        nonlocal calls
        calls += 1
        copy = original_add_copy(*args, **kwargs)
        if calls == 2:
            raise ValidationError("Falha simulada de persistência.")
        return copy

    monkeypatch.setattr("library.libib_imports.add_copy", fail_after_one_copy)

    result = process_libib_rows(library, session.pk, [{"id": row.pk, "action": "import"}])

    assert result[0]["result"] == "error"
    assert not Book.objects.filter(library=library).exists()
    assert not Copy.objects.filter(library=library).exists()
    assert not ImportReceipt.objects.filter(library=library).exists()

    monkeypatch.undo()
    retried = process_libib_rows(library, session.pk, [{"id": row.pk, "action": "import"}])

    assert retried[0]["result"] == "created"
    assert Book.objects.filter(library=library).count() == 1
    assert Copy.objects.filter(library=library).count() == 2
    assert ImportReceipt.objects.filter(library=library).count() == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_processing_of_same_file_in_two_sessions_creates_only_one_receipt():
    from django.db import close_old_connections

    library = Library.objects.create(name="Casa")
    content = _valid_export(copies="2")
    sessions = [preview_libib(library, [(f"{index}.csv", content)]) for index in range(2)]
    row_ids = [session.rows.get().pk for session in sessions]

    def process(index):
        close_old_connections()
        try:
            return process_libib_rows(
                library, sessions[index].pk, [{"id": row_ids[index], "action": "import"}]
            )
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(process, [0, 1]))

    assert sorted(result[0]["result"] for result in results) == ["already_imported", "created"]
    assert Book.objects.filter(library=library).count() == 1
    assert Copy.objects.filter(library=library).count() == 2
    assert ImportReceipt.objects.filter(library=library).count() == 1
