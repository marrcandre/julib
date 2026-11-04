from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from library.models import ImportSession


class Command(BaseCommand):
    help = "Remove sessões e linhas de importação expiradas, preservando livros/exemplares."

    def handle(self, *args, **options):
        count, _ = ImportSession.objects.filter(
            created_at__lt=timezone.now() - timedelta(days=7)
        ).delete()
        self.stdout.write(f"{count} registros temporários removidos.")
