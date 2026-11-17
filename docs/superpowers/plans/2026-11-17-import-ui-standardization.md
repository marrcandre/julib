# Import UI Standardization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing unified import screen clear and visually consistent for Goodreads and Libib while preserving each importer's behavior and API contract.

**Architecture:** Keep both sources on `ImportBooks.vue` and retain the existing routes and source-specific processing code. Reorganize presentation around a shared, prominent source selector and shared instruction/upload area; keep source-specific preview, selection, progress, and result data in the current page. Update the catalog menu label and add focused tests for navigation and both source experiences.

**Tech Stack:** Vue 3, TypeScript, PrimeVue, Vitest, Vue Test Utils, Playwright, Vite.

**Spec:** User-provided specification, "Julib — Padronização das interfaces de importação Goodreads e Libib" (2026-11-17).

## Global Constraints

- Keep one import menu entry labeled `Importar livros`.
- Preserve `/importar` and `/bibliotecas/:libraryId/importar` and existing sessions.
- Preserve the Goodreads and Libib parsers, services, API contracts, identification, idempotency, copy creation, and validation behavior.
- Do not implement bibliographic enrichment or change models/migrations.
- Keep Goodreads limited to one CSV (3 MiB); keep Libib limited to five CSVs, 5 MiB each and 25 MiB total.
- Do not change the supplied reference CSV.
- Leave all changes uncommitted; do not push, deploy, publish, touch production, or alter GitHub Actions.

## Review Focus

- Switching source while an upload or process is active must remain disabled and not redirect results to the other source; covered by existing import page tests.
- Invalid Libib files and sessions with no importable rows must remain visible with their current validation feedback; covered by existing import page tests and E2E.
- Reopening existing Goodreads and Libib sessions must continue using the existing source-specific endpoints; add/retain coverage in frontend tests.
- Multiple Libib files must remain attached as individual multipart files; covered by existing import page tests and E2E.
- Narrow screens must allow preview tables to scroll horizontally without clipping page controls; verify through existing responsive styles and E2E where supported.

## File Structure

- `frontend/src/components/CatalogToolbar.vue`: rename the single import menu item, preserving its route command.
- `frontend/src/pages/ImportBooks.vue`: present the source choice, consistent instructions/upload, and shared visual hierarchy while retaining the current source-specific data and operations.
- `frontend/src/style.css` (or page-scoped styles in `ImportBooks.vue` if this remains the established local choice): add only import-specific responsive and focus styling needed by the unified screen.
- `frontend/tests/import-books.test.ts`: cover source selector and source-specific instructions/upload/session behavior.
- `frontend/tests/catalog.test.ts` or a focused toolbar test: cover the menu label and unchanged import navigation.

### Task 1: Rename the single import menu item

**Files:**
- Modify: `frontend/e2e/libib-import.spec.ts`
- Modify: `frontend/src/components/CatalogToolbar.vue`

**Interfaces:**
- The import page continues to use `/imports` and `/imports/libib/sessions` to load resumable sessions.
- The menu command continues routing to `/importar` or `/bibliotecas/:libraryId/importar` according to the active route.

- [ ] Add an E2E case that opens the catalog's secondary menu, sees exactly one `Importar livros` item, and follows it to `/bibliotecas/77/importar`.
- [ ] Run the focused E2E case and confirm it fails because the menu still uses the old label.
- [ ] Change only the menu label; preserve the existing route command.
- [ ] Run the focused E2E case and confirm the menu label and active-library route pass.

### Task 2: Standardize the shared import presentation

**Files:**
- Modify: `frontend/src/components/CatalogToolbar.vue`
- Modify: `frontend/src/pages/ImportBooks.vue`
- Modify: `frontend/src/style.css` only if shared styles do not already cover the screen

**Interfaces:**
- Keep all current `api`, `post`, session, file, row, selection, and process payload shapes unchanged.
- Keep the existing source-specific upload routes and limits unchanged.
- Continue linking to the Goodreads help URL already recorded in project docs and the Libib export/CSV help URLs in `docs/importacao-libib.md`.

- [ ] Add a focused Vitest case that asserts Goodreads instructions and single-file input initially, then Libib instructions and a multiple-file input after choosing Libib; also assert the collection/location distinction and existing-session resume actions.
- [ ] Run the focused import page test and confirm it fails on the missing detailed instructions.
- [ ] Make source selection a prominent, keyboard-accessible group with selected-state feedback.
- [ ] Give both sources a consistent instruction/upload panel; explain Goodreads export, recognized fields, matching, selection, and confirmation; explain Libib multi-file export, identification, existing books, copy counts, unmapped fields, and collection versus Julib location.
- [ ] Keep preview tables, selection rules, validation messages, progress, result, expiry, and resume content source-specific where their meanings differ; align spacing and hierarchy around shared page patterns.
- [ ] Preserve `role=alert`/`role=status`, visible focus, labels, horizontal table scrolling, and responsive stacking.
- [ ] Run the focused import page tests and confirm source instructions, existing upload, session, and partial-progress behavior pass.

### Task 3: Verify import regressions and build

**Files:**
- Review: `frontend/src/pages/ImportBooks.vue`, `frontend/src/components/CatalogToolbar.vue`, and their tests.

- [ ] Run the full frontend Vitest suite.
- [ ] Run the existing Goodreads and Libib processing test suites.
- [ ] Run the existing Libib import E2E test and any relevant responsive checks supported by the suite.
- [ ] Run the frontend build, review the full diff, and confirm the reference CSV is untouched and Git remains uncommitted on `codex/import-ui-standardization`.

### Task 4: Distinguish completed imports from empty previews

**Files:**
- Modify: `frontend/src/pages/ImportBooks.vue`
- Modify: `frontend/tests/import-books.test.ts`

**Interfaces:**
- Derive completion from existing source-specific row outcomes; do not add or change API payloads.
- Completed Libib candidates must not show the empty-importable notice; invalid-only sessions must keep it.

- [ ] Extend the existing Goodreads and Libib processing tests to assert a visible `Importação concluída` state after all relevant rows finish and no contradictory empty-importable notice for completed Libib rows.
- [ ] Run the focused Libib completion test and confirm it fails on the old generic result heading/empty notice.
- [ ] Derive finished state from terminal row outcomes for each source, show partial-result feedback while eligible rows remain, and suppress the Libib empty-importable notice after completion.
- [ ] Run all focused import-page tests and confirm completed, partial, invalid-only, and resume states pass.

### Task 5: Treat already-imported Libib rows as terminal

**Files:**
- Modify: `frontend/src/pages/ImportBooks.vue`
- Modify: `frontend/tests/import-books.test.ts`

**Interfaces:**
- `data.already_imported` means the durable Libib receipt already completed this row; no API changes are needed.
- The completed-session summary must include such rows in its ignored/already-imported count.

- [ ] Add a test for reopening a session containing only a row with `data.already_imported=true`; assert the completed state, the already-imported count, and no empty-importable notice.
- [ ] Run the focused test and confirm it fails because the screen reports an empty session.
- [ ] Treat already-imported rows as terminal for the session summary and count them once in the existing ignored/already-imported total.
- [ ] Run the full import-page test file and confirm this case and invalid-only cases both pass.

---

## Self-Review

- Spec coverage: menu and unified source choice (Tasks 1-2); instructions and upload (Task 2); preserved source behavior/session states and accessible responsive layout (Tasks 1-2); tests/build and diff review (Task 3); no enrichment/backend behavior/migration changes (Global Constraints).
- Task steps are limited to focused tests, UI changes, and verification; no service or API extraction is planned.
- Review focus conditions are assigned to existing or newly added frontend tests and responsive E2E validation.
- Plan length is proportional to this UI-only change.
