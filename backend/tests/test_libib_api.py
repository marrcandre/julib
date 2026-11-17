import csv
import io
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from library.models import Copy, ImportFile, ImportSession, Library, Membership

pytestmark = pytest.mark.django_db

HEADER = (
    "id,item_type,title,creators,first_name,last_name,collection,ean_isbn13,upc_isbn10,"
    "description,publisher,publish_date,group,tags,notes,price,length,number_of_discs,"
    "number_of_players,age_group,ensemble,aspect_ratio,esrb,rating,review,review_date,"
    "status,began,completed,added,copies"
)


def export(title, collection, copies):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(HEADER.split(","))
    row = [""] * 31
    row[1:4] = ["book", title, "Author"]
    row[6], row[30] = collection, str(copies)
    writer.writerow(row)
    return output.getvalue().encode()


def test_libib_api_uploads_multiple_files_previews_then_processes_selected_rows(client, member):
    library = Library.objects.create(name="Minha biblioteca")
    Membership.objects.create(user=member, library=library)

    response = client.post(
        "/api/v1/imports/libib/preview",
        {
            "files": [
                SimpleUploadedFile("first.csv", export("First", "Fiction", 2), "text/csv"),
                SimpleUploadedFile("second.csv", export("Second", "Study", 1), "text/csv"),
            ]
        },
        HTTP_X_LIBRARY_ID=str(library.pk),
    )

    assert response.status_code == 200, response.content
    session_id = response.json()["id"]
    details = client.get(f"/api/v1/imports/libib/{session_id}", HTTP_X_LIBRARY_ID=str(library.pk))
    assert len(details.json()["files"]) == 2
    assert [row["data"]["collection"] for row in details.json()["rows"]] == [
        "Fiction",
        "Study",
    ]
    assert Copy.objects.filter(library=library).count() == 0

    row = details.json()["rows"][0]
    processed = client.post(
        f"/api/v1/imports/libib/{session_id}/process",
        data={"actions": [{"id": row["id"], "action": "import"}]},
        content_type="application/json",
        HTTP_X_LIBRARY_ID=str(library.pk),
    )

    assert processed.status_code == 200
    assert processed.json()[0]["copies_added"] == 2
    assert Copy.objects.filter(library=library).count() == 2


def test_libib_session_is_not_visible_from_another_library(client, member):
    library = Library.objects.create(name="Minha biblioteca")
    Membership.objects.create(user=member, library=library)
    response = client.post(
        "/api/v1/imports/libib/preview",
        {"files": [SimpleUploadedFile("first.csv", export("First", "Fiction", 1))]},
        HTTP_X_LIBRARY_ID=str(library.pk),
    )
    session_id = response.json()["id"]
    other = Library.objects.create(name="Outra")

    denied = client.get(f"/api/v1/imports/libib/{session_id}", HTTP_X_LIBRARY_ID=str(other.pk))

    assert denied.status_code == 403


def test_malformed_file_is_reported_without_rejecting_valid_sibling(client, member):
    library = Library.objects.create(name="Minha biblioteca")
    Membership.objects.create(user=member, library=library)
    response = client.post(
        "/api/v1/imports/libib/preview",
        {
            "files": [
                SimpleUploadedFile("bad.csv", b"Title,Author\nBook,Writer\n"),
                SimpleUploadedFile("good.csv", export("Good", "Fiction", 1)),
            ]
        },
        HTTP_X_LIBRARY_ID=str(library.pk),
    )

    assert response.status_code == 200
    details = client.get(
        f"/api/v1/imports/libib/{response.json()['id']}", HTTP_X_LIBRARY_ID=str(library.pk)
    ).json()
    assert details["files"][0]["status"] == "error"
    assert "Cabeçalho" in details["files"][0]["error"]
    assert details["files"][1]["status"] == "ready"
    assert [row["data"]["title"] for row in details["rows"]] == ["Good"]


def test_libib_session_details_allow_valid_session(client, member):
    library = Library.objects.create(name="Minha biblioteca")
    Membership.objects.create(user=member, library=library)
    response = client.post(
        "/api/v1/imports/libib/preview",
        {"files": [SimpleUploadedFile("first.csv", export("First", "Fiction", 1))]},
        HTTP_X_LIBRARY_ID=str(library.pk),
    )

    details = client.get(
        f"/api/v1/imports/libib/{response.json()['id']}", HTTP_X_LIBRARY_ID=str(library.pk)
    )

    assert details.status_code == 200


def test_libib_session_details_reject_expired_session_without_cleanup(client, member):
    library = Library.objects.create(name="Minha biblioteca")
    Membership.objects.create(user=member, library=library)
    session = ImportSession.objects.create(library=library, source=ImportSession.SOURCE_LIBIB)
    ImportFile.objects.create(
        session=session,
        position=1,
        original_name="expired.csv",
        sha256="a" * 64,
        status="error",
        error="Cabeçalho inválido.",
    )
    ImportSession.objects.filter(pk=session.pk).update(
        created_at=timezone.now() - timedelta(days=8)
    )

    details = client.get(f"/api/v1/imports/libib/{session.pk}", HTTP_X_LIBRARY_ID=str(library.pk))

    assert details.status_code == 400
    assert "expirada" in details.json()["detail"].lower()


def test_libib_session_details_reject_missing_session(client, member):
    library = Library.objects.create(name="Minha biblioteca")
    Membership.objects.create(user=member, library=library)

    details = client.get("/api/v1/imports/libib/999999", HTTP_X_LIBRARY_ID=str(library.pk))

    assert details.status_code == 400
    assert "não encontrado" in details.json()["detail"].lower()
