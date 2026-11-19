from typing import Any

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import (
    MaxLengthValidator,
    MaxValueValidator,
    MinLengthValidator,
    MinValueValidator,
)
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .metadata import (
    DESCRIPTION_MAX_LENGTH,
    SUBTITLE_MAX_LENGTH,
    validate_subjects,
)


class User(AbstractUser):
    can_create_libraries = models.BooleanField(default=False, db_default=False)
    catalog_view = models.CharField(
        max_length=10,
        default="covers",
        db_default="covers",
        choices=[(v, v) for v in ("covers", "cards", "list")],
    )
    cover_columns = models.PositiveSmallIntegerField(
        default=7, db_default=7, validators=[MinValueValidator(3), MaxValueValidator(10)]
    )


class Library(models.Model):
    name = models.CharField(max_length=150, blank=True)
    next_number = models.PositiveIntegerField(default=1)

    def __str__(self) -> str:
        return self.name


class LibraryInvite(models.Model):
    library = models.ForeignKey(Library, on_delete=models.CASCADE, related_name="invites")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_library_invites",
    )
    token_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="accepted_library_invites",
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="revoked_library_invites",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["id", "library"], name="unique_invite_library_id"),
            models.CheckConstraint(
                condition=~(Q(accepted_at__isnull=False) & Q(revoked_at__isnull=False)),
                name="invite_cannot_be_accepted_and_revoked",
            ),
            models.CheckConstraint(
                condition=Q(expires_at__gt=models.F("created_at")),
                name="invite_expiry_after_creation",
            ),
        ]


class LibraryCreationInvite(models.Model):
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_library_creation_invites",
    )
    token_hash = models.CharField(max_length=64, unique=True)
    email = models.EmailField(blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="accepted_library_creation_invites",
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="revoked_library_creation_invites",
    )
    created_library = models.OneToOneField(
        Library,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="creation_invite",
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~(Q(accepted_at__isnull=False) & Q(revoked_at__isnull=False)),
                name="creation_invite_not_accepted_and_revoked",
            ),
            models.CheckConstraint(
                condition=Q(expires_at__gt=models.F("created_at")),
                name="creation_invite_expiry_after_creation",
            ),
            models.CheckConstraint(
                condition=(
                    Q(accepted_at__isnull=True, created_library__isnull=True)
                    | Q(accepted_at__isnull=False, created_library__isnull=False)
                ),
                name="creation_invite_acceptance_has_library",
            ),
        ]


class Membership(models.Model):
    ROLE_ADMIN = "admin"
    ROLE_MEMBER = "member"
    ROLE_CHOICES = [(ROLE_ADMIN, "Administradora"), (ROLE_MEMBER, "Membro")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    library = models.ForeignKey(Library, on_delete=models.CASCADE)
    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default=ROLE_MEMBER,
        db_default=ROLE_MEMBER,
    )
    joined_at = models.DateTimeField(default=timezone.now, null=True, blank=True)
    invitation = models.ForeignKey(
        LibraryInvite,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="memberships",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "library"], name="unique_member"),
            models.UniqueConstraint(
                fields=["invitation"],
                condition=Q(invitation__isnull=False),
                name="unique_invite_membership",
            ),
        ]


class Owned(models.Model):
    library = models.ForeignKey(Library, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self) -> None:
        super().clean()
        if self.pk:
            previous = (
                type(self)
                ._default_manager.filter(pk=self.pk)
                .values_list("library_id", flat=True)
                .first()
            )
            if previous is not None and previous != self.library_id:
                raise ValidationError(
                    "A biblioteca de um registro existente não pode ser alterada."
                )
        for field in self._meta.fields:
            if isinstance(field, models.ForeignKey) and field.name != "library":
                related = getattr(self, field.name, None)
                if (
                    related is not None
                    and hasattr(related, "library_id")
                    and related.library_id != self.library_id
                ):
                    raise ValidationError("Os registros devem pertencer à mesma biblioteca.")

    class Meta:
        abstract = True


class Location(Owned):
    name = models.CharField(max_length=150)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["id", "library"], name="unique_location_library_id"),
        ]

    def __str__(self) -> str:
        return self.name


class Tag(Owned):
    name = models.CharField(max_length=60)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["id", "library"], name="unique_tag_library_id"),
            models.UniqueConstraint(fields=["library", "name"], name="unique_library_tag"),
        ]

    def __str__(self) -> str:
        return self.name


class Book(Owned):
    provenance = models.JSONField(default=dict, db_default={}, blank=True)
    is_desired = models.BooleanField(default=False, db_default=False)
    title = models.CharField(max_length=300)
    subtitle = models.CharField(
        max_length=SUBTITLE_MAX_LENGTH, default="", db_default="", blank=True
    )
    description = models.TextField(
        default="",
        db_default="",
        blank=True,
        validators=[MaxLengthValidator(DESCRIPTION_MAX_LENGTH)],
    )
    subjects = models.JSONField(
        default=list,
        db_default=[],
        blank=True,
        validators=[validate_subjects],
    )
    authors = models.JSONField(default=list)
    isbn = models.CharField(max_length=13, blank=True, default="")
    publisher = models.CharField(max_length=200, blank=True)
    edition = models.CharField(max_length=100, blank=True)
    year = models.CharField(max_length=20, blank=True)
    page_count = models.PositiveIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1)]
    )
    language = models.CharField(max_length=50, blank=True)
    cover_url = models.URLField(max_length=1000, blank=True)
    cover_id = models.CharField(max_length=255, blank=True)
    source = models.CharField(max_length=40, blank=True)
    source_id = models.CharField(max_length=150, blank=True)
    tags = models.ManyToManyField(Tag, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["id", "library"], name="unique_book_library_id"),
            models.UniqueConstraint(
                fields=["library", "isbn"], condition=~Q(isbn=""), name="unique_library_isbn"
            ),
        ]
        ordering = ["title", "pk"]

    def __str__(self) -> str:
        return self.title


class Copy(Owned):
    book = models.ForeignKey(Book, on_delete=models.PROTECT, related_name="copies")
    number = models.PositiveIntegerField()
    location = models.ForeignKey(Location, null=True, blank=True, on_delete=models.PROTECT)
    acquired_on = models.DateField(default=timezone.localdate)
    state = models.CharField(
        max_length=12,
        default="active",
        choices=[
            (s, n)
            for s, n in [
                ("active", "No acervo"),
                ("sold", "Vendido"),
                ("donated", "Doado"),
                ("lost", "Perdido"),
            ]
        ],
    )
    retired_on = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["id", "library"], name="unique_copy_library_id"),
            models.UniqueConstraint(fields=["library", "number"], name="unique_copy_number"),
        ]
        ordering = ["number"]

    def __str__(self) -> str:
        return f"#{self.number} — {self.book}"


class Person(Owned):
    name = models.CharField(max_length=150, validators=[MinLengthValidator(1)])
    phone = models.CharField(max_length=40, validators=[MinLengthValidator(1)])
    email = models.EmailField(blank=True)
    archived = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["id", "library"], name="unique_person_library_id"),
        ]

    def clean(self) -> None:
        super().clean()
        self.name = self.name.strip()
        self.phone = self.phone.strip()
        if not self.name or not self.phone:
            raise ValidationError("Nome e telefone são obrigatórios.")
        if self.archived and self.pk and self.loans.filter(state="open").exists():
            raise ValidationError("Encerre os empréstimos antes de arquivar.")

    def __str__(self) -> str:
        return self.name


class Loan(Owned):
    copy = models.ForeignKey(Copy, on_delete=models.PROTECT, related_name="loans")
    person = models.ForeignKey(Person, on_delete=models.PROTECT, related_name="loans")
    started_on = models.DateField()
    due_on = models.DateField()
    returned_on = models.DateField(null=True, blank=True)
    state = models.CharField(
        max_length=12,
        default="open",
        choices=[("open", "Aberto"), ("returned", "Devolvido"), ("lost", "Encerrado por perda")],
    )

    class Meta:
        ordering = ["-started_on", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["copy"], condition=Q(state="open"), name="one_open_loan"
            ),
            models.CheckConstraint(
                condition=Q(due_on__gte=models.F("started_on")), name="valid_due_date"
            ),
            models.CheckConstraint(
                condition=Q(returned_on__isnull=True) | Q(returned_on__gte=models.F("started_on")),
                name="valid_return_date",
            ),
            models.CheckConstraint(
                condition=(
                    Q(state="returned", returned_on__isnull=False)
                    | Q(state__in=["open", "lost"], returned_on__isnull=True)
                ),
                name="valid_loan_state",
            ),
        ]


class ShareLink(Owned):
    digest = models.CharField(max_length=64, unique=True)
    active = models.BooleanField(default=True)


class ImportSession(Owned):
    SOURCE_GOODREADS = "goodreads"
    SOURCE_LIBIB = "libib"
    source = models.CharField(
        max_length=20,
        default=SOURCE_GOODREADS,
        choices=[(SOURCE_GOODREADS, "Goodreads"), (SOURCE_LIBIB, "Libib")],
    )


class ImportFile(models.Model):
    session = models.ForeignKey(ImportSession, on_delete=models.CASCADE, related_name="files")
    position = models.PositiveSmallIntegerField()
    original_name = models.CharField(max_length=255)
    collection = models.CharField(max_length=150, blank=True)
    sha256 = models.CharField(max_length=64)
    status = models.CharField(
        max_length=10, default="ready", choices=[("ready", "Ready"), ("error", "Error")]
    )
    error = models.CharField(max_length=300, blank=True)
    unknown_columns = models.JSONField(default=list)
    total_rows = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["session", "position"], name="unique_import_file_position"
            )
        ]


class ImportReceipt(Owned):
    source_key = models.CharField(max_length=64)
    file_sha256 = models.CharField(max_length=64, db_index=True)
    row_fingerprint = models.CharField(max_length=64)
    collection = models.CharField(max_length=150, blank=True)
    desired_copies = models.PositiveSmallIntegerField()
    added_copies = models.PositiveSmallIntegerField(default=0)
    decision = models.CharField(max_length=10, choices=[("import", "Import"), ("copy", "Copy")])
    state = models.CharField(
        max_length=12, default="completed", choices=[("completed", "Completed")]
    )
    book = models.ForeignKey(Book, null=True, blank=True, on_delete=models.SET_NULL)
    copies: Any = models.ManyToManyField(
        Copy, through="ImportReceiptCopy", related_name="import_receipts"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["id", "library"], name="unique_import_receipt_library_id"
            ),
            models.UniqueConstraint(
                fields=["library", "source_key"], name="unique_import_receipt_source"
            ),
        ]
        indexes = [
            models.Index(fields=["library", "file_sha256"], name="receipt_library_file_hash")
        ]


class ImportReceiptCopy(models.Model):
    library = models.ForeignKey(Library, on_delete=models.CASCADE)
    receipt = models.ForeignKey(ImportReceipt, on_delete=models.CASCADE)
    copy = models.ForeignKey(Copy, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["receipt", "copy"], name="unique_receipt_copy"),
        ]

    def clean(self) -> None:
        super().clean()
        if (
            self.receipt_id
            and self.copy_id
            and self.copy
            and self.receipt.library_id != self.copy.library_id
        ):
            raise ValidationError("O recibo e o exemplar devem pertencer à mesma biblioteca.")
        if self.library_id and self.receipt_id and self.library_id != self.receipt.library_id:
            raise ValidationError("O recibo pertence a outra biblioteca.")
        if (
            self.library_id
            and self.copy_id
            and self.copy
            and self.library_id != self.copy.library_id
        ):
            raise ValidationError("O exemplar pertence a outra biblioteca.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class ImportRow(models.Model):
    session = models.ForeignKey(ImportSession, on_delete=models.CASCADE, related_name="rows")
    import_file = models.ForeignKey(
        ImportFile, null=True, blank=True, on_delete=models.CASCADE, related_name="rows"
    )
    position = models.PositiveIntegerField()
    file_row_number = models.PositiveIntegerField(null=True, blank=True)
    source_key = models.CharField(max_length=64, blank=True)
    row_fingerprint = models.CharField(max_length=64, blank=True)
    data = models.JSONField()
    result = models.CharField(max_length=20, blank=True)
    copy = models.ForeignKey(Copy, null=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["session", "position"], name="unique_import_row")
        ]


class Registration(Owned):
    key = models.UUIDField()
    fingerprint = models.CharField(max_length=64)
    book = models.ForeignKey(Book, null=True, on_delete=models.SET_NULL)
    copy = models.ForeignKey(Copy, null=True, on_delete=models.SET_NULL)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["id", "library"], name="unique_registration_library_id"
            ),
            models.UniqueConstraint(fields=["library", "key"], name="unique_registration_key"),
        ]
