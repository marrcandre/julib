# Multiple Libraries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an authenticated Julib account access and switch among its authorized libraries, and let explicitly authorized accounts create libraries without weakening existing data isolation.

**Architecture:** Preserve the existing `Library` and library-owned records. Add membership roles and an explicit user capability for creating libraries. Put the active library ID in each authenticated UI route and pass it with every scoped API request; the backend resolves it through the requesting user's memberships.

**Tech Stack:** Django 5.2, Django Ninja, PostgreSQL, Vue 3, TypeScript, Vue Router, PrimeVue.

**Spec:** User request in `/home/marco/.codex/attachments/bf82d749-641d-444d-803a-4f584d309a2a/Texto colado.txt`, with the active-library approach selected in conversation: URL per browser tab.

## Global Constraints

- Preserve the current library's primary key and all existing library-owned data and media references.
- Keep membership many-to-many, and keep library access checks in the backend on every scoped operation.
- The library ID in a URL or request header is untrusted input and must be resolved against the authenticated user's memberships.
- Library creation permission is explicit user state, separate from technical staff and membership role.
- No public library signup, invitations, member-management UI, email services, or global administration UI.
- No change to public token-based catalog sharing except ensuring it remains scoped to its library.
- Keep personal preferences on User/browser; only library-owned settings belong to Library or a future library-settings model.

## Review Focus

- A user changes the library ID in the URL/header: all scoped endpoints reject non-membership before accessing records (Task 2).
- A valid record ID from another library is supplied through a relationship or bulk operation: the relation is rejected (Task 2).
- Library creation is attempted by a user without the explicit capability, or its transaction fails midway: no library or membership is created (Task 3).
- Two tabs select different libraries and one switches while requests are pending: each tab keeps its own context and stale results do not display (Task 4).
- Existing users, blank library names, data IDs, media IDs, and public links survive migration and old entry URLs still resolve safely (Tasks 1 and 4).

---

### Task 1: Add membership roles and explicit create capability

**Files:**
- Modify: `backend/library/models.py`
- Create: `backend/library/migrations/0010_membership_role_user_can_create_libraries.py`
- Modify: `backend/library/auth.py`
- Modify: `backend/library/management/commands/bootstrap_library.py`
- Modify: `backend/library/schemas.py`
- Modify: `backend/library/api.py`
- Test: `backend/tests/test_access.py`
- Test: `backend/tests/test_library_settings.py`

**Interfaces:**
- Add `User.can_create_libraries: bool`, default false.
- Add `Membership.role: Literal["admin", "member"]`, default `"member"`.
- `GET /api/v1/session` returns `can_create_libraries` and accessible libraries as `{id, name, role}`; retain user identity and personal preferences.
- `require_library(request)` resolves the positive integer `X-Library-ID` header through the authenticated user's memberships. If the header is absent, allow the sole membership for backward compatibility; with zero or multiple memberships, return 403. Malformed or unauthorized IDs always return 403; never fall back to `.first()`.

- [ ] Add tests that session lists only memberships, defaults `can_create_libraries` to false, and request context accepts the sole membership, rejects missing context for multiple memberships, and rejects malformed or non-member IDs.
- [ ] Run the targeted tests and confirm the new assertions fail for the expected missing behavior.
- [ ] Add an additive migration for role and capability; set existing `is_staff` memberships to `admin`, leave other memberships as `member`, and provision `can_create_libraries=True` for the existing `is_staff AND is_superuser` account. Leave Library and owned rows untouched.
- [ ] Change bootstrap and Google account provisioning to grant the explicit create capability to the configured administrative account, while authorization checks use the stored boolean. Make bootstrap idempotent, retain current membership access, and keep existing staff memberships at `admin`.
- [ ] Implement the scoped library resolver and update session/API schemas.
- [ ] Run `cd backend && uv run pytest tests/test_access.py tests/test_library_settings.py -q` and confirm pass.

### Task 2: Scope API operations and validate cross-library relations

**Files:**
- Modify: `backend/library/api.py`
- Modify: `backend/library/services.py`
- Modify: `backend/library/circulation.py`
- Modify: `backend/library/imports.py`
- Modify: `backend/library/media.py`
- Modify: `backend/library/admin.py`
- Modify: `backend/library/models.py`
- Create: `backend/library/migrations/0011_library_composite_relationships.py`
- Test: `backend/tests/test_access.py`
- Test: `backend/tests/test_invariants.py`
- Test: `backend/tests/test_loans.py`
- Test: `backend/tests/test_media.py`
- Test: `backend/tests/test_library_settings.py`

**Interfaces:**
- Every existing authenticated library-owned endpoint continues to call `require_library(request)`; it now requires the validated header established in Task 1.
- Service functions continue receiving a resolved `Library` object, never an untrusted library ID.
- Rename the library through the validated active library and allow only `Membership.role == "admin"`; retain the current technical-account check for technical tools only.

- [ ] Add API tests for books, loans, people, locations, tags, imports, media signatures, and public-link administration using a second library; assert cross-library reads/writes fail and valid access remains.
- [ ] Add relation tests for foreign copy/person/book/location/tag IDs, including bulk location and import-row operations; confirm each fails before mutation.
- [ ] Run the focused tests and verify they fail for missing header scoping or cross-library validation.
- [ ] Audit every route in `api.py`, including search/enrichment, aggregate counts, pagination, import/export, upload attachment, and share-link actions; ensure library-scoped handlers resolve context before querying or mutating data.
- [ ] Ensure services and Django admin validate library equality for all foreign-key and many-to-many relationships. Add PostgreSQL composite foreign keys for location parent, copy book/location, loan copy/person, and registration book/copy; retain application validation for Book.tags and ImportRow, which lack a shared library column. Do not add a duplicated library field to ImportRow solely for an extra constraint.
- [ ] Run the focused backend tests and confirm pass.

### Task 3: Library listing, creation, and per-library settings

**Files:**
- Modify: `backend/library/schemas.py`
- Modify: `backend/library/api.py`
- Modify: `backend/library/auth.py`
- Modify: `backend/library/models.py` only if an existing setting is found to require a per-library field
- Test: `backend/tests/test_library_settings.py`
- Test: `backend/tests/test_access.py`

**Interfaces:**
- `POST /api/v1/libraries` accepts `{name: string}`; trim whitespace, require 1–150 characters, and create Library plus admin Membership in one `transaction.atomic()` block.
- `GET /api/v1/libraries` returns only the caller's memberships as `{id, name, role}`.
- `PUT /api/v1/library/name` uses `X-Library-ID` and requires admin role for that library.
- Duplicate library names are allowed; IDs, not names, define identity.
- Initial configuration uses existing Library fields/defaults. Do not add a generic settings table unless a concrete library setting is missing from the existing model.

- [ ] Add tests for authorized creation, unauthorized creation, trimmed/blank/oversized names, duplicate names, membership role, only-own-library listing, and transaction rollback on simulated membership failure.
- [ ] Run the focused tests and verify expected failures.
- [ ] Implement endpoints with creation permission checked from the stored user capability and atomic library/membership creation.
- [ ] Move library rename authorization from `technical()` to the active membership's admin role; keep user theme/catalog preferences personal.
- [ ] Run `cd backend && uv run pytest tests/test_library_settings.py tests/test_access.py -q` and confirm pass.

### Task 4: URL-per-tab selection and responsive selector

**Files:**
- Modify: `frontend/src/main.ts`
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/generated/schema.d.ts` via the repository's schema export command
- Modify: `frontend/src/pages/Settings.vue`
- Modify: `frontend/src/pages/Books.vue`, `Loans.vue`, `Locations.vue`, and `ImportBooks.vue` only where route parameter or request transition requires it
- Modify: `frontend/src/style.css`
- Test: `frontend/tests/api.test.ts`
- Test: `frontend/e2e/library.spec.ts`
- Test: `frontend/e2e/library-branding.spec.ts`

**Interfaces:**
- Authenticated canonical routes use `/bibliotecas/:libraryId/livros`, `/livros/:id`, `/emprestimos`, `/locais`, `/importar`, and `/configuracoes` beneath the library context.
- The API client derives `X-Library-ID` from the active route for scoped calls; session and library-list/create calls remain unscoped.
- Legacy authenticated routes redirect to a validated last-used library ID, falling back to the first accessible membership; inaccessible stored IDs are discarded.
- Active selection is saved under a user-keyed localStorage key only as a startup preference. Each open tab's route remains authoritative.

- [ ] Add API-client tests that scoped calls send the route's library ID, while session/list/create and public catalog calls do not; verify malformed/unscoped routes never reuse a stale library header.
- [ ] Add E2E coverage for listing and switching, create option visibility, create-and-open-empty-catalog, browser title updates, responsive selector, legacy route redirect, and two tabs retaining distinct library URLs.
- [ ] Run targeted tests and verify missing context/selector behavior fails as expected.
- [ ] Implement route guards after session loading, redirects preserving query/hash, selector loading/error/long-name behavior, and a keyed page transition that clears old component state before loading the new library.
- [ ] Keep the public `/colecao/:token` and `/sobre` routes outside authenticated library route nesting.
- [ ] Update Settings to show the active library name and only expose editing to its membership admin.
- [ ] Regenerate the OpenAPI TypeScript schema with `make schema` (root `scripts/export_schema.py` and `openapi-typescript`).
- [ ] Run `cd frontend && npm test -- --run tests/api.test.ts`, TypeScript/build checks, and the relevant Playwright specs when local services and E2E credentials are available.

### Task 5: Preservation, regression, and operational checks

**Files:**
- Modify tests across `backend/tests/` and `frontend/e2e/` as required by the new authenticated route contract.
- Modify: `README.md` and `docs/operations.md` for the new account/library flow and migration checks.

**Interfaces:**
- Old single-library URLs remain redirects, not alternate authorization paths.
- Public catalog tokens remain bound to the original library ID.
- No backup, migration, or production deployment is performed by this implementation task.

- [ ] Add a migration test recording existing library/member/owned-row primary keys and counts before/after applying the new migration; assert no owned rows or media identifiers change.
- [ ] Update existing test helpers and E2E URLs to provide a valid active library context.
- [ ] Run backend suite, frontend unit suite, schema checks, and build; run E2E if its disposable database and session fixture are available.
- [ ] Review generated schema and diff for migration reversibility, default RLS/grants, public token behavior, and absence of invite/member-management endpoints.
- [ ] Record any unavailable environment-dependent checks without claiming them as passed.
