# Catalog situations and ordering implementation plan

Goal: replace collection/wishlist switch with multi-select situations, default available+loaned; add remembered sort (newest registration default).
Architecture: retain Book/Copy/Loan ownership and history. Derive statuses from copies/loans. OR within selected statuses, AND with search/tag and same-copy location conditions. Existing sold/donated data remains preserved, not offered as new filters. Wishlist remains exclusive of active copies.
Tech stack: Django/Ninja ORM, Vue/PrimeVue, PostgreSQL, Vitest/Playwright.

Approved design: situations available/loaned/wishlist/lost only; sort newest/oldest inclusion, title asc/desc, first author asc, newest/oldest acquisition (latest copy acquisition per book, null last), newest/oldest publication (unknown last). Stable ID tie-break; no duplicates. Default available+loaned. Empty selection means all four offered situations. Remember sort per account/browser; explicit URL wins. Preserve filters/order/page on detail return, map legacy query links. Acquisition does not change creation date. No schema migration or production data rewrite.

- [x] Backend RED/GREEN tests: OR statuses, duplicates, same-copy location, retired exclusion, default order, all sorting/nulls and library isolation. Implement query helper and optional API parameters, maintain legacy callers.
- [x] Frontend RED/GREEN: URL roundtrip/legacy, sort preference fallback; replace scope selector with Livros, multi-select Situation, compact ordering menu; integrate query/load/return/reset/registration target.
- [x] Relevant suites, full local gate and browser journeys; review whole diff and correct findings.
- [ ] Record checks, backup/deploy per existing authorized manual routine, smoke-check production without modifying user records.

Review rulings: preserve historical lost-copy filtering even after move to wishlist; retain saved order on same-component navbar navigation; four inline checkboxes replace unstable mobile MultiSelect popup. Regression tests added. No session-scoped settings in production inspections.

Verification: 78 backend, 17 Vitest, 24 Playwright passed; Ruff/mypy/Django/schema/types/build passed. First full browser run lost its runner processes; rerun in independent process completed all 24. Encrypted backup manual-20261106T173040Z restored successfully (239 managed media).
