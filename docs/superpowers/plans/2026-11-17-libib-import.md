# Libib Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Import one or more Libib CSV exports with a review step, copy counts, library isolation, durable idempotency, and no Goodreads behavior changes.

**Architecture:** Keep `preview_csv` and `process_rows` for Goodreads unchanged. Add Libib-specific parser and processor, `ImportFile` and `ImportReceipt` tables, file associations on import rows, dedicated upload/preview/details/process routes, and a progressive UI on the existing import page.

**Tech Stack:** Django 5.2, PostgreSQL constraints, Django Ninja, pytest, Vue 3, TypeScript, Vitest/Playwright.

**Spec:** `docs/superpowers/specs/2026-11-17-libib-import-design.md`

## Global Constraints

- Limits: 5 MiB/file, 5 files/session, 5,000 records/file, 25,000 records/session, 100 copies/record, and 25 process actions/request.
- Only `item_type=book` creates books; ISBN match is library scoped; no title merge; Libib `id` is not a trusted key.
- A preview must complete before any Book or Copy is created.
- Receipt, Book, Tags, Copies, and row completion must commit atomically per source row.
- Session data expires after seven days; durable receipts do not.
- No production database operations, deploy, push, workflow edits, or commits.
- Goodreads request/response contracts and matching behavior remain unchanged.

## Review Focus

- Malformed CSV or UTF-8 failures must produce friendly per-file errors while valid sibling files remain processable.
- Same bytes under a different filename/session must not add another copy (receipt/idempotency test).
- Changed bytes with a matching ISBN must require an explicit copy decision (existing-book import test).
- Same ISBN in another library must never match or be disclosed (API/library isolation test).
- Invalid or excessive copy counts must not permit processing (mapping/action test).

### Task 1: Libib parser and normalized preview rows

**Files:** Create `backend/library/libib_imports.py`; modify `backend/tests/test_libib_imports.py`.

**Interfaces:** `parse_libib_files(files) -> ParsedImport`; `ParsedImport` returns per-file metadata and normalized row payloads. No database writes.

- [x] Write parser tests for header/BOM, quoting, multiline cells, unknown columns, required fields, malformed CSV/encoding, record limits, and field mapping.
- [x] Run focused tests and observe expected failures.
- [x] Implement bounded strict parser and pure normalizers; preserve creators conservatively and attach warnings/unimported-field names.
- [x] Re-run parser tests.

### Task 2: Persistent file and receipt schema

**Files:** Modify `backend/library/models.py`; create migration under `backend/library/migrations`; modify `backend/tests/test_schema.py` and `backend/tests/test_postgres_integrity_triggers.py` as appropriate.

**Interfaces:** Add `ImportFile`, `ImportReceipt`, receipt-copy association, `ImportSession.source`, and optional `ImportRow.import_file`/source row metadata. Constraints scope keys and foreign keys to a library.

- [x] Add failing model/migration tests for unique file positions, receipt source keys, composite library relationships, and durable receipt retention.
- [x] Apply migration in the test database and observe failure first.
- [x] Implement models and additive migration, including PostgreSQL composite FKs/triggers where needed.
- [x] Verify `makemigrations --check` and integrity tests.

### Task 3: Preview, details, and atomic processing

**Files:** Modify `backend/library/libib_imports.py`, `backend/library/imports.py` only for safe shared helper extraction if required; modify `backend/library/api.py`, `backend/library/schemas.py`; create/modify `backend/tests/test_libib_imports.py` and API tests.

**Interfaces:** `preview_libib(library, files) -> ImportSession`; `libib_details(library, session_id)`; `process_libib_rows(library, session_id, actions) -> per-row results`. One DB transaction per row and receipt.

- [x] Write failing tests for multiple files, ISBN matching, tags, copies, invalid/incompatible rows, skip/import/copy actions, cross-library access, repeats, changed file hashes, and concurrent actions.
- [x] Run focused tests and observe expected failures.
- [x] Implement the separate Libib lifecycle, with locked unique receipt creation and `create_book`/`add_copy`; do not alter Goodreads parsing semantics.
- [x] Re-run Libib tests plus Goodreads regression tests.

### Task 4: Multi-file upload and user interface

**Files:** Modify `backend/library/api.py`, `frontend/src/pages/ImportBooks.vue`, generated schema if project conventions require it; add frontend unit/E2E tests.

**Interfaces:** Multipart upload accepts up to five `files`; Libib routes expose per-file and per-row status; UI displays summary, row decisions, actual batch progress, errors, and resume.

- [x] Add failing API/UI tests for multiple files and progress/resume presentation.
- [x] Run focused tests and observe expected failures.
- [x] Implement bounded upload handling and accessible progressive UI without adding dependencies.
- [x] Run frontend unit tests, typecheck/build, and relevant E2E journey.

### Task 5: Documentation and complete validation

**Files:** Modify README or focused `docs/` guide; review all changed files.

- [x] Document format, field map, limits, copy behavior, duplicate rules, receipts, seven-day temporary retention, and resume process.
- [x] Run focused Libib tests, full backend/frontend suites, lint/typecheck/build, and available E2E tests.
- [x] Verify migration on disposable PostgreSQL when available; otherwise report the unavailable environment.
- [x] Review the entire diff and check Goodreads behavior and clean Git state apart from the supplied CSV.
