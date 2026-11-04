from datetime import date
from ninja import Schema
from pydantic import Field

class BookIn(Schema):
    title: str = Field(min_length=1, max_length=300)
    authors: list[str] = Field(min_length=1)
    isbn: str = ''
    publisher: str = ''
    edition: str = ''
    year: str = ''
    language: str = ''
    cover_url: str = ''
    source: str = ''
    source_id: str = ''
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
    email: str = ''
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
    action: str = 'import'

class ImportActions(Schema):
    actions: list[ImportAction] = Field(max_length=25)

class MediaIn(Schema):
    public_id: str
