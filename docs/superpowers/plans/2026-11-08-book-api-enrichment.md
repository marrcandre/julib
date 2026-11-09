# Book API enrichment implementation plan

Approved: restore best-source search with missing-field/cover fallback; keep camera/ISBN matching; detailed provenance in book details, compact mandatory Google credits in catalog. Other backlog UI changes deferred.

Architecture: Google-first discovery; enrich ISBN lookup and selected text candidate from exact-ISBN Google/BrasilAPI CBL and Mercado Editorial/Open Library Books edition endpoints. Preserve Google result order, do not intermix search result lists. Only fill empty fields, never silently overwrite an identified edition or manual data. Known-provider image URLs validated, bounded timeout/fallback, positive warm cache. Keep sources per field and cover separate from storage in Book.provenance JSON (default empty, backward compatible additive migration). Existing books untouched; user uploads invalidate old cover credit while retaining metadata source. New enrichment endpoint is read-only and authenticated; no remote URLs supplied by callers are fetched. No bulk cover replacement.

- [x] RED/GREEN adapter/orchestrator tests: first result missing cover, CBL vs ME, exact edition/ISBN10 conversion, malformed/failed API, image placeholder/redirect, bounded requests/cache.
- [x] Add provenance schema/model migration and persist registration/edits safely, legacy fallback; verify Google metadata/cover credits independent of current storage.
- [x] Selected-candidate enrichment with draft/registration guards, detail sources section, compact catalog links and one adjacent Google logo when relevant.
- [x] Full local proof: `make check-local` passed (94 backend tests, 22 frontend tests, Ruff, mypy, Django checks, migration check and frontend build); `make e2e-local` passed all 30 Playwright journeys. OpenAPI and generated TypeScript schema regenerated; `git diff --check` clean.
- [x] Focused diff review completed after the local proof; no whitespace errors or migration drift found.
- [ ] Independent fresh-context review, fresh encrypted production backup and disposable restore, then manual release, production migration and deployment. This remains blocked because `gh auth status` reports the GitHub token invalid; no production backup, migration or deployment was attempted.

Rulings: enrich only confirmed ISBN across metadata sources; without ISBN retain provider candidate and use no cross-edition metadata merge. Search responses from Google retain their order. Client cover URLs are never used for server image fetches. Time budget bounds worst-case provider cascades; only positive public API responses cached briefly. No existing data backfill or paid/new API account.

Review ruling: httpx eager reads were insufficient for promised resource bounds. Separate async streaming transport now uses hard wall deadline and size caps, with independent oversize/trickle tests. Identified OpenLibrary real redirects to archive.org/download then iaNNN.us.archive.org/view_archive.php and allowed only this controlled chain. Contradictory values from consulted sources are retained as alternatives, not substituted.

Final local proof: 94 backend, 22 Vitest and 30 Playwright passed; Ruff/mypy/Django/schema/types/build passed. Fresh-context review P1 fixed and independently rechecked (11 transport/adapter tests). Real external ISBN probes confirmed OpenLibrary/Archive cover for 1984 and Google cover for The Hobbit. Manual release resumed after user asked to finish; refresh encrypted backup before production DDL.
