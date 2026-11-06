# Catalog pagination and rows implementation plan

Goal: numbered compact pagination, responsive rows per page and stable detail return.
Architecture: bounded page_size (1–100; legacy default 24) and clamped page in private catalog API. Pure pagination functions and reusable accessible pagination component. Covers: selected 3–10 columns times 3/5/8/10 rows (default 5). Cards: actual existing grid (3 mobile / 5 desktop) times rows. List: separate 24/48/96 size. Rows and list size stored per account/browser. URL records effective page size; incoming size/page identify anchor index when layout differs. Resize/view/density change keeps reference book on a recalculated page; page navigation scrolls to results. Filters reset page, detail return restores URL and scroll. No schema migration, data rewrite or public sharing changes.

- [x] RED/GREEN API tests: variable size, bounds, partial/empty/end clamping, stable ordered slices.
- [x] RED/GREEN pure functions: page windows, range, containing-page recalculation, preference validation/isolation, URL roundtrip.
- [x] Implement rows/list controls and pagination with native links, current-page semantics, keyboard support, mobile layout and result range. Remove hardcoded frontend page size. Preserve query/order and browser history.
- [ ] Browser proof: page jumps/back/forward/detail return, resize/density/card/list sizing, persistence, filters/deletion clamping, mobile bounds; review, local gates and backup/manual release.

Additional requests recorded for next iteration (not part of this implementation): save/cancel at top as well as bottom or top-only; toast at top right or centered; cover click opens cover editing. Cover click is feasible and should use an accessible button, same edit/upload flow and unsaved preview, with no implicit save. Existing UI remains until that follow-up.

Review found no important defects. Validation: 79 backend, 21 Vitest, 27 Playwright; Ruff/mypy/Django/schema/types/build passed. Backup manual-20261106T181915Z downloaded and restored, 248 managed media. Additional requests remain explicitly in docs/backlog.md.
