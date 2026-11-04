from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from library.models import Library, Membership, User


class Command(BaseCommand):
    help = "Provisiona a biblioteca inicial e associa usuários já autenticados da allowlist."

    def add_arguments(self, parser):
        parser.add_argument("--name", default="Nossa biblioteca")

    def handle(self, *args, **options):
        if not settings.ALLOWED_EMAILS or settings.ADMIN_EMAIL not in settings.ALLOWED_EMAILS:
            raise CommandError("Configure ALLOWED_EMAILS e ADMIN_EMAIL antes de provisionar.")
        library = Library.objects.first() or Library.objects.create(name=options["name"])
        for user in User.objects.filter(email__in=settings.ALLOWED_EMAILS):
            Membership.objects.get_or_create(user=user, library=library)
            user.is_staff = user.email.lower() == settings.ADMIN_EMAIL
            user.is_superuser = user.is_staff
            user.save(update_fields=["is_staff", "is_superuser"])
        self.stdout.write(
            self.style.SUCCESS("Biblioteca provisionada. As contas entram via Google.")
        )
