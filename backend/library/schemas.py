from datetime import date, datetime
from typing import Literal
from uuid import UUID

from ninja import Schema
from pydantic import Field


class ProvenanceEntry(Schema):
    alternatives: list[str] = Field(default_factory=list, max_length=4)
    source: str = Field(max_length=40)
    source_id: str = Field(default="", max_length=300)
    url: str = Field(default="", max_length=1000)


class BookIn(Schema):
    provenance: dict[str, ProvenanceEntry] = Field(default_factory=dict, max_length=12)
    page_count: int | None = Field(default=None, ge=1, le=2147483647)
    title: str = Field(min_length=1, max_length=300)
    authors: list[str] = Field(min_length=1)
    isbn: str = ""
    publisher: str = ""
    edition: str = ""
    year: str = ""
    language: str = ""
    cover_url: str = ""
    source: str = ""
    source_id: str = ""
    tag_ids: list[int] = Field(default_factory=list)


class CopyIn(Schema):
    book_id: int
    location_id: int | None = None
    acquired_on: date | None = None


class BookEditIn(BookIn):
    cover_public_id: str | None = None


class LocationIn(Schema):
    name: str = Field(min_length=1, max_length=150)
    parent_id: int | None = None


class NameIn(Schema):
    name: str = Field(min_length=1, max_length=60)


class BulkLocation(Schema):
    copy_ids: list[int] = Field(min_length=1, max_length=1000)
    location_id: int | None = None


class PersonIn(Schema):
    name: str = Field(min_length=1, max_length=150)
    phone: str = Field(min_length=1, max_length=40)
    email: str = ""
    archived: bool = False


class LoanIn(Schema):
    copy_id: int
    person_id: int
    started_on: date | None = None
    due_on: date | None = None


class ReturnIn(Schema):
    returned_on: date


class RetireIn(Schema):
    reason: str


class ImportAction(Schema):
    id: int
    action: str = "import"


class ImportActions(Schema):
    actions: list[ImportAction] = Field(max_length=25)


class MediaIn(Schema):
    public_id: str


class CopyUpdate(Schema):
    location_id: int | None = None
    acquired_on: date


class TagOut(Schema):
    id: int
    name: str


class CopyOut(Schema):
    id: int
    book_id: int
    number: int
    location_id: int | None
    acquired_on: str
    state: str
    on_loan: bool


class PublicBookOut(Schema):
    metadata_attribution_name: str = ""
    metadata_attribution_url: str = ""
    page_count: int | None = None
    attribution_name: str = ""
    attribution_url: str = ""
    id: int
    title: str
    authors: list[str]
    isbn: str
    publisher: str
    edition: str
    year: str
    language: str
    cover_url: str
    tags: list[TagOut]
    available: bool


class BookOut(PublicBookOut):
    provenance: dict[str, ProvenanceEntry] = Field(default_factory=dict)
    is_desired: bool
    can_delete: bool
    copies: list[CopyOut]
    source: str
    source_id: str


class CatalogOut(Schema):
    items: list[BookOut]
    total: int
    page: int
    page_size: int


class PublicCatalogOut(Schema):
    name: str
    items: list[PublicBookOut]
    total: int


class CatalogPreferencesIn(Schema):
    catalog_view: Literal["covers", "cards", "list"]
    cover_columns: int = Field(ge=3, le=10)


class LibraryNameIn(Schema):
    name: str = Field(max_length=150)


class LibraryCreateIn(Schema):
    name: str = Field(min_length=1, max_length=150)


class LibraryNameOut(Schema):
    name: str


class LibrarySummaryOut(Schema):
    id: int
    name: str
    role: Literal["admin", "member"]


class LibraryCreationInviteCreateIn(Schema):
    email: str = Field(default="", max_length=254)


class LibraryCreationInviteOut(Schema):
    id: int
    email: str
    created_at: datetime
    expires_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None
    status: Literal["pending", "accepted", "expired", "revoked"]
    created_library: LibrarySummaryOut | None = None


class LibraryCreationInviteCreateOut(Schema):
    id: int
    invite_url: str
    expires_at: datetime


class LibraryCreationInvitePrepareIn(Schema):
    token: str = Field(min_length=20, max_length=128)


class LibraryCreationInvitePreviewOut(Schema):
    pending: bool
    email: str = ""
    expires_at: datetime | None = None


class LibraryCreationInviteConsumeIn(Schema):
    name: str = Field(min_length=1, max_length=150)


class LibraryMemberOut(Schema):
    user_id: int
    name: str
    email: str
    avatar_url: str
    role: Literal["admin", "member"]
    joined_at: datetime | None
    is_current_user: bool
    can_change_role: bool
    can_remove: bool
    can_leave: bool


class MemberDirectoryOut(Schema):
    members: list[LibraryMemberOut]
    current_membership: LibraryMemberOut
    can_manage: bool


class MemberRoleIn(Schema):
    role: Literal["admin", "member"]


class LibraryInviteOut(Schema):
    id: int
    created_at: datetime
    expires_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None
    status: Literal["pending", "accepted", "expired", "revoked"]


class LibraryInviteCreateOut(Schema):
    id: int
    invite_url: str
    expires_at: datetime


class LibraryInvitePrepareIn(Schema):
    token: str = Field(min_length=20, max_length=128)


class LibraryInvitePreviewOut(Schema):
    pending: bool
    library_name: str | None = None
    expires_at: datetime | None = None


class LibraryInviteAcceptOut(Schema):
    library_id: int
    library_name: str
    already_member: bool


class CsrfOut(Schema):
    csrf: str


class SessionOut(Schema):
    user_id: int
    catalog_view: Literal["covers", "cards", "list"] = "covers"
    cover_columns: int = 7
    avatar_url: str
    name: str
    email: str
    technical: bool
    can_create_libraries: bool
    libraries: list[LibrarySummaryOut]
    library: str | None
    csrf: str


class ShareStatusOut(Schema):
    active: bool


class LocationOut(Schema):
    id: int
    name: str
    parent_id: int | None


class PersonOut(Schema):
    id: int
    name: str
    phone: str
    email: str
    archived: bool


class LoanOut(Schema):
    metadata_attribution_name: str = ""
    metadata_attribution_url: str = ""
    cover_url: str = ""
    attribution_name: str = ""
    attribution_url: str = ""
    id: int
    copy_id: int
    copy_number: int
    title: str
    person_id: int
    person_name: str
    started_on: str
    due_on: str
    returned_on: str | None
    state: str
    overdue: bool


class RegistrationIn(Schema):
    target: Literal["collection", "wishlist"] = "collection"
    key: UUID
    book: BookIn
    existing_book_id: int | None = None
    location_id: int | None = None
    acquired_on: date | None = None


class RegistrationOut(Schema):
    book_id: int
    copy_id: int | None
    number: int | None
