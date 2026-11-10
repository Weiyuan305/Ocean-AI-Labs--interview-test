# Certificate Console Implementation Plan

Spec: [spec.md](spec.md). Approved for implementation by the candidate. All UI and documentation are English.

## Global constraints

Implement A1-A7 with real SQLite persistence, actor-derived tenancy, transactional audit, idempotent issuance, local calendar dates, stable streamed CSV, and one-command startup. Original target freeze: 00:30 Asia/Shanghai; the candidate then requested expanded testing and review. Hard deadline remains 00:45. Work on `implementation/certificate-console` in the existing clean project folder.

## Tasks

1. **Foundation and tenant queries** — create dependency manifests, database/seed, actor resolution, course/list/detail interfaces. Write HTTP tests for isolation, pagination, search validation and prescribed local times; run them red, implement, run green.
2. **Issuance and revocation** — add transactional operations behind the certificate module. Write tests for concurrent same/different keys, 409 conflicts, skip reasons, replay, revocation counts, recoverable rejection and audit rollback; observe failure, implement, verify.
3. **Export and scale** — add shared filtering/order, owned read snapshots, CSV stream and isolated 100,000-row generator. Verify CSV semantics, exact order, 60-second downloads, repeated stability and overlapping HTTP list access.
4. **English console** — implement actor selector, table, search/sort/pagination, course issuance outcomes, details/audit and confirmed revocation using Ant Design. Build/typecheck and exercise the browser workflow, actor switching and export.
5. **Delivery and independent review** — run complete checks, review the whole change with a fresh reviewer, fix material findings, verify clean startup, write README and measured results, export/index native AI evidence, and commit milestones.

## Completion criteria

Each task records its actual verification below. Task 5 distinguishes passing checks from known limitations and candidate-owned answers. Tests cross public HTTP interfaces and use file-backed databases; no mock substitutes for concurrency or performance.

## Progress ledger

- Baseline: document commit 2972cbd; no application code or existing tests. Interface contract is docs/spec.md. Shared interfaces: actor context -> all certificate operations; query description -> list/export; certificate response -> UI; persisted operation -> UI retry.
- Task 1: complete. Two HTTP behavior tests first failed against the empty route scaffold, then passed after database/query implementation.
- Task 2: complete. Four new behavior tests failed for missing issuance/revocation routes, then passed. Concurrent independent clients and audit-failure rollback included. Backend milestone 6f418c5.
- Task 3: complete. CSV test failed before route implementation; then nine backend tests passed. Real HTTP A6 passed (100,000 rows, two full downloads under one second), with independent list access. Full suite later added real-socket A2/A7; ten tests pass.
- Task 4: complete. Production build and full isolated browser smoke passed, including delayed actor response rejection and mobile width. Stable screenshots visually inspected.
- Task 5: engineering checks complete. Independent standards/spec review completed; material findings fixed in 332982c; full suite/build/UI and new-database startup passed. Four native AI snapshots are exported with explicit cutoffs. Candidate answer declaration and final conversation-tail refresh remain submission responsibilities.
- Ruling: preserve the existing user-visible project folder and use an implementation branch; no extra worktree needed for this empty dedicated assessment repository.
- Ruling: accepted Ant Design functional design takes precedence over optional image-led visual concepting. Browser functional verification remains mandatory.
- Ruling: local pip uses system CA bundle; certificate verification remains enabled. Vite updated to 6.4.6 after npm audit identified an affected earlier patch.

- Follow-up review: 17 backend/performance tests, 13 expanded browser checks, original browser smoke, and production build passed. Three UI regressions and four backend security/validation concerns were fixed and independently re-reviewed. Evidence publication is pending candidate-answer privacy redaction; unfinished answers and raw snapshots remain local.
