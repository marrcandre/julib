"""Derived catalog situations and stable ordering; no duplicated book status."""

from typing import Literal

from django.core.exceptions import ValidationError
from django.db.models import Case, Exists, F, IntegerField, Max, OuterRef, Q, QuerySet, When
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast, Lower

from .models import Book, Copy, Library, Loan, Location

CatalogOrder = Literal[
    "newest",
    "oldest",
    "title_asc",
    "title_desc",
    "author",
    "acquired_desc",
    "acquired_asc",
    "year_desc",
    "year_asc",
]


def by_situations(
    qs: QuerySet[Book], library: Library, statuses: str, location_id: int | None, missing: bool
) -> QuerySet[Book]:
    selected = set(statuses.split(",")) if statuses else {"available", "loaned", "wishlist", "lost"}
    if not selected <= {"available", "loaned", "wishlist", "lost"}:
        raise ValidationError("Situação inválida.")
    copies = Copy.objects.filter(library=library).annotate(
        borrowed=Exists(Loan.objects.filter(copy_id=OuterRef("pk"), state="open"))
    )
    if location_id:
        from .services import owned

        ids = [owned(Location, library, location_id).pk]
        while children := list(
            Location.objects.filter(library=library, parent_id__in=ids)
            .exclude(pk__in=ids)
            .values_list("pk", flat=True)
        ):
            ids += children
        copies = copies.filter(location_id__in=ids)
    if missing:
        copies = copies.filter(location__isnull=True)
    condition = Q(pk__in=[])
    for status in selected:
        if status == "wishlist":
            if not location_id and not missing:
                condition |= Q(is_desired=True)
        else:
            matching = copies.filter(state="lost" if status == "lost" else "active")
            if status != "lost":
                matching = matching.filter(borrowed=status == "loaned")
            condition |= (
                Q(pk__in=matching.values("book_id"))
                if status == "lost"
                else Q(pk__in=matching.values("book_id"), is_desired=False)
            )
    return qs.filter(condition)


def ordered(qs: QuerySet[Book], order: CatalogOrder) -> QuerySet[Book]:
    if order in {"newest", "oldest"}:
        return qs.order_by(
            "-created_at" if order == "newest" else "created_at",
            "-pk" if order == "newest" else "pk",
        )
    if order in {"title_asc", "title_desc"}:
        return qs.order_by(
            Lower("title").desc() if order == "title_desc" else Lower("title").asc(), "pk"
        )
    if order == "author":
        return qs.order_by(
            Lower(KeyTextTransform(0, "authors")).asc(nulls_last=True), Lower("title"), "pk"
        )
    if order.startswith("acquired_"):
        qs = qs.annotate(sort_date=Max("copies__acquired_on"))
        return qs.order_by(
            F("sort_date").desc(nulls_last=True)
            if order == "acquired_desc"
            else F("sort_date").asc(nulls_last=True),
            "pk",
        )
    qs = qs.annotate(
        sort_year=Case(
            When(year__regex=r"^\d{4}$", then=Cast("year", IntegerField())),
            default=None,
            output_field=IntegerField(),
        )
    )
    return qs.order_by(
        F("sort_year").desc(nulls_last=True)
        if order == "year_desc"
        else F("sort_year").asc(nulls_last=True),
        "pk",
    )
