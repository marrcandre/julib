from datetime import timedelta
from typing import Any, Literal, cast

from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import logout
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import HttpRequest, HttpResponseForbidden
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import File, NinjaAPI, Query, Status
from ninja.errors import HttpError
from ninja.files import UploadedFile

from . import catalog, circulation, imports, media, providers, services, sharing
from . import schemas as s
from .auth import AllowedSession, require_library, require_membership, technical
from .models import (
    Book,
    Copy,
    ImportSession,
    Library,
    Loan,
    Location,
    Membership,
    Person,
    ShareLink,
    Tag,
    User,
)
from .presentation import book_data, candidate_credits, loan_data
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
    memberships = list(user.membership_set.select_related("library").order_by("library_id"))
    selected = require_membership(request) if request.headers.get("X-Library-ID") else None
    if selected is None and len(memberships) == 1:
        selected = memberships[0]
    google_account = SocialAccount.objects.filter(user=user, provider="google").first()
    return {
        "user_id": user.pk,
        "name": user.get_full_name() or user.username,
        "email": user.email,
        "catalog_view": user.catalog_view,
        "cover_columns": user.cover_columns,
        "avatar_url": (google_account.get_avatar_url() or "") if google_account else "",
        "technical": technical(request.user),
        "can_create_libraries": user.can_create_libraries,
        "libraries": [
            {"id": m.library_id, "name": m.library.name, "role": m.role} for m in memberships
        ],
        "library": selected.library.name if selected else None,
        "csrf": get_token(request),
    }


@api.get("/libraries", response=list[s.LibrarySummaryOut])
def libraries(request: HttpRequest) -> list[dict[str, Any]]:
    return [
        {"id": membership.library_id, "name": membership.library.name, "role": membership.role}
        for membership in Membership.objects.filter(user=cast(User, request.user))
        .select_related("library")
        .order_by("library_id")
    ]


@api.post("/libraries", response=s.LibrarySummaryOut)
def create_library(request: HttpRequest, payload: s.LibraryCreateIn) -> dict[str, Any]:
    user = cast(User, request.user)
    if not user.can_create_libraries:
        raise HttpError(403, "Esta conta não pode criar bibliotecas.")
    name = payload.name.strip()
    if not name:
        raise ValidationError("Informe o nome da biblioteca.")
    with transaction.atomic():
        library = Library.objects.create(name=name)
        membership = Membership.objects.create(
            user=user, library=library, role=Membership.ROLE_ADMIN
        )
    return {"id": library.pk, "name": library.name, "role": membership.role}


@api.put("/preferences/catalog", response=s.CatalogPreferencesIn)
def catalog_preferences(request: HttpRequest, payload: s.CatalogPreferencesIn) -> dict[str, Any]:
    user = cast(User, request.user)
    user.catalog_view = payload.catalog_view
    user.cover_columns = payload.cover_columns
    user.save(update_fields=["catalog_view", "cover_columns"])
    return payload.model_dump()


@api.put("/library/name", response=s.LibraryNameOut)
def update_library_name(request: HttpRequest, payload: s.LibraryNameIn) -> dict[str, str]:
    membership = require_membership(request)
    if membership.role != Membership.ROLE_ADMIN:
        raise HttpError(403, "Somente administradores desta biblioteca podem renomeá-la.")
    library = membership.library
    library.name = payload.name.strip()
    library.save(update_fields=["name"])
    return {"name": library.name}


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
    scope: Literal["collection", "wishlist", "all"] = "collection",
    statuses: str | None = None,
    order: catalog.CatalogOrder = "newest",
    page_size: int = Query(24, ge=1, le=100),
) -> dict[str, Any]:
    lib = require_library(request)
    qs = books_query(lib)
    if statuses is not None:
        qs = catalog.by_situations(qs, lib, statuses, location_id, missing_location)
    elif scope != "all":
        qs = qs.filter(is_desired=scope == "wishlist")
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(authors__icontains=q) | Q(isbn__icontains=q))
    if tag_id:
        qs = qs.filter(tags__id=tag_id)
    if location_id and statuses is None:
        ids = [services.owned(Location, lib, location_id).pk]
        while children := list(
            Location.objects.filter(library=lib, parent_id__in=ids)
            .exclude(pk__in=ids)
            .values_list("pk", flat=True)
        ):
            ids += children
        qs = qs.filter(copies__location_id__in=ids)
    if missing_location and statuses is None:
        qs = qs.filter(copies__location__isnull=True, copies__state="active")
    if available is not None and statuses is None:
        available_ids = (
            Copy.objects.filter(library=lib, state="active")
            .exclude(loans__state="open")
            .values("book_id")
        )
        qs = qs.filter(pk__in=available_ids) if available else qs.exclude(pk__in=available_ids)
    qs = catalog.ordered(qs.distinct(), order)
    total = qs.count()
    size = page_size
    page = min(max(1, page), max(1, (total + size - 1) // size))
    return {
        "items": [book_data(b) for b in qs[(page - 1) * size : page * size]],
        "total": total,
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
def edit_book(request: HttpRequest, pk: int, payload: s.BookEditIn) -> dict[str, Any]:
    return book_data(services.edit_book(require_library(request), pk, payload.model_dump()))


@api.delete("/books/{pk}")
def delete_book(request: HttpRequest, pk: int) -> dict[str, bool]:
    services.delete_book(require_library(request), pk)
    return {"ok": True}


@api.post("/books/{pk}/wishlist", response=s.BookOut)
def move_to_wishlist(request: HttpRequest, pk: int) -> dict[str, Any]:
    return book_data(services.move_to_wishlist(require_library(request), pk))


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


@api.get("/search")
def search(request: HttpRequest, q: str) -> list[dict[str, Any]]:
    require_library(request)
    return [candidate_credits(result) for result in providers.search_books(q)]


@api.post("/search/enrich")
def enrich_search(request: HttpRequest, payload: s.BookIn) -> dict[str, Any]:
    require_library(request)
    return candidate_credits(providers.enrich_book(payload.model_dump()))


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
    book.provenance = {
        **book.provenance,
        "cover_url": {"source": "manual", "source_id": "", "url": data["cover_url"]},
    }
    book.save(update_fields=["cover_id", "cover_url", "provenance"])
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


@api.get("/share/manage", response=s.ShareStatusOut)
def share_status(request: HttpRequest) -> dict[str, bool]:
    return {
        "active": ShareLink.objects.filter(library=require_library(request), active=True).exists()
    }


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


@api.post("/registrations", response=s.RegistrationOut)
def register_copy(request: HttpRequest, payload: s.RegistrationIn) -> dict[str, int | None]:
    return services.register_copy(require_library(request), payload.model_dump())
