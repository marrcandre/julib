from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from library.models import Library, Membership, User


class Command(BaseCommand):
    help = "Provisiona a biblioteca inicial e associa usuários existentes da allowlist."

    def add_arguments(self, parser):
        parser.add_argument("--name", default="Nossa biblioteca")

    def handle(self, *args, **options):
        if not settings.ALLOWED_EMAILS or settings.ADMIN_EMAIL not in settings.ALLOWED_EMAILS:
            raise CommandError("Configure ALLOWED_EMAILS e ADMIN_EMAIL antes de provisionar.")
        library = Library.objects.order_by("pk").first() or Library.objects.create(
            name=options["name"]
        )
        for user in User.objects.filter(email__in=settings.ALLOWED_EMAILS):
            is_admin = user.email.lower() == settings.ADMIN_EMAIL
            membership, _ = Membership.objects.get_or_create(
                user=user,
                library=library,
                defaults={"role": Membership.ROLE_ADMIN if is_admin else Membership.ROLE_MEMBER},
            )
            if is_admin and membership.role != Membership.ROLE_ADMIN:
                membership.role = Membership.ROLE_ADMIN
                membership.save(update_fields=["role"])
            user.is_staff = is_admin
            user.is_superuser = user.is_staff
            update_fields = ["is_staff", "is_superuser"]
            if is_admin and not user.can_create_libraries:
                user.can_create_libraries = True
                update_fields.append("can_create_libraries")
            user.save(update_fields=update_fields)
        self.stdout.write(
            self.style.SUCCESS("Biblioteca provisionada. As contas entram via Google.")
        )
