import hashlib
import secrets
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Book, Library, ShareLink
from .presentation import book_data


@transaction.atomic
def renew_link(library: Library) -> str:
    Library.objects.select_for_update().get(pk=library.pk)
    ShareLink.objects.filter(library=library).update(active=False)
    token = secrets.token_urlsafe(32)
    ShareLink.objects.create(library=library, digest=hashlib.sha256(token.encode()).hexdigest())
    return token


def public_books(
    token: str, q: str = "", page: int = 1, tag_id: int | None = None
) -> dict[str, Any]:
    link = ShareLink.objects.filter(
        digest=hashlib.sha256(token.encode()).hexdigest(), active=True
    ).first()
    if not link:
        raise ValidationError("Link inválido ou desativado.")
    qs = (
        Book.objects.filter(library=link.library, copies__state="active", is_desired=False)
        .prefetch_related("tags", "copies__loans")
        .distinct()
    )
    if q:
        qs = qs.filter(title__icontains=q)
    if tag_id:
        qs = qs.filter(tags__id=tag_id)
    page = max(1, page)
    return {
        "name": link.library.name,
        "items": [book_data(b, public=True) for b in qs[(page - 1) * 24 : page * 24]],
        "total": qs.count(),
    }
