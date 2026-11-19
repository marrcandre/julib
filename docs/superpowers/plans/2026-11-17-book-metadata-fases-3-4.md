# Julib Book Metadata Phases 3 and 4 Implementation Plan

> **For agentic workers:** execute inline in the main repository; do not commit, push, merge, deploy, run production migrations, or enrich production data.

**Goal:** Add subtitle, description, and bibliographic subjects to book metadata and safely enrich only missing fields in existing books.

**Architecture:** Additive Django fields and API contracts expose the three fields to private and public catalogs while keeping provenance private. A dated ISBN Range Message snapshot classifies registration groups reproducibly. Providers are queried at most once per source, candidates are retained briefly, and declarative per-field priorities resolve values independently. The existing command remains preview-first and applies only still-empty fields under row locks.

**Tech Stack:** Django, Django migrations, Django Ninja/Pydantic, Vue 3, TypeScript, pytest, PostgreSQL.

**Spec:** Approved consolidated Fases 3–4 plan; details recorded in the Codex plan and user-approved continuation instructions.

## Global Constraints

- Add `subtitle`, `description`, and `subjects`; subjects remain independent of personal tags.
- Brazilian ISBN registration groups use CBL → Mercado Editorial → Open Library → Google Books; other groups use Open Library → Google Books → CBL → Mercado Editorial.
- Each field has an independent declarative priority list; query a provider at most once and stop when no unresolved field can benefit from more candidates.
- Existing values are never overwritten by enrichment; manual edits remove only provenance for edited fields.
- Description is plain safe text; provider values outside documented limits are rejected as a whole, never silently truncated.
- Tests use mocked provider responses. Database migration and locking checks use disposable local PostgreSQL only.
- Preserve the two existing local changes, including the CSV; do not perform destructive Git operations.
- No production migration, production enrichment, production data changes, push, deploy, or workflow activation.

## Field Limits

- `subtitle`: up to 500 Unicode code points.
- `description`: up to 20,000 Unicode code points after safe HTML-to-text conversion.
- `subjects`: up to 50 distinct nonempty strings, each at most 200 Unicode code points.
- Reject an over-limit field value without truncation; continue resolving other fields and report rejected provider values.
- A read-only sample for ISBN `9788535914849` showed BrasilAPI/CBL returning a Portuguese synopsis and duplicate subjects, Open Library returning an ISBN-matched edition detail, and Google Books returning HTTP 429. This validates the actual field names and the need for deduplication/fallback; it does not establish absolute provider maxima.
- The limits are documented operational ceilings rather than claimed API maxima. Tests cover exact boundaries and over-limit rejection; retain whole provider strings and never truncate them.

## Review Focus

- ISBN-10/13 normalization, 978/979 registration-group rules, and Brazilian versus other groups use the pinned range snapshot.
- A lower-priority candidate cannot beat an unqueried higher-priority source for that individual field.
- Duplicate, blank, malformed, HTML, and oversized provider values do not become unsafe or silently truncated data.
- Concurrent manual edits and library boundaries remain protected in `enrich_books`.
- Public catalog exposes new fields but never provenance; subjects never enter personal tags.

## Tasks

### Task 1: Versioned ISBN classification and field resolver

**Files:** Add `backend/library/data/isbn_range_message_2026-11-17.xml`; add classifier module and tests; modify `backend/library/providers.py` and provider tests.

- [x] Pin the official International ISBN Agency Range Message snapshot, source URL, retrieval date, and SHA-256.
- [x] Test classification in Brazilian, English, other international, 979, invalid, and unclassified ISBN cases.
- [x] Test declarative per-field priority resolution, higher-priority pending candidates, rejected oversized values, and provider query efficiency.
- [x] Run focused tests red before implementation.
- [x] Implement snapshot-backed classification and candidate collection/resolution; normalize subjects and plain-text descriptions without truncation.
- [x] Run focused tests and provider regression suite.

### Task 2: Additive model/API/persistence contracts

**Files:** Modify `backend/library/models.py`, `schemas.py`, `services.py`, `presentation.py`, `api.py`; add migration and model/API tests; regenerate frontend OpenAPI types.

- [x] Add tests for defaults, authenticated/public responses, manual edits, per-field provenance preservation, and subject/tag independence.
- [x] Run migration and locking tests with local test databases; migration test confirms existing row values survive 0019.
- [x] Implement additive defaults and explicit field limits; public serializers omit provenance.
- [x] Run focused backend checks and migration checks.

### Task 3: Book details and editing UI

**Files:** Modify `frontend/src/pages/BookDetails.vue`, relevant book edit form, and generated API types; add/update Vitest coverage.

- [x] Test subtitle placement, accessible collapsed description, separate subjects section, and editing all three fields.
- [x] Implement safe text rendering and distinct subject presentation without tag controls or filters.
- [x] Run frontend tests and type/build checks.

### Task 4: Existing-book enrichment and reporting

**Files:** Modify `backend/library/management/commands/enrich_books.py`, tests, `docs/operations.md`, and `docs/backlog.md`.

- [x] Test preview counts, queried providers, exact ISBN correspondence, source/fill/preserve/failure reporting, bounded description preview, preview-only defaults, `--apply`, concurrency, isolation, and repeat-run idempotency.
- [x] Implement candidate-aware eligibility for the new fields, lock/recheck before writes, preserve unrelated provenance, and report structured provider outcomes.
- [x] Update roadmap only after validations passed.
- [x] Run backend/frontend suites, E2E on disposable PostgreSQL, migration/locking checks, `git diff --check`, diff review, and `make check-local`.

## Completion

Leave the work uncommitted and on the feature branch for final user review. Report files/migration, decisions, checks, Git state, limitations, and risks. Do not integrate into `main`.

## Validation Results

- `make check-local`: passed (Ruff, formatting, mypy, Django checks, migrations, 264 backend tests, 61 frontend unit tests, production build).
- `make e2e-local` against disposable PostgreSQL: passed (43 Playwright tests).
- `git diff --check`: passed.
- `docs/backlog.md` records phases 2–4 as implemented and publication pending; no integration or publication was performed.
