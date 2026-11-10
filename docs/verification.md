# Verification Results

Environment: macOS 14.6 arm64, Python 3.13.2, Node.js 24.18.0. Test databases are file-backed and isolated from the interactive demo.

## Backend and build

Command: `bash scripts/verify.sh`.

Observed: **17 tests passed**, including tenant isolation, literal search/validation, local dates/DST, bulk outcomes, replay, key conflict, same/different-key concurrency, repeated/concurrent revocation, learner savepoint rollback, audit-failure whole-operation rollback, restart persistence, CSV escaping/order/filtering, and real HTTP scale tests. TypeScript checking and Vite production build completed successfully. Full output: `artifacts/verification.log`.

Real HTTP A6 measured 100,000 matching East rows. First full download: **0.351 seconds**; second: **0.314 seconds**; overlapping list request: **0.107 seconds**. Both exports matched the independently expected serial sequence. Selective search, unfiltered export, West isolation, early disconnect, and real-socket concurrent issuance/revocation also passed. These are local measurements, not a guarantee for every machine.

The first A6 attempt was prevented by sandbox loopback restrictions. It was rerun with permission to bind a local test server; no assertion was disabled. Initial Python installation failed due to the local certificate trust configuration, then succeeded using the system CA bundle.

## UI

Browser/IAB initialization timed out. Playwright used installed Google Chrome as a fallback because bundled Playwright browser binaries were unavailable. The repeatable test is `scripts/ui-smoke.cjs`; it starts its own fresh database and local server. **UI_SMOKE_PASS** was observed for the full workflow. Final result is recorded in `artifacts/ui-verification.log`. Screenshots: `artifacts/console-desktop.png`, `artifacts/console-detail.png`, `artifacts/console-mobile.png`.

The expanded suite `scripts/ui-controls.cjs` passed **13/13 checks** with no failed checks (`artifacts/ui-controls.log`). The initial regression run reproduced three product defects: initial date sorting, export retry, and a delayed revoke failure leaking into another drawer. Their corrected behaviors passed on rerun. Pagination initially failed because the test asserted before rendering completed; the test now waits for the expected rendered rows. The date check also had to exclude Ant Design's invisible measurement row. These test corrections did not change application requirements.

| Control / scenario | Browser evidence |
| --- | --- |
| Administrator selection and delayed previous-actor response | Smoke suite |
| Course selection, issue button, result summary | Smoke and expanded suites |
| Uncertain issuance retry after the server commits but the response is lost | Expanded suite; same key and original 30 issued outcomes |
| All five sortable headers, both directions; initial date click | Expanded suite |
| Search Enter, search button, clear, empty results | Both suites |
| Certificate next/previous page and page size; outcome next/previous page | Expanded suite |
| View details, drawer close, revoke confirmation, cancel, revoked disabled state | Both suites |
| CSV download and failed-export retry | Both suites |
| Initial actor, list, courses, detail retry buttons | Expanded suite |
| Delayed failed revoke after selecting another certificate | Expanded suite |
| Mobile width and uncaught browser exceptions | Smoke suite |

This covers every visible control type and the named error/retry paths; it does not exhaust every possible combination of data, timing, browser, or network failure.

The UI follows the approved functional Ant Design specification; no generated visual concept was requested. Inspect copy, table layout, controls, tenant label, detail/audit, and mobile document width. Functional coverage includes issuance, confirmation/revocation, download, stale actor response rejection, and empty search state.

## Startup and visual checks

The exact startup script was executed with PORT=8002 and a new DB_PATH. It installed dependencies, built the UI, started Uvicorn, served HTML, and returned three initial East certificates. Startup output is in artifacts/startup.log. Restart persistence is also covered by tests for both operation replay and revoked_at.

Final screenshots were visually inspected at desktop 1440x1000 and mobile 390x844. English copy, table hierarchy, tenant identity, control spacing, status labels and drawer audit presentation were checked. The mobile table scrolls within its container; the document does not overflow horizontally. Exit animations were allowed to finish before evidence screenshots.

## Known limitations and warnings

- Upstream Starlette/AnyIO emits one deprecation warning in pytest.
- Ant Design's upstream use-client directives are ignored in this client-only Vite build. The JavaScript bundle is approximately 961 kB before compression and triggers Vite's size warning. No SSR is used.
- npm reported a Vite advisory for the initial selected version; Vite was updated to compatible patch 6.4.6 and npm reported zero vulnerabilities afterward.
- Windows setup, sustained-load behavior, and file-descriptor leak soak tests are not verified.
- Native AI exports remain local pending candidate-answer privacy redaction; they are deliberately excluded from this push.
- AI export completeness and candidate-written answers are separate submission gates; passing application tests does not certify them.
