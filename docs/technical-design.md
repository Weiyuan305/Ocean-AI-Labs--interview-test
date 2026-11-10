# Certificate Admin Console: Technical Design

Status: independent builder review completed; material clarifications incorporated. Ready for candidate review. No application code exists yet. See [review record](design-review.md) and [detailed specification](spec.md).

## 1. Authority, scope, and time box

Source: `Ocean AI Labs Beijing - Technical Interview Assessment - 2026110302.pdf`, internal version 20261102, Sections 1-5 and 7-9. The assessment takes precedence over this design. Domain terms are defined in [GLOSSARY.md](../GLOSSARY.md).

The candidate confirmed that the formal assessment began at **2026-11-10 23:45 Asia/Shanghai**. The deadline is **2026-11-11 00:45 Asia/Shanghai**. Target implementation freeze is **00:30**, reserving 15 minutes for the candidate's independent written answers and packaging. Planning, research, documentation, and AI activity remain part of the evidence; elapsed time is never reset by creating these documents.

Deliver a locally runnable multi-tenant certificate console: list/search/sort/page, course-wide issuance, certificate detail/revocation, and CSV export. Preserve complete AI evidence and git history. Section 6 is candidate-owned; this workflow does not produce, translate, or edit its answers.

The project starts in a folder containing only the assessment PDF. Initialize an original repository rather than importing an existing product. Use declared open-source dependencies. No production login, cloud deployment, email, certificate PDF rendering, course editor, learner editor, or cache is required.

## 2. Approaches and selection

| Approach | Benefit | Cost | Decision |
| --- | --- | --- | --- |
| React + Ant Design + FastAPI + SQLite | Small application, reusable controls, explicit transaction behavior, no database server | Custom business rules and HTTP contracts | Selected proposal |
| React-admin or Refine + custom backend | More CRUD infrastructure | Additional provider conventions for a single custom workflow; export still needs a backend | Not selected |
| Adapt Frappe LMS, Open edX, or a full-stack template | Existing product/framework structure | Excess functionality, dependency setup, different domain rules, template provenance ambiguity | Reference only |

Use TypeScript, Vite, React, and Ant Design for the UI; Python, FastAPI, Pydantic, sqlite3, zoneinfo/tzdata, and csv for the backend; pytest and HTTP-level checks for verification. Pin compatible dependency versions during implementation and record resolved versions. Build the frontend and serve it from FastAPI on one origin. Runtime prerequisites are documented Python and Node versions; the startup command installs project dependencies, not operating-system runtimes.

References: [Ant Design Table](https://ant.design/components/table/), [FastAPI template](https://github.com/fastapi/full-stack-fastapi-template), [Frappe certificate rules](https://raw.githubusercontent.com/frappe/lms/develop/lms/lms/doctype/lms_certificate/lms_certificate.py), [Open edX certificate lifecycle](https://docs.openedx.org/projects/edx-platform/en/latest/references/docstrings/lms/lms.djangoapps.certificates.html). These references were inspected, not executed or verified against A1-A7. Retain required dependency notices; do not copy AGPL application code into this project.

## 3. Domain decisions and invariants

- Names and course titles can repeat across tenants. IDs identify records.
- Each administrator belongs to exactly one tenant. Resolve the tenant from a fixed demonstration bearer token, never a request-supplied tenant identifier.
- A tenant/course/learner has at most one certificate, including revoked certificates. Revocation does not restore eligibility. Reissuance is outside scope.
- A completed enrollment with no certificate is eligible. An incomplete enrollment is skipped; an existing certificate is skipped. Incomplete takes precedence if both conditions apply.
- Issuance creates exactly one issuance audit event. An active-to-revoked transition creates exactly one revocation audit event. Business state and audit write commit together.
- Bulk issuance returns an outcome for every enrollment, ordered by learner ID. Zero enrollments produces a successful empty operation.
- An idempotency key is scoped to tenant and actor. Repeating a valid request returns the persisted original operation result, even if certificate states later change. A different valid payload with that key returns 409 without replacing the original result.
- Tenant time zones are fixed for this assessment. Persist UTC issuance time and the derived local calendar date; format local date/time from the same zone conversion. Never use the browser's time zone or a fixed UTC offset.

## 4. Modules and interfaces

Follow Matt Pocock's deep-module principle: keep transaction and tenancy knowledge behind small interfaces, with tests using those same interfaces. Do not introduce generic repositories or hypothetical database adapters.

| Module | Interface responsibility | Hidden implementation |
| --- | --- | --- |
| Actor context | Resolve a request credential to actor and tenant | Demo token mapping and rejection |
| Certificate operations | Issue a course; revoke a certificate | Eligibility, write locking, uniqueness, idempotency, savepoints, audit atomicity |
| Certificate queries | List, detail, and export using an actor and query | Tenant predicates, parameterized SQL, ordering, snapshot and connection lifetime |
| Database setup | Open configured connections and initialize data | Foreign keys, WAL, schema, indexes, idempotent seeds |
| Console | Present actor-scoped workflows and outcomes | Controlled inputs, pending states, cancellation and response ownership |

## 5. Persistence and integrity

Use tables for tenants, actors, courses, learners, enrollments, certificates, issuance_operations, and audit_events. Tenant-owned records carry tenant_id. Composite foreign keys ensure referenced courses/learners/certificates belong to that same tenant. Enable foreign keys on every connection.

Key constraints: unique actor email and token; unique enrollment `(tenant_id, course_id, learner_id)`; unique certificate on the same triple; globally unique certificate serial; unique operation `(tenant_id, actor_id, idempotency_key)`; unique audit `(tenant_id, certificate_id, event_type)`. Status and completion values use explicit checks.

Persist UTC timestamps in a single normalized representation. A certificate also has `issue_date_local` in YYYY-MM-DD form. Seed and bulk-data tools use the same conversion rule. Index tenant and supported sort keys; SQLite can sort other bounded result sets as needed. Performance is a measured acceptance condition, not an index-based claim.

## 6. Write transactions and retries

Use independent connections, WAL, a bounded busy timeout, and short synchronous write transactions. Blocking sqlite3 work executes outside the event loop.

Bulk issuance: validate identity and strict request syntax; verify course ownership; acquire `BEGIN IMMEDIATE`; recheck ownership and read the scoped idempotency record. A matching fingerprint returns its persisted result. A different fingerprint returns 409. Otherwise evaluate enrollments in stable order, insert eligible certificates and audit events, store the complete operation result, and commit before replying.

The fingerprint covers the normalized validated payload and operation version. It does not depend on JSON whitespace or property order. Unknown payload fields are rejected rather than ignored. Course ownership is checked before looking up prior operation results, so unauthorized targets never disclose historical outcomes.

Only an explicit `IssuanceRejected` exception from the learner issuance step is recoverable: roll back that learner's savepoint, return failed with reason `ISSUANCE_REJECTED`, and continue. Exercise it through a test-only injected failure; expose no failure-triggering HTTP option. Normal seed data does not artificially fail. Unexpected programming errors, database unavailability, audit write errors, or operation-result persistence errors roll back the entire transaction and return a non-success response. Never claim an issuance when its audit did not commit.

There is no durable pending operation and no background queue: the complete operation and all committed learner outcomes become visible atomically. A crash before commit leaves no operation; a lost response after commit is replayable. Concurrent same-key callers serialize, then read the same result. Lock timeout is a transient 503 with retry guidance, never a false 409 or fabricated success. Under the specified small-course concurrent acceptance fixture, all calls must complete with the same successful result; test this explicitly.

Revocation: acquire a write transaction, read the certificate through the tenant predicate, and change active to revoked while inserting its audit. An already-revoked certificate returns its current state without another event. Cross-tenant and unknown IDs both return 404.

## 7. Query, date, and export consistency

List and export consume the same validated query description. Search is a literal case-insensitive substring of learner name or serial number; normalize consistently. Define a whitelist of sort fields and always append certificate ID ascending as the deterministic tie-breaker. Sorting by issue date means `issue_date_local`, not UTC time or the formatted timestamp. Export ignores list pagination.

CSV uses exactly the four assessment columns. Use a CSV library for commas, quotes, Unicode, and line breaks. Export active and revoked records because the assessment requests certificate data without a status exclusion.

Use one dedicated read connection and read transaction for the entire streamed export, fetch rows in bounded batches, and close the cursor/transaction/connection on success or disconnect. Establish the read snapshot before sending response headers. A synchronous handler and its streaming iterator may execute on different pool threads: open this request-owned connection with `check_same_thread=False`, use it sequentially, and never share it with other requests. Concurrent writes do not change the in-flight snapshot. Keep the export off the event loop and leave capacity for list requests. Do not hold an application-wide mutex around export.

A6 measures the complete response body, twice, with 100,000 matching rows and repeated sort keys. Verify exact membership, count, order, and equal-key ordering, plus a list request while the export remains active. Additional selective search checks catch filters that accidentally export everything. Identical repeat output is expected for an unchanged dataset, not across intervening writes.

## 8. User experience

One page contains actor selection, search, course selection, bulk issue and export actions, the certificate table, and per-learner results. A drawer shows certificate details, audit history, and confirmed revocation.

On actor switch, immediately clear prior records, course selection, details, operation results, and pending action context. Abort obsolete reads or discard responses by actor/request generation. A previous actor's late response must never repopulate the page. Server authorization remains authoritative.

Disable submission while pending. Retain the same key and payload for uncertain network retries; use a new key only for an explicitly new operation. A completed operation may include failed learner outcomes; retrying that same key replays them. A deliberate new operation re-evaluates eligibility with a new key. Display revoked state only after server confirmation. Provide loading, empty, error, and retry states.

## 9. Verification and delivery

Test A1-A7 through real HTTP requests and a file-backed SQLite database. Use independent clients/connections and concurrent request starts for A2/A7; serial mocks are insufficient. Check database certificate and audit counts as well as responses. UI smoke checks cover both actors and the complete issue/detail/revoke/export path.

Maintain isolated demo and performance databases. The 100,000-row command targets a separate path and is safely repeatable. Startup seeds missing demo data without deleting existing changes; reset is explicit. Re-running startup must preserve revoked state.

Required delivery: source and full git history, final SHA/repository URL, one-command startup, reproducible A1-A7 instructions, bulk-data command, measured verification results, known limitations, original AI session exports, session index, decision log, tool action evidence, and completeness declaration. The candidate supplies independent written answers.

AI export is a delivery risk: the available chat-reading tool exposes summaries/truncated outputs, so it is not sufficient evidence by itself. Native root-session JSONL was located and inspected at 23:55 Asia/Shanghai: session ID `01a1c623-2c2e-7b80-abe6-be94617590ba`, containing messages, session metadata, and tool calls/outputs. The builder-review session log was also located. Availability is verified; completeness, redaction, final export, and index linkage are not yet verified. Export these native chronological logs, including subordinate review sessions; if any tool lacks complete export, provide its complete chronological transcript and disclose the limitation. Never manufacture logs, verification output, model IDs, times, or commits. Capture only this assessment's sessions and narrowly redact secrets. Refresh evidence after the final AI interaction.

## 10. Risk review and decision status

| Risk / question | Resolution or required check |
| --- | --- |
| What does SSD mean? | Interpreted as Spec-Driven Development (SDD); documents remain in English. |
| Is the assessment clock running? | Confirmed by candidate; 23:45 start, 00:45 deadline, Asia/Shanghai. |
| Can an existing LMS be submitted? | Use original application code and declared libraries; no wholesale product import. |
| Can revoked certificates be reissued? | No; explicitly documented scope decision. |
| Can frontend filtering enforce tenants? | No; every backend operation enforces actor ownership. |
| Is existence-check-before-insert sufficient? | No; transactional serialization and database uniqueness are required. |
| Does export include only the visible page? | No; all matching tenant records, stable order, bounded streaming. |
| Can UI components prove export performance? | No; measure A6 using complete real response bodies. |
| Can every learner error be swallowed? | No; only classified learner failures continue; integrity/system errors abort. |
| Are AI logs exportable and complete? | Native JSONL availability verified; completeness, redaction, and final packaging remain delivery checks. |
| Is the implementation correct or fast enough? | Unverified until implemented and tested; design review cannot certify runtime behavior. |

Error precedence for an authenticated bulk request is strict syntax validation (422), then course ownership/existence (404), then scoped key/payload conflict (409). A3 uses two valid courses belonging to Alice. Invalid or unauthorized targets do not reveal prior operations.

Next sequence: completed independent builder review -> detailed executable specification -> candidate review before application implementation. The detailed spec owns exact HTTP contracts and test fixtures; this design owns architecture and rationale.
