from pathlib import Path
from typing import Any

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from library.imports import fill_goodreads_pages
from library.models import Library


class Command(BaseCommand):
    help = "Preenche páginas ausentes por ID Goodreads; padrão é somente prévia."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--library", type=int, required=True)
        parser.add_argument("--csv", required=True)
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            library = Library.objects.get(pk=options["library"])
            count = fill_goodreads_pages(
                library, Path(options["csv"]).read_bytes(), apply=options["apply"]
            )
        except (Library.DoesNotExist, OSError, UnicodeError, ValidationError) as exc:
            raise CommandError(
                "Não foi possível processar o CSV ou localizar a biblioteca."
            ) from exc
        action = "Atualizados" if options["apply"] else "Elegíveis (prévia)"
        self.stdout.write(f"{action}: {count}")
