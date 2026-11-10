# Certificate Console Implementation Plan

Spec: [spec.md](spec.md). Approved for implementation by the candidate. All UI and documentation are English.

## Global constraints

Implement A1-A7 with real SQLite persistence, actor-derived tenancy, transactional audit, idempotent issuance, local calendar dates, stable streamed CSV, and one-command startup. Freeze engineering at 00:30 Asia/Shanghai; deadline 00:45. Work on `implementation/certificate-console` in the existing clean project folder.

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
- Task 1: in progress.
