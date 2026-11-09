# Safe Book Reprocessing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a resumable Django command that enriches missing metadata and covers for existing books without overwriting populated fields.

**Architecture:** A management command selects only ISBN-bearing books with enrichment gaps, calls `library.providers.enrich_book` outside database transactions, and defaults to preview. With `--apply`, it locks each row and fills only fields that remain empty, merging provenance for those fields only. No API endpoint, schema migration, or new dependency is needed.

**Tech Stack:** Django management commands, existing provider pipeline, pytest-django, PostgreSQL.

**Spec:** `docs/superpowers/specs/2026-11-08-safe-book-reprocessing-design.md`

## Global Constraints

- Process only the requested library and exact-ISBN matches.
- Preview is the default; `--apply` is required for writes.
- Never overwrite populated fields, existing cover URLs/IDs, or source/source_id.
- Skip books without valid ISBN and never create books or copies.

## Review Focus

- A user's edit made while provider lookup is in progress must win; test that updates happen only after row lock/recheck.
- A Cloudinary/manual cover must be preserved; test populated cover URL/ID remain identical.
- Existing metadata and provenance outside updated fields must remain identical; test mixed populated/missing values.
- A second run must not change an already enriched row; test resumability/idempotency.
- Books in another library or without ISBN must not be processed; test scope and eligibility.

### Task 1: Safe bulk enrichment command

**Files:**
- Create: `backend/library/management/commands/enrich_books.py`
- Modify: `backend/tests/test_cover_enrichment.py`
- Modify: `docs/operations.md`

**Interfaces:**
- Consumes: `library.providers.enrich_book(dict[str, Any]) -> dict[str, Any]` and `Book.provenance`.
- Produces: `python manage.py enrich_books --library ID [--limit N] [--delay SECONDS] [--apply]`; dry-run unless `--apply` is set.

- [x] Add tests for preview-only behavior, apply fills only blank fields/provenance, populated values and source identifiers remain unchanged, no ISBN/empty result ignored, library scoping, and repeat run idempotency.
- [x] Run focused tests and confirm expected failures before implementation.
- [x] Implement provider calls outside locks; on apply, lock each target row and re-check blank fields before merging/saving only eligible updates.
- [x] Run focused tests, then the complete backend check suite.
- [x] Document preview and apply invocations plus scope/safety in `docs/operations.md`.
- [x] Commit the implementation on the isolated feature branch.

## Execution

Implement natively in this session. Do not run the command against production without first producing and validating a fresh encrypted backup; inspect the preview summary before any production writes.

Review finding fixed: `--limit` now counts valid-ISBN candidates, so earlier invalid entries cannot starve later books. Regression test verified red→green. The initial-eligibility snapshot also prevents repopulating a field that was filled when lookup began but cleared while the API request was in flight.
