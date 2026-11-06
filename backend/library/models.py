from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinLengthValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class User(AbstractUser):
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
    name = models.CharField(max_length=150)
    next_number = models.PositiveIntegerField(default=1)

    def __str__(self) -> str:
        return self.name


class Membership(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    library = models.ForeignKey(Library, on_delete=models.CASCADE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "library"], name="unique_member")]


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

    def __str__(self) -> str:
        return self.name


class Tag(Owned):
    name = models.CharField(max_length=60)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["library", "name"], name="unique_library_tag")
        ]

    def __str__(self) -> str:
        return self.name


class Book(Owned):
    is_desired = models.BooleanField(default=False, db_default=False)
    title = models.CharField(max_length=300)
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
            models.UniqueConstraint(
                fields=["library", "isbn"], condition=~Q(isbn=""), name="unique_library_isbn"
            )
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
            models.UniqueConstraint(fields=["library", "number"], name="unique_copy_number")
        ]
        ordering = ["number"]

    def __str__(self) -> str:
        return f"#{self.number} — {self.book}"


class Person(Owned):
    name = models.CharField(max_length=150, validators=[MinLengthValidator(1)])
    phone = models.CharField(max_length=40, validators=[MinLengthValidator(1)])
    email = models.EmailField(blank=True)
    archived = models.BooleanField(default=False)

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
    pass


class ImportRow(models.Model):
    session = models.ForeignKey(ImportSession, on_delete=models.CASCADE, related_name="rows")
    position = models.PositiveIntegerField()
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
            models.UniqueConstraint(fields=["library", "key"], name="unique_registration_key")
        ]
