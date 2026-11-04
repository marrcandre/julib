import pytest
from django.db import OperationalError, connection
from django.db.backends.postgresql.base import DatabaseWrapper
from django.test import Client

pytestmark = pytest.mark.django_db(transaction=True)


def test_readiness_reads_database_without_exposing_data_and_disables_cache():
    response = Client().get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "no-store" in response["Cache-Control"]


def test_database_failure_is_503_without_details_and_liveness_still_works(monkeypatch):
    def broken(*args, **kwargs):
        raise OperationalError("private-database-password-and-host")

    monkeypatch.setattr(DatabaseWrapper, "get_new_connection", broken)
    client = Client()
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    assert "private-database" not in response.content.decode()
    assert "no-store" in response["Cache-Control"]
    assert client.get("/api/v1/health").json() == {"status": "ok"}


def test_readiness_times_out_on_locked_table_and_recovers_after_release():
    blocker = connection.copy()
    try:
        blocker.set_autocommit(False)
        with blocker.cursor() as cursor:
            cursor.execute("LOCK TABLE library_library IN ACCESS EXCLUSIVE MODE")
        assert Client().get("/api/v1/health/ready").status_code == 503
        blocker.rollback()
    finally:
        blocker.close()
    assert Client().get("/api/v1/health/ready").status_code == 200


def test_head_monitor_checks_database_with_same_status_and_no_body(monkeypatch):
    client = Client()
    response = client.head("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.content == b""
    assert "no-store" in response["Cache-Control"]

    def broken(*args, **kwargs):
        raise OperationalError("unavailable")

    monkeypatch.setattr(DatabaseWrapper, "get_new_connection", broken)
    assert client.head("/api/v1/health/ready").status_code == 503
