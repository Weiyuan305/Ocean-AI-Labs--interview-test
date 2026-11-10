# Certificate Admin Console: Executable Specification

Status: ready for candidate review; implementation and runtime acceptance are pending.

## 1. Authority and SDD workflow

The assessment PDF is authoritative. [Technical design](technical-design.md) owns architecture and rationale; [glossary](../GLOSSARY.md) owns domain terms; this specification owns observable contracts and acceptance checks. [Design review](design-review.md) records resolved findings. All project documentation is English.

SDD means: agree contracts -> implement one vertical workflow -> verify it against this spec -> record evidence -> continue. Change this spec and its affected acceptance checks together when a requirement changes. Do not weaken A1-A7 to make an implementation pass.

Formal window: 2026-11-10 23:45 to 2026-11-11 00:45 Asia/Shanghai. Target engineering freeze: 00:30. This document does not restart the timer. Section 6 answers are candidate-owned and excluded from AI authoring/review.

## 2. Application and planned file responsibilities

One same-origin local application serves React assets and `/api` routes. Use React, TypeScript, Vite, Ant Design, FastAPI, SQLite, zoneinfo/tzdata, and Python csv. Lock tested dependency versions. No external database service or cloud dependency is required.

Planned files below do not yet exist:

| File | Responsibility |
| --- | --- |
| `backend/app.py` | HTTP routes, validation, error conversion, static frontend serving |
| `backend/database.py` | Schema, configured connections, repeatable demo initialization |
| `backend/certificates.py` | Actor-scoped reads, issuance/revocation transactions, export query |
| `backend/seed_large.py` | Repeatable isolated performance dataset |
| `backend/tests/test_acceptance.py` | A1-A7 correctness and concurrency checks |
| `frontend/src/App.tsx` | Single-page workflow, detail drawer, operation outcomes |
| `frontend/src/api.ts` | Typed requests, actor headers, error handling and stale-response control |
| `scripts/start.sh` | Install declared dependencies, initialize selected database, build UI, start server |
| `scripts/verify.sh` | Reproducible correctness and performance verification |
| `README.md` | Actual startup prerequisites/commands, actors, A1-A7 reproduction, limitations |

Use one certificate module initially; split only when doing so concentrates behavior rather than creating pass-through layers. Database path and clock are injectable for tests; production business rules remain identical.

## 3. Data contract

Use integer record IDs, normalized UTC timestamps, and explicit tenant relationships. Names are not keys.

| Record | Required information and constraints |
| --- | --- |
| Tenant | ID, name, IANA time zone |
| Actor | ID, tenant ID, unique email, unique demonstration token |
| Course | ID, tenant ID, title; unique `(tenant_id, id)` for composite references |
| Learner | ID, tenant ID, name, normalized search name; unique `(tenant_id, id)` |
| Enrollment | Tenant/course/learner, completed boolean; unique triple; composite course/learner foreign keys |
| Certificate | ID, tenant/course/learner, unique serial number, issued_at UTC, issue_date_local, status, revoked_at; unique tenant/course/learner triple; composite references |
| Issuance operation | ID, tenant/actor/key, request fingerprint, committed JSON result, created_at; unique tenant/actor/key |
| Audit event | ID, tenant/certificate/actor, event type, created_at; unique tenant/certificate/event type; composite references |

Enable foreign keys on every connection. Use status values `ACTIVE` and `REVOKED`, event types `ISSUED` and `REVOKED`. ACTIVE requires revoked_at null; REVOKED requires a timestamp. Certificates remain unique after revocation. Index tenant/date/ID and commonly used ordering columns. Use parameters for values and a whitelist for SQL identifiers.

## 4. HTTP conventions

All business routes require `Authorization: Bearer <demo-token>`. Missing/unknown credentials return 401. Resolve tenant exclusively from the actor. `GET /api/demo-actors` is an intentional local-demo exception returning only the two declared demonstration identities and their public demo tokens; it exposes no learner/certificate data. Document that these are demonstration credentials.

Errors use `error.code` and `error.message`; validation errors may additionally include field details. Normalize framework validation to this envelope. Do not expose SQL, stack traces, or whether foreign-tenant records exist. Set business responses to `Cache-Control: no-store`.

For an authenticated request: malformed data is 422; unknown/foreign resource is 404; a reused key with a different valid authorized payload is 409; transient database lock exhaustion is 503 with Retry-After; unexpected internal failure is 500. An empty search result is 200, not 404. Reject unsupported query fields, including client-supplied tenant_id, with 422.

### Query parameters shared by list and export

- `q`: optional, default empty, maximum 200 characters; trim outer whitespace, Unicode casefold, literal substring match on normalized learner name OR serial. Escape SQL LIKE wildcard characters so `%` and `_` are literal input.
- `sort`: `learner_name`, `course_title`, `serial_number`, `issue_date`, or `status`; default `issue_date`.
- `order`: `asc` or `desc`; default `desc`.
- Always append certificate ID ascending, independent of primary sort direction. Text sorting uses SQLite BINARY collation; search normalization does not change displayed text.
- List only: `page` positive integer, default 1; `page_size` 1-100, default 20. Export does not accept pagination parameters.

### Endpoints

| Method and route | Request | Successful response |
| --- | --- | --- |
| GET `/api/demo-actors` | None | `items`: actor ID, email, tenant name, time zone, demo token |
| GET `/api/courses` | Actor | `items`: ID, title, completed_count, incomplete_count; current tenant only |
| GET `/api/certificates` | Actor + list parameters | `items`, `total`, `page`, `page_size` |
| GET `/api/certificates/{id}` | Actor | Certificate plus `audit_events` ordered by event ID |
| POST `/api/certificate-issuances` | Actor, Idempotency-Key, strict JSON course_id | Persisted operation result; 200 for initial completion and replay |
| POST `/api/certificates/{id}/revoke` | Actor, no body | Current certificate; 200 for first and repeated revocation |
| GET `/api/certificates/export.csv` | Actor + shared query parameters | Streaming UTF-8 CSV attachment |

Register the export route before the ID route or use typed route matching so export.csv is never parsed as a certificate ID.

A certificate response contains `id`, `serial_number`, `course_id`, `course_title`, `learner_id`, `learner_name`, `issued_at`, `issue_date_local`, `issued_at_local`, `status`, and `revoked_at`. `issued_at`/`revoked_at` are UTC ISO timestamps; `issued_at_local` includes its actual offset. UI detail displays YYYY-MM-DD HH:mm and the tenant zone.

An audit event response contains `id`, `event_type`, `actor_email`, and `created_at`. All joins retain tenant predicates.

## 5. Issuance and revocation behavior

`Idempotency-Key` is required, nonempty, at most 128 ASCII characters from letters, digits, dash, underscore, and dot. The UI generates a UUID. `course_id` is a strict positive integer; reject additional JSON properties. Fingerprint the normalized validated payload plus a fixed issuance version. The key is unique within tenant and actor and has no expiry in this assessment.

For valid input, check course ownership before key lookup. In a short `BEGIN IMMEDIATE` transaction, check the key again. Matching fingerprint returns the original committed result unchanged; differing fingerprint returns 409 without writes. Evaluate enrollments by learner ID. Incomplete -> skipped/INCOMPLETE; otherwise existing certificate of either status -> skipped/ALREADY_CERTIFIED; otherwise insert certificate and one audit event -> issued. Evaluate all enrollments, not just currently eligible ones, so skip reasons are visible.

Result fields: `operation_id`, `course_id`, `status` (COMPLETED), `summary` (`issued`, `skipped`, `failed` counts), and `outcomes`. Each outcome includes `learner_id`, `learner_name`, `outcome`, nullable `reason`, and nullable `certificate_id`. Existing-certificate skips include that certificate ID; incomplete/failed outcomes have null IDs. An empty course returns zero counts and an empty outcomes list.

Persist this complete result in the same transaction as certificates and audits. Respond only after commit. Do not regenerate results on retry. Same-key concurrent calls must serialize and receive the same operation and outcome data under the acceptance load. Different-key concurrent calls also cannot produce duplicate certificates or issuance events.

Use savepoints only to handle explicit `IssuanceRejected` from the issuance step: return failed/ISSUANCE_REJECTED after rolling back that learner's writes. Test this with an injected dependency; do not expose a production HTTP fault switch. Any unexpected database, audit, or result-persistence failure rolls back the whole operation. A pre-commit failure leaves no operation; a post-commit lost response is safely replayed. Bounded lock exhaustion returns 503, with the caller retaining its key for retry. A 503 is not counted as a successful A2 result.

Revocation runs in a write transaction. Unknown/foreign ID -> 404. ACTIVE -> REVOKED, set revoked_at, append one event, commit. REVOKED -> return current certificate without changing timestamps or adding an event. Concurrent revocations follow the same rule. Reissuance is not supported.

## 6. Export and dates

CSV header order: `learner_name,course_title,serial_number,issue_date_local`. Date values are YYYY-MM-DD. Include all matching ACTIVE and REVOKED certificates. Quote commas, quotes, and embedded newlines using the CSV library; preserve Unicode values. No frontend CSV construction or default admin-framework export is used.

List and export use one shared validated filter/order implementation. Date sort uses the local calendar date; certificate ID ascending breaks date ties, not the time within that date. For `2026-01-10T13:30:00Z`, East displays `2026-01-11 00:30` and exports `2026-01-11`; West displays `2026-01-10 21:30` and exports `2026-01-10`. Derive local fields using Australia/Sydney and Australia/Perth, not constant offsets.

Export opens a dedicated request-owned SQLite connection with foreign keys enabled and check_same_thread=False. Begin a read transaction, execute the tenant-scoped query and fetch the first batch before sending headers. Iterate sequentially in bounded batches (1,000 rows), stream encoded CSV chunks, and close resources in a finally path plus idempotent response cleanup on disconnect. No request shares this connection. Synchronous database/stream work runs outside the event loop. A single snapshot supplies the export; list uses another connection and remains responsive. A midstream fatal error terminates the response; it cannot be converted into a successful CSV or a new JSON status after headers.

## 7. UI acceptance

- Default to Alice; display actor email, tenant name, and zone. Fetch courses and certificates for that actor.
- Search, sortable headers, and server pagination use controlled state; changing search/sort resets page to 1. Show loading, empty, failure, and retry states.
- Course selection shows course completion counts. Bulk submission disables duplicate clicks and displays pending/completed/error state and every learner outcome/reason.
- Hold key and payload for an uncertain retry, including 503/network errors. An explicit new operation gets a new key. Replayed results may be historical after later revocation; refresh the certificate list independently.
- Detail shows required fields and audit events. Confirm before revocation; update status only after server success.
- Export passes the currently applied search and sort, omits pagination, sends actor credentials, and displays errors.
- Actor switching immediately clears records, course selection, detail, results, and request context. Abort obsolete reads or discard responses by request generation. Late results from a previous actor cannot update the screen. A write already received by the server may still commit for its original actor; switching UI identity does not retarget it.

## 8. Reproducible fixtures and verification

Demo: East/Australia/Sydney with alice@east.test; West/Australia/Perth with bob@west.test. Both have Safety 101 and Alex Lee. Each Safety 101 includes: Alex (completed, uncertified), Casey (incomplete), Jordan (completed, certified). Jordan's seeded certificate uses the A5 UTC timestamp and has one issuance audit event. East additionally has another valid course for A3. IDs/tokens are deterministic and listed in README. Add two date-sort fixtures on the same tenant-local date with IDs ordered opposite their issue times; this distinguishes calendar-date sorting from timestamp sorting.

Performance data lives in a separate explicitly selected SQLite file containing the small demo plus an additional East course with exactly 100,000 generated certificates. Give every generated learner a name containing `Export Fixture`, with repeated learner names and dates to exercise ties. Give each a distinct ID and serial, completed enrollment, and one issuance audit. Re-running the generator replaces only its dedicated fixture dataset transactionally or recognizes a complete existing dataset; it never appends duplicates or touches the demo database.

| Check | Procedure | Required observable result |
| --- | --- | --- |
| A1 | Bob lists/searches, requests East detail/revoke, issues East course, and exports; try tenant_id tampering | Only West data; foreign targets 404; unsupported tenant selector 422; zero East writes or audit changes |
| A2 | Alice issues Safety 101; repeat sequentially and start at least two same-key HTTP calls together against a fresh fixture | All successful responses share operation ID and identical outcomes; one certificate and issuance event for Alex; no duplicates |
| A3 | Alice reuses a completed key for the second valid East course | 409; original result unchanged; no second-course writes |
| A4 | Issue mixed Safety 101 | Alex issued, Casey skipped/INCOMPLETE, Jordan skipped/ALREADY_CERTIFIED; counts match outcomes |
| A5 | Read both Jordan certificates, sort local-date fixtures, export both tenants | Exact prescribed local dates/times; same-day ties follow IDs, including across different times; CSV agrees |
| A6 | Search Export Fixture, choose learner_name ascending, stream complete export twice; start a list request after first export starts and before it finishes | Each complete download <=60 s; exactly 100,000 East data rows; exact membership/order, stable ties; list succeeds during export |
| A7 | Revoke a fresh active East certificate, repeat, then exercise concurrent repeats | One status transition and one revocation event; preserved revoked_at |

For A6, measure full wall-clock body consumption, excluding fixture generation; report machine/runtime versions, row count and duration. Use a real HTTP server and independent connections. Coordinate overlap with a streaming reader barrier; if the export finishes too quickly, use a bounded client-side reading pause rather than a server production delay. Also export a selective substring and verify the exact subset, and run the no-search export to catch pagination truncation. Compare parsed rows and expected database ordering, not merely file size.

Additional checks: missing actor; malformed/unknown sort and invalid page; literal search wildcards and mixed case; CSV quotes/newlines/Unicode; empty course; revoked-certificate eligibility; restart preserving operations/revocations; lost-response replay; different-key concurrency; injected learner rejection with savepoint rollback; injected audit failure with whole-operation rollback; export disconnect cleanup; stale actor responses. Add a winter timestamp to exercise Sydney offset changes. Avoid tests that merely duplicate internal function structure.

## 9. Delivery and execution order

Implement in vertical steps: (1) database/actors/list and demo UI; (2) issuance/revocation with transactional acceptance checks; (3) export/date semantics and real A6; (4) UI completion, clean startup, evidence packaging. Run the relevant checks after each step and commit working milestones. If time falls short, preserve A1-A7 correctness and disclose unfinished scope; never report unrun tests as passing.

Planned startup contract: `bash scripts/start.sh` installs declared dependencies, initializes the selected database if necessary, builds frontend assets and starts the whole app. Use a documented DB_PATH override for the performance database. Document the actual data-generation and verification commands once implemented. Startup is non-destructive; reset is a separate explicit action.

Submission includes repository URL and final SHA; README with exact actor credentials, A1-A7 steps, generation command, measured results and limitations; original native AI exports in `ai/sessions/`; `ai/session-index.csv` with session_id, tool, model, started_at, ended_at, export_file, purpose, related_commits; `ai/decision-log.md`; tool action evidence; and completeness declaration. Keep AI instruction files in git. Index parent and reviewer sessions and use consistent timezone offsets. Capture the final conversation tail after work ends without making a recursive claim that an export already includes future activity.

Record at least an accepted suggestion, a corrected/rejected suggestion or honest verification if no meaningful error occurred, and a real scope/design tradeoff. Link each to actual session, evidence and commit. Candidate authors written-answers.md independently and confirms that fact personally. The final repository must preserve the independent answer file without AI editing. Submission sending is a separate user action unless explicitly requested.

Definition of done: candidate-approved document baseline; implemented workflows; actual passing A1-A7 evidence or explicit unfinished findings; successful clean startup and persistence check; reproducible performance fixture; real git history; complete reviewed AI evidence; candidate-owned written answers; final submission identifiers. Document review alone satisfies none of the runtime or evidence gates.
