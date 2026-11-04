"""Read-only database probe using an isolated, short-lived connection."""

from django.db import DatabaseError, connection


def database_ready() -> bool:
    probe = connection.copy()
    probe.settings_dict["OPTIONS"]["connect_timeout"] = 3
    try:
        probe.set_autocommit(False)
        with probe.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '2s'")
            cursor.execute("SET LOCAL lock_timeout = '1s'")
            cursor.execute("SELECT EXISTS (SELECT 1 FROM library_library LIMIT 1)")
            cursor.fetchone()
        probe.rollback()
        return True
    except DatabaseError:
        return False
    finally:
        probe.close()
