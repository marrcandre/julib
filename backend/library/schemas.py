from datetime import date
from uuid import UUID

from ninja import Schema
from pydantic import Field


class BookIn(Schema):
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


class SessionOut(Schema):
    avatar_url: str
    name: str
    email: str
    technical: bool
    library: str | None
    csrf: str


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
    key: UUID
    book: BookIn
    existing_book_id: int | None = None
    location_id: int | None = None
    acquired_on: date | None = None
