# `enrich_books` Reports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Export concise and detailed, library-scoped enrichment reports in preview and apply modes without duplicate provider calls.

**Architecture:** Extend the existing Django management command to build aggregate and per-field rows from its one provider result per book. In apply mode, derive persisted statuses only from fields returned by the existing locked save function. Keep stdout behavior and make file export opt-in.

**Tech Stack:** Django management command, Python `csv`/`json`, pytest-django.

**Spec:** `docs/superpowers/specs/2026-11-20-enrich-books-reports-design.md`

## Global Constraints

- Preview remains the default; `--apply` is still required to write.
- Every query and report is scoped to the explicitly required `--library`.
- Do not make duplicate provider requests to populate reports.
- Do not report candidate fields as persisted unless the locked save confirms persistence.
- Never emit credentials, tokens, or sensitive data.
- No permanent report storage, migration, GUI, or production enrichment.

## Review Focus

- Empty eligible set and no provider results: ensure zero counts and valid empty exports.
- Provider HTTP 429: ensure it increments only its provider failure metric and produces safe field statuses.
- Already-populated fields: ensure they appear as `já preenchido` without replacing values or provenance.
- Concurrent edit between lookup and save: ensure preview candidate is not claimed as persisted in apply report.
- CSV/JSON special characters and Unicode: ensure valid machine-readable output.

---

### Task 1: Build and export reports

**Files:**
- Modify: `backend/library/management/commands/enrich_books.py`
- Test: `backend/tests/test_book_metadata_enrichment.py`

**Interfaces:**
- CLI: `--report-format {csv,json}` and `--report-file PATH` must be supplied together; neither is required.
- Detail row keys: `book_id`, `isbn`, `title`, `field`, `status`, `value`, `provider`.
- JSON report keys: `mode`, `summary`, `details`.

- [x] **Step 1: Add failing tests** for CSV/JSON preview exports; empty/no-result reports; provider 429 failures; already-filled fields; and preview versus apply under concurrent field change. Assert one enrichment call per book and that apply reports only persisted fields.
- [x] **Step 2: Run focused tests and confirm failure** with `uv run --project backend pytest backend/tests/test_book_metadata_enrichment.py -q`.
- [x] **Step 3: Implement** paired CLI arguments, stable summary counters, per-book/per-field rows with the five statuses, and optional CSV/JSON serialization. Build reports using the existing lookup result; do not issue any additional provider request. Retain existing stdout JSON keys and add a concise human-readable summary.
- [x] **Step 4: Run focused tests** with `uv run --project backend pytest backend/tests/test_book_metadata_enrichment.py -q`.
- [x] **Step 5: Document** exact preview and apply report commands plus interpretation in `docs/operations.md`; explicitly state apply is local/disposable only for validation and production requires separate authorization.
- [x] **Step 6: Run validation** with `make check-local`, `make e2e-local`, and `git diff --check`.
- [ ] **Step 7: Review** diff for library scoping, sensitive values, accurate persistence status, and no extra provider calls.
