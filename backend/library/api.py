from datetime import timedelta
from typing import Any, cast

from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import logout
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Q
from django.http import HttpRequest, HttpResponseForbidden
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import File, NinjaAPI, Status
from ninja.files import UploadedFile

from . import circulation, imports, media, providers, services, sharing
from . import schemas as s
from .auth import AllowedSession, require_library, technical
from .models import Book, Copy, ImportSession, Loan, Location, Person, ShareLink, Tag, User
from .presentation import book_data, loan_data
from .readiness import database_ready

api = NinjaAPI(
    title="Julib API",
    version="1.0",
    auth=AllowedSession(),
    docs_decorator=lambda view: tools_only(view),
)


def tools_only(view: Any) -> Any:
    def protected(request: HttpRequest, *args: Any, **kwargs: Any) -> Any:
        if not technical(request.user):
            return HttpResponseForbidden("Documentação restrita ao administrador.")
        return view(request, *args, **kwargs)

    return protected


@api.exception_handler(ValidationError)
def validation_error(request: HttpRequest, exc: ValidationError) -> Any:
    return api.create_response(request, {"detail": "; ".join(exc.messages)}, status=400)


@api.exception_handler(IntegrityError)
def conflict(request: HttpRequest, exc: IntegrityError) -> Any:
    return api.create_response(
        request, {"detail": "Operação em conflito com um registro existente."}, status=409
    )


@api.get("/health", auth=None)
def health(request: HttpRequest) -> dict[str, str]:
    return {"status": "ok"}


@api.get("/health/ready", auth=None, response={200: dict[str, str], 503: dict[str, str]})
def ready(request: HttpRequest) -> Status[dict[str, str]]:
    if database_ready():
        return Status(200, {"status": "ok"})
    return Status(503, {"status": "unavailable"})


@api.api_operation(
    ["HEAD"],
    "/health/ready",
    auth=None,
    response={200: dict[str, str], 503: dict[str, str]},
    include_in_schema=False,
)
def ready_head(request: HttpRequest) -> Status[dict[str, str]]:
    return ready(request)


@api.get("/session", response=s.SessionOut)
def session(request: HttpRequest) -> dict[str, Any]:
    user = cast(User, request.user)
    membership = user.membership_set.select_related("library").first()
    google_account = SocialAccount.objects.filter(user=user, provider="google").first()
    return {
        "name": user.get_full_name() or user.username,
        "email": user.email,
        "catalog_view": user.catalog_view,
        "cover_columns": user.cover_columns,
        "avatar_url": (google_account.get_avatar_url() or "") if google_account else "",
        "technical": technical(request.user),
        "library": membership.library.name if membership else None,
        "csrf": get_token(request),
    }


@api.put("/preferences/catalog", response=s.CatalogPreferencesIn)
def catalog_preferences(request: HttpRequest, payload: s.CatalogPreferencesIn) -> dict[str, Any]:
    user = cast(User, request.user)
    user.catalog_view = payload.catalog_view
    user.cover_columns = payload.cover_columns
    user.save(update_fields=["catalog_view", "cover_columns"])
    return payload.model_dump()


@api.post("/logout")
def logout_view(request: HttpRequest) -> dict[str, bool]:
    logout(request)
    return {"ok": True}


def books_query(library: Any) -> Any:
    return Book.objects.filter(library=library).prefetch_related("tags", "copies__loans")


@api.get("/books", response=s.CatalogOut)
def books(
    request: HttpRequest,
    q: str = "",
    tag_id: int | None = None,
    location_id: int | None = None,
    available: bool | None = None,
    page: int = 1,
    missing_location: bool = False,
) -> dict[str, Any]:
    lib = require_library(request)
    qs = books_query(lib)
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(authors__icontains=q) | Q(isbn__icontains=q))
    if tag_id:
        qs = qs.filter(tags__id=tag_id)
    if location_id:
        ids = [services.owned(Location, lib, location_id).pk]
        while children := list(
            Location.objects.filter(library=lib, parent_id__in=ids)
            .exclude(pk__in=ids)
            .values_list("pk", flat=True)
        ):
            ids += children
        qs = qs.filter(copies__location_id__in=ids)
    if missing_location:
        qs = qs.filter(copies__location__isnull=True, copies__state="active")
    if available is not None:
        available_ids = (
            Copy.objects.filter(library=lib, state="active")
            .exclude(loans__state="open")
            .values("book_id")
        )
        qs = qs.filter(pk__in=available_ids) if available else qs.exclude(pk__in=available_ids)
    qs = qs.distinct()
    page = max(1, page)
    size = 24
    return {
        "items": [book_data(b) for b in qs[(page - 1) * size : page * size]],
        "total": qs.count(),
        "page": page,
        "page_size": size,
    }


@api.get("/books/{pk}", response=s.BookOut)
def book_detail(request: HttpRequest, pk: int) -> dict[str, Any]:
    return book_data(get_object_or_404(books_query(require_library(request)), pk=pk))


@api.post("/books", response=s.BookOut)
def create_book(request: HttpRequest, payload: s.BookIn) -> dict[str, Any]:
    return book_data(services.create_book(require_library(request), payload.model_dump()))


@api.put("/books/{pk}", response=s.BookOut)
def edit_book(request: HttpRequest, pk: int, payload: s.BookIn) -> dict[str, Any]:
    return book_data(services.create_book(require_library(request), payload.model_dump(), pk))


@api.delete("/books/{pk}")
def delete_book(request: HttpRequest, pk: int) -> dict[str, bool]:
    book = services.owned(Book, require_library(request), pk)
    if book.copies.exists():
        raise ValidationError("Dê baixa nos exemplares; livros com exemplares não são apagados.")
    book.delete()
    return {"ok": True}


@api.post("/copies")
def create_copy(request: HttpRequest, payload: s.CopyIn) -> dict[str, int]:
    copy = services.add_copy(require_library(request), **payload.model_dump())
    return {"id": copy.pk, "number": copy.number}


@api.post("/copies/locate")
def locate(request: HttpRequest, payload: s.BulkLocation) -> dict[str, int]:
    return {"updated": services.locate_copies(require_library(request), **payload.model_dump())}


@api.post("/copies/{pk}/retire")
def retire(request: HttpRequest, pk: int, payload: s.RetireIn) -> dict[str, bool]:
    circulation.retire_copy(require_library(request), pk, payload.reason)
    return {"ok": True}


@api.get("/locations", response=list[s.LocationOut])
def locations(request: HttpRequest) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in (
            Location.objects.filter(library=require_library(request))
            .order_by("name")
            .values("id", "name", "parent_id")
        )
    ]


@api.post("/locations")
def new_location(request: HttpRequest, payload: s.LocationIn) -> dict[str, int]:
    return {"id": services.save_location(require_library(request), payload.model_dump()).pk}


@api.put("/locations/{pk}")
def edit_location(request: HttpRequest, pk: int, payload: s.LocationIn) -> dict[str, int]:
    return {"id": services.save_location(require_library(request), payload.model_dump(), pk).pk}


@api.delete("/locations/{pk}")
def delete_location(request: HttpRequest, pk: int) -> dict[str, bool]:
    location = services.owned(Location, require_library(request), pk)
    if (
        Location.objects.filter(parent=location).exists()
        or Copy.objects.filter(location=location).exists()
    ):
        raise ValidationError("Mova os exemplares e sublocais antes de excluir.")
    location.delete()
    return {"ok": True}


@api.get("/tags", response=list[s.TagOut])
def tags(request: HttpRequest) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in (
            Tag.objects.filter(library=require_library(request))
            .order_by("name")
            .values("id", "name")
        )
    ]


@api.post("/tags")
def new_tag(request: HttpRequest, payload: s.NameIn) -> dict[str, Any]:
    tag = Tag(library=require_library(request), name=payload.name.strip())
    tag.full_clean()
    tag.save()
    return {"id": tag.pk, "name": tag.name}


@api.get("/people", response=list[s.PersonOut])
def people(request: HttpRequest) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in (
            Person.objects.filter(library=require_library(request))
            .order_by("name")
            .values("id", "name", "phone", "email", "archived")
        )
    ]


@api.post("/people")
def new_person(request: HttpRequest, payload: s.PersonIn) -> dict[str, int]:
    person = Person(library=require_library(request), **payload.model_dump())
    person.name = person.name.strip()
    person.phone = person.phone.strip()
    person.full_clean()
    person.save()
    return {"id": person.pk}


@api.put("/people/{pk}")
def edit_person(request: HttpRequest, pk: int, payload: s.PersonIn) -> dict[str, int]:
    person = services.owned(Person, require_library(request), pk)
    if payload.archived and person.loans.filter(state="open").exists():
        raise ValidationError("Encerre os empréstimos antes de arquivar.")
    for key, value in payload.model_dump().items():
        setattr(person, key, value.strip() if isinstance(value, str) else value)
    person.full_clean()
    person.save()
    return {"id": person.pk}


@api.get("/loans", response=list[s.LoanOut])
def loans(
    request: HttpRequest, person_id: int | None = None, copy_id: int | None = None, state: str = ""
) -> list[dict[str, Any]]:
    qs = Loan.objects.filter(library=require_library(request)).select_related(
        "copy__book", "person"
    )
    if person_id:
        qs = qs.filter(person_id=person_id)
    if copy_id:
        qs = qs.filter(copy_id=copy_id)
    if state:
        qs = qs.filter(state=state)
    return [loan_data(loan) for loan in qs]


@api.post("/loans", response=s.LoanOut)
def new_loan(request: HttpRequest, payload: s.LoanIn) -> dict[str, Any]:
    return loan_data(circulation.lend(require_library(request), **payload.model_dump()))


@api.post("/loans/{pk}/return", response=s.LoanOut)
def return_book(request: HttpRequest, pk: int, payload: s.ReturnIn) -> dict[str, Any]:
    return loan_data(circulation.return_loan(require_library(request), pk, payload.returned_on))


@api.get("/dashboard")
def dashboard(request: HttpRequest) -> dict[str, Any]:
    lib = require_library(request)
    active = Copy.objects.filter(library=lib, state="active")
    open_loans = Loan.objects.filter(library=lib, state="open").select_related(
        "copy__book", "person"
    )
    return {
        "books": active.values("book_id").distinct().count(),
        "copies": active.count(),
        "loans": open_loans.count(),
        "overdue": open_loans.filter(due_on__lt=timezone.localdate()).count(),
        "recent": [
            {
                "number": c.number,
                "acquired_on": c.acquired_on.isoformat(),
                "book": book_data(c.book),
            }
            for c in active.select_related("book").order_by("-acquired_on", "-pk")[:6]
        ],
        "attention": [loan_data(loan) for loan in open_loans.order_by("due_on")[:5]],
    }


@api.get("/search")
def search(request: HttpRequest, q: str) -> list[dict[str, Any]]:
    require_library(request)
    return providers.search_books(q)


@api.post("/media/sign")
def sign_media(request: HttpRequest) -> dict[str, Any]:
    return media.signature(require_library(request))


@api.post("/books/{pk}/cover")
def attach_cover(request: HttpRequest, pk: int, payload: s.MediaIn) -> dict[str, str]:
    lib = require_library(request)
    book = services.owned(Book, lib, pk)
    data = media.verify_upload(lib, payload.public_id)
    book.cover_id = data["cover_id"]
    book.cover_url = data["cover_url"]
    book.save(update_fields=["cover_id", "cover_url"])
    return data


@api.post("/imports")
def import_preview(request: HttpRequest, file: File[UploadedFile]) -> dict[str, int]:
    return {"id": imports.preview_csv(require_library(request), file.read()).pk}


@api.get("/imports")
def import_sessions(request: HttpRequest) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in (
            ImportSession.objects.filter(
                library=require_library(request),
                created_at__gte=timezone.now() - timedelta(days=7),
            )
            .order_by("-pk")
            .values("id", "created_at")
        )
    ]


@api.get("/imports/{pk}")
def import_details(request: HttpRequest, pk: int) -> dict[str, Any]:
    lib = require_library(request)
    session = services.owned(ImportSession, lib, pk)
    return {
        "id": pk,
        "rows": [
            {
                "id": row.pk,
                "data": row.data,
                "result": row.result,
                "existing": imports.matching(lib, row.data) is not None,
            }
            for row in session.rows.all()
        ],
    }


@api.post("/imports/{pk}/process")
def import_process(request: HttpRequest, pk: int, payload: s.ImportActions) -> list[dict[str, Any]]:
    return imports.process_rows(
        require_library(request), pk, [a.model_dump() for a in payload.actions]
    )


@api.post("/share/manage")
def share_create(request: HttpRequest) -> dict[str, str]:
    return {"token": sharing.renew_link(require_library(request))}


@api.delete("/share/manage")
def share_disable(request: HttpRequest) -> dict[str, bool]:
    ShareLink.objects.filter(library=require_library(request)).update(active=False)
    return {"ok": True}


@api.get("/public/{token}/books", auth=None, response=s.PublicCatalogOut)
def public_catalog(
    request: HttpRequest, token: str, q: str = "", page: int = 1, tag_id: int | None = None
) -> dict[str, Any]:
    return sharing.public_books(token, q, page, tag_id)


@api.put("/copies/{pk}")
def update_copy(request: HttpRequest, pk: int, payload: s.CopyUpdate) -> dict[str, bool]:
    from django.db import transaction

    lib = require_library(request)
    with transaction.atomic():
        services.locate_copies(lib, [pk], payload.location_id)
        Copy.objects.filter(library=lib, pk=pk).update(acquired_on=payload.acquired_on)
    return {"ok": True}


@api.post("/registrations")
def register_copy(request: HttpRequest, payload: s.RegistrationIn) -> dict[str, int]:
    return services.register_copy(require_library(request), payload.model_dump())
