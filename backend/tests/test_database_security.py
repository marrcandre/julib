import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

pytestmark = pytest.mark.django_db


def test_security_setup_rejects_unknown_runtime_role():
    with pytest.raises(CommandError, match="Role de runtime"):
        call_command("secure_database", role="julib_nonexistent_runtime")


def test_runtime_role_has_dml_without_public_access():
    from uuid import uuid4

    from django.db import connection
    from psycopg import sql

    from library.models import Library

    role = "julib_test_" + uuid4().hex[:12]
    with connection.cursor() as cursor:
        cursor.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(role)))
    library = Library.objects.create(name="Role test")
    call_command("secure_database", role=role)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relrowsecurity FROM pg_class WHERE oid=%s::regclass", ["library_library"]
        )
        assert cursor.fetchone()[0] is True
        cursor.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
        try:
            assert Library.objects.get(pk=library.pk).name == "Role test"
            cursor.execute("SELECT has_schema_privilege(current_user,'public','CREATE')")
            assert cursor.fetchone()[0] is False
        finally:
            cursor.execute("RESET ROLE")
