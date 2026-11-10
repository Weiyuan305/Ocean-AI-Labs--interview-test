# Certificate Admin Console

A local multi-tenant training certificate console built with React, TypeScript, Ant Design, FastAPI, and SQLite. Administrators search certificates, issue them to eligible course learners, inspect audit history, revoke certificates, and export tenant-scoped CSV data.

## Quick start

Prerequisites: Python 3.11+ (tested 3.13.2), Node.js 22+ (tested 24.18.0), npm, and internet access for the initial dependency installation. macOS/Linux shell. No database server is required.

```bash
bash scripts/start.sh
```

Open http://127.0.0.1:8000. The command creates a virtual environment, installs locked Python/Node dependencies, builds the frontend, initializes demo data if missing, and starts the complete application. Repeated startup preserves certificates, revocations, and idempotency results. `PORT` and `DB_PATH` can override the listening port and database file. Stop with Ctrl+C.

On macOS, startup uses the system CA certificate bundle for pip if available; it does not disable certificate verification. For development-only frontend work, `cd frontend && npm run dev` requires a separately configured API proxy; the supported complete application is the one-command production build above.

## Demonstration identities

| Actor | Tenant | Time zone | Bearer token |
| --- | --- | --- | --- |
| alice@east.test | East | Australia/Sydney | east-demo-token |
| bob@west.test | West | Australia/Perth | west-demo-token |

These are intentionally public demonstration identities, selectable in the UI. They are not production authentication. The server derives tenant ownership from the token; it rejects caller-supplied tenant query selectors.

Both tenants have a Safety 101 course and Alex Lee. Course IDs: East Safety 101 = 1, West Safety 101 = 2, East First Aid = 3 (empty course), East Date Ordering = 4. Learners in each Safety 101: Alex is completed/uncertified, Casey is incomplete, Jordan is already certified. Initial certificate IDs: East Jordan = 1, West Jordan = 2; IDs 3 and 4 are same-local-date ordering fixtures.

## Verification

After startup has installed dependencies:

```bash
bash scripts/verify.sh
```

This runs the full pytest suite with isolated temporary databases and a real local HTTP server for scale/concurrency checks, followed by TypeScript checking and a production build. It does not change the demo database. The HTTP test requires permission to bind a loopback port.

Optional real browser smoke test (its server and data are isolated):

```bash
cd frontend
npx playwright install chromium
cd ..
node scripts/ui-smoke.cjs
```

If Chrome is already installed on macOS, use `BROWSER_EXECUTABLE='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' node scripts/ui-smoke.cjs`. The script checks issuance, detail, confirmed revocation, CSV download, identity switching with a delayed response, empty search, mobile width, and browser exceptions. It writes screenshots under artifacts/. Set UI_TEST_PORT if 8011 is occupied.

The expanded control suite is `node scripts/ui-controls.cjs` (default port 8021, same BROWSER_EXECUTABLE override). It tests all sort columns, search/clear, cancellation, pagination/page size, actor/list/detail/course/export retries, lost-response issuance replay, and delayed revocation errors.

## A1-A7 reproduction

Use a fresh database for repeatable manual demonstrations: `DB_PATH=data/manual-check.sqlite3 PORT=8001 bash scripts/start.sh`. Pick a new filename for a fresh dataset; startup never silently resets existing data.

| Scenario | Reproduction and expected result |
| --- | --- |
| A1: Tenant isolation | Select Bob: only West certificates appear. With Bob's bearer token, GET `/api/certificates/1`, POST `/api/certificates/1/revoke`, and issuing course 1 return 404. Export returns only West rows. `?tenant_id=1` returns 422. Automated test asserts no unauthorized writes. |
| A2: Retry safety | As Alice POST `/api/certificate-issuances` with JSON `{"course_id":1}` and `Idempotency-Key: demo-operation`. Repeat the same request sequentially/concurrently: all successful responses contain the original operation and outcomes. Exactly one new certificate and issuance event. Real-socket and in-process concurrent checks are in the suite. |
| A3: Key misuse | Reuse demo-operation with `{"course_id":3}`: 409; original result remains intact. Invalid input returns 422 and foreign courses return 404 before key lookup. |
| A4: Learner outcomes | On fresh East Safety 101 issuance: Alex issued, Casey skipped/INCOMPLETE, Jordan skipped/ALREADY_CERTIFIED. UI shows every learner result. |
| A5: Local dates | View certificate 1 as Alice: 2026-01-11 00:30. View certificate 2 as Bob: 2026-01-10 21:30. Both originate from 2026-01-10T13:30:00Z. CSV uses local dates. Sorting by issue date uses calendar date and ID ties, proven with IDs 3 and 4; a winter test checks Sydney's changed offset. |
| A6: Export growth | Generate performance data using the command below, start that database, search Export Fixture, sort Learner ascending and export twice. Each export has exactly 100,000 rows in stable order. During export request the certificate list. The automated test measures full body downloads, compares expected serial ordering, tests selective/no-search export, and overlaps another request. |
| A7: Revocation audit | Revoke an active certificate, then repeat the POST. Status remains REVOKED with the original revoked_at and one revocation event. The suite also sends concurrent repeats. |

Example request (after startup):

```bash
curl -sS http://127.0.0.1:8000/api/certificate-issuances \
  -H 'Authorization: Bearer east-demo-token' \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: demo-operation' \
  -d '{"course_id":1}'
```

Use `/docs` for the generated OpenAPI interface. Exact endpoints, payloads, error envelopes, and query semantics are in [docs/spec.md](docs/spec.md).

## 100,000-row dataset

```bash
.venv/bin/python -m backend.seed_large --db data/performance.sqlite3
DB_PATH=data/performance.sqlite3 PORT=8001 bash scripts/start.sh
```

This creates a separate database with demo data plus exactly 100,000 East certificates in Export Performance (course 1000). Repeating generation recognizes the existing fixture. The generator refuses the default demo database. The search Export Fixture matches precisely the generated rows; an unfiltered East export includes the three initial East certificates too.

## Behavior and tradeoffs

- Revocation retains the certificate; no reissuance is supported. Revoked certificates still count as already certified.
- A single SQLite writer serializes short write transactions. Lock exhaustion returns 503 with retry guidance. Retain the same key after an uncertain network outcome.
- Idempotency results are durable and historical. Replaying a completed issuance after revocation returns the original operation; refresh certificate details for current status.
- CSV streams one tenant-scoped snapshot with a fixed ID tie-breaker. Database reads are batched; the browser receives the download as a Blob. All matching active and revoked records are included. Formula-like CSV cells receive an apostrophe prefix for spreadsheet safety; source data is unchanged (exact rules in the spec).
- Tenant time zones are fixed. Local dates are persisted at issuance and used consistently by list and export.
- Only explicit learner-local issuance rejection is recoverable within a batch; audit/database failures roll back the entire operation.
- Ant Design supplies UI controls. Original business rules implement the assessment; no LMS or full-stack application was copied.

## Evidence and limitations

See [docs/verification.md](docs/verification.md), [docs/code-review.md](docs/code-review.md), and [ai/decision-log.md](ai/decision-log.md) for actual results and review dispositions. Native AI interaction snapshots, index, and export manifest are included under ai/. They cover only the mianshi-Ocean workspace. Capture cutoffs, privacy redactions, and completeness limits are explicit in [ai/completeness.md](ai/completeness.md).

This is a local assessment app, not a production authentication/deployment solution. Windows startup is not verified. The frontend build has a large-bundle warning and ignores upstream Ant Design `use client` directives in this client-only application. The pytest run reports an upstream Starlette/AnyIO deprecation warning. These warnings do not represent passing checks being skipped. See verification for any remaining unverified scenarios.

`written-answers.md` is candidate-owned and was not drafted or edited by the implementation assistant. A Git whitespace check inadvertently echoed one line; it was not assessed or used for answer assistance. Subsequent content checks exclude the file. The completed file is included unchanged following the candidate's explicit publication request. Its presence alone is not a claim about completeness or independent authorship. The candidate must make that declaration and submit the repository URL and final commit SHA to the assessment recipient.
