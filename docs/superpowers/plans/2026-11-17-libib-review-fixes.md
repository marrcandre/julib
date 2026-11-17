# Libib Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Resolve the three important review findings and the four requested improvements without changing Goodreads behavior.

**Architecture:** Keep the existing Libib services, routes, and models. Add database-side receipt/copy/book consistency guards in a new additive PostgreSQL migration; enforce session expiry at the details boundary; make the import screen render file state independently from row state and pin async operations to their starting source/session.

**Tech Stack:** Django 5.2, PostgreSQL 17, pytest, Vue 3, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-17-libib-import-design.md` plus the review findings in the current Codex conversation.

## Global Constraints

- Preserve existing uncommitted implementation and the untracked reference CSV.
- Keep changes on `codex/libib-import`; do not commit, push, deploy, run backups, or use production databases.
- Run migration and PostgreSQL integrity checks only against disposable local test databases.
- Keep Goodreads parser, routes, and payloads unchanged.

## Review Focus

- All-invalid uploads must still show file errors and a no-importable-records state.
- Expired Libib session details must be unavailable even if cleanup has not run.
- Receipt, copy, and book relationships must remain valid under inserts, updates, deletes, and concurrent writes.
- Source switching during upload or processing must not change the request's route or session.
- OAuth E2E expectations must follow the configured frontend origin while retaining CSRF/redirect assertions.
- Reordering, duplicate rows, failed processing retries, and cross-session reimports must preserve receipt idempotency.

## Files and Responsibilities

- `frontend/src/pages/ImportBooks.vue`: independent file/row rendering, explicit empty/error states, pinned async operation context, disabled source controls.
- `frontend/tests/import-books.test.ts`: regressions for invalid-only and partial uploads plus source switching.
- `frontend/e2e/libib-import.spec.ts`: browser-visible all-invalid and partial-file states.
- `backend/library/api.py` and `backend/library/libib_imports.py`: reject expired detail requests using the existing seven-day boundary.
- `backend/tests/test_libib_api.py`: detail access for valid, expired, missing, cross-library, and expired-error sessions.
- `backend/library/migrations/0018_import_receipt_copy_book_integrity.py`: additive PostgreSQL trigger protections for receipt/book/copy agreement.
- `backend/tests/test_postgres_integrity_triggers.py`: allowed and rejected relation mutations, including concurrency.
- `backend/tests/test_libib_imports.py`: order-independent keys, repeated records, failed retry, cross-session replay.
- `frontend/e2e/oauth.spec.ts`: derive origin from the configured Playwright base URL.

## Tasks

### Task 1: File-state UI and async source stability

- [x] Add frontend tests for single/all invalid files, valid plus invalid files, and zero importable records.
- [x] Add tests proving source controls stay disabled during upload and processing.
- [x] Run the focused Vitest tests and confirm they fail for the reported behavior.
- [x] Render file cards independently of rows; show an explicit empty/importability state; snapshot source/session at operation start and disable source/resume controls while busy.
- [x] Run focused Vitest tests and Libib E2E.

### Task 2: Expired session detail authorization

- [x] Add API tests for valid, expired, missing, cross-library, and expired session containing errored files.
- [x] Run focused API tests and confirm the expired detail case fails before the fix.
- [x] Apply the same seven-day boundary to Libib details while preserving `owned()` library scoping and established HTTP error handling.
- [x] Run focused API tests.

### Task 3: PostgreSQL receipt/copy/book integrity

- [x] Add PostgreSQL tests for correct copy, second copy of same book, different same-library book, cross-library copy, and invalid updates to receipt/copy/link.
- [x] Run focused PostgreSQL tests and observe the same-library/different-book case currently succeeds incorrectly.
- [x] Add an additive migration using row locks and triggers to serialize relation changes and enforce book/library agreement at insert and relevant parent/link updates; handle deletion nullification safely.
- [x] Apply all migrations from an empty disposable PostgreSQL database and run the integrity tests, including a concurrent write case.

### Task 4: Idempotency and OAuth E2E robustness

- [x] Add tests for reordered rows, repeated identical rows, same content under different names/sessions, and retry after a failed row transaction.
- [x] Run focused tests before and after any required minimal identity change; retain current identity if the tests confirm it.
- [x] Derive OAuth redirect and `Origin` expectations from Playwright's configured base URL.
- [x] Run OAuth E2E at 5173 and 5175, Libib E2E, then the full E2E suite.

### Task 5: Final verification and review

- [x] Run the full backend and frontend unit suites, Ruff, mypy, Django checks, migration drift check, and frontend build.
- [x] Review the complete diff and confirm Goodreads behavior and the reference CSV are unchanged.
- [x] Leave all work uncommitted on `codex/libib-import` for independent review.
