"""Limit Django tables to its trusted backend role; never to Supabase client roles."""

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction


class Command(BaseCommand):
    help = "Protege as tabelas Django contra Data API pública e concede DML ao runtime."

    def add_arguments(self, parser):
        parser.add_argument("--role", default="julib_app")

    @transaction.atomic
    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            raise CommandError("Este comando exige PostgreSQL.")
        role = options["role"]
        quote = connection.ops.quote_name
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT rolsuper, rolcreaterole, rolcreatedb, rolbypassrls FROM pg_roles WHERE rolname=%s",
                [role],
            )
            privileges = cursor.fetchone()
            if privileges is None or any(privileges):
                raise CommandError(
                    "Role de runtime inexistente ou com privilégios administrativos."
                )
            cursor.execute("SELECT rolname FROM pg_roles WHERE rolname IN ('anon','authenticated')")
            public_roles = [quote(row[0]) for row in cursor.fetchall()] + ["PUBLIC"]
            client_roles = ", ".join(public_roles)
            # Applies to the migration owner; new tables start without public grants.
            cursor.execute(
                f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM {client_roles}"
            )
            cursor.execute(
                f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM {client_roles}"
            )
            tables = {
                model._meta.db_table
                for model in apps.get_models(include_auto_created=True)
                if model._meta.managed
            }
            tables.add("django_migrations")
            present = set(connection.introspection.table_names(cursor))
            secured = 0
            for table in sorted(tables & present):
                qualified = "public." + quote(table)
                cursor.execute(f"REVOKE ALL ON TABLE {qualified} FROM {client_roles}")
                cursor.execute(f"ALTER TABLE {qualified} ENABLE ROW LEVEL SECURITY")
                cursor.execute(
                    "SELECT 1 FROM pg_policies WHERE schemaname=%s AND tablename=%s AND policyname=%s",
                    ["public", table, "julib_backend_access"],
                )
                if not cursor.fetchone():
                    cursor.execute(
                        f"CREATE POLICY julib_backend_access ON {qualified} FOR ALL TO {quote(role)} USING (true) WITH CHECK (true)"
                    )
                cursor.execute(
                    f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {qualified} TO {quote(role)}"
                )
                secured += 1
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {quote(role)}")
            # This project is dedicated to Julib; sequences are owned by its migrations.
            cursor.execute(
                f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {quote(role)}"
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"{secured} tabelas Django protegidas; runtime sem privilégios de DDL."
            )
        )
