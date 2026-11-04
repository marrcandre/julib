import time

import httpx
from django.core.management.base import BaseCommand

from library.cover_lookup import lookup_cover
from library.models import Book, Library


class Command(BaseCommand):
    help = "Busca capas faltantes sem substituir metadados nem capas existentes."

    def add_arguments(self, parser):
        parser.add_argument("--library", type=int, required=True)
        parser.add_argument("--limit", type=int, default=5000)
        parser.add_argument("--delay", type=float, default=1.1)

    def handle(self, *args, **options):
        library = Library.objects.get(pk=options["library"])
        books = list(
            Book.objects.filter(library=library, cover_url="", cover_id="").order_by("pk")[
                : options["limit"]
            ]
        )
        updated = missing = 0
        with httpx.Client(
            headers={"User-Agent": "Julib/0.1 (personal-library; marcoandre@gmail.com)"}
        ) as client:
            for index, book in enumerate(books, 1):
                url = lookup_cover(client, book.isbn, book.title, book.authors)
                if url:
                    updated += Book.objects.filter(
                        pk=book.pk,
                        library=library,
                        cover_url="",
                        cover_id="",
                        isbn=book.isbn,
                        title=book.title,
                        authors=book.authors,
                    ).update(cover_url=url)
                else:
                    missing += 1
                self.stdout.write(
                    f"{index}/{len(books)}: capas adicionadas={updated}; sem correspondência={missing}"
                )
                if options["delay"] > 0 and index < len(books):
                    time.sleep(options["delay"])
        self.stdout.write(
            self.style.SUCCESS(f"Concluído: {updated} capas; {missing} sem correspondência segura.")
        )
