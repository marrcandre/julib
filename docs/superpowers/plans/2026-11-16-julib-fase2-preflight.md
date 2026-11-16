# Julib Fase 2 Preflight Implementation Plan

> **For agentic workers:** Execute inline in this worktree; do not commit, push, merge, deploy, re-enable Actions, upload backups, or alter production.

**Goal:** Prepare auditable local changes for PostgreSQL trigger security, backup separation and private artifact handling, and publication operations.

**Architecture:** Add a forward-only Django migration that pins trusted schemas and schema-qualifies application tables; exercise the actual triggers on PostgreSQL 17. Keep backup generation read-only and add a separate manual artifact workflow that receives an already encrypted local artifact, validates and hashes it, then uploads it to the private backup repository with finite retention.

**Tech Stack:** Django migrations, PostgreSQL 17, pytest, GitHub Actions `workflow_dispatch` and `actions/upload-artifact`.

**Spec:** User request on 2026-11-16, following the approved preflight recommendations.

## Global Constraints

- Base commit: `0d73238676e6ca41af846b277b134879646c752c`.
- Do not modify migrations `0010`–`0013`.
- Do not apply migrations in production or alter production configuration/data.
- Do not transfer or regenerate backups, run `cleanup_imports`, re-enable Actions, deploy, or commit/push/merge.
- No secrets, key material, or backup files in this repository.
- Use PostgreSQL 17 for integration tests; test valid and cross-library trigger relations and temporary-table shadowing.
- Keep backup creation, data maintenance, and artifact upload independent.

## Review Focus

- Trigger SQL resolution under hostile `pg_temp` objects: test all four functions with colliding temp table names.
- Cross-library writes and parent-library changes: assert constraint violations and same-library successes for tags and import rows/copies.
- Artifact intake: reject absent, structurally invalid, oversized, hash-mismatched, or unsafe-name files before upload.
- Repository boundary: upload workflow only operates in the private backup repository and grants least permissions.
- Retention/recovery: document 30-day artifact retention, integrity evidence, and retrieval/descryption/restore steps.

## Tasks

### Task 1: PostgreSQL 17 trigger hardening

**Files:** Create `backend/library/migrations/0014_secure_integrity_trigger_search_path.py`; create `backend/tests/test_postgres_integrity_triggers.py`.

- Write PostgreSQL-only tests for valid same-library relationships, rejected cross-library inserts and parent moves, and temp-table shadowing of each referenced `library_*` relation.
- Run tests against a local PostgreSQL 17 database to confirm the intended failure before the migration exists.
- Add `ALTER FUNCTION public.<function>() SET search_path = pg_catalog, public, pg_temp` and explicit `public.` qualification for every application table reference. Make the migration irreversible.
- Run the tests and Django migration checks; inspect migration SQL and current local fixture data compatibility without targeting production.

### Task 2: Backup and artifact workflows

**Files:** Modify `ops/backup-workflow.yml.example`; create `ops/upload-existing-backup-workflow.yml.example`; add workflow validation tests if a project seam exists.

- Remove `cleanup_imports` from backup generation and keep database/media capture, encryption, and current integrity behavior.
- Create an independent, manually dispatched workflow for the private backup repository. Accept an existing encrypted file through an explicit operator-provided runner path, validate envelope structure/size/hash, produce a SHA-256 sidecar, and upload it with 30-day retention. Restrict permissions and enforce a private repository guard.
- Provide a documented, approval-aware manual dispatch procedure; never add a path to the backup file or key to the public code repository.
- Verify the workflow is syntactically valid and no automatic trigger or deploy/migration dependency is present.

### Task 3: Operations documentation and verification

**Files:** Modify `docs/operations.md`.

- Separate backup from data maintenance; document read-only backup behavior, workflow activation as an explicit later operation, 30-day artifact retention, existing-backup publication, integrity checks, recovery, migration `0014` rehearsal, and concise manual Google OAuth/callback validation.
- Run backend tests, PostgreSQL 17 integration tests, project checks, workflow validation, secret/file diff checks, and `git diff --check`.
- Review changed files and report remaining limitations. Keep the worktree uncommitted for user review.
