# Decision Log

Root session: 01a1c623-2c2e-7b80-abe6-be94617590ba. The native session index and snapshots are published for this workspace only; see completeness.md for the cutoff and redaction scope.

| Decision | Type and rationale | Evidence | Commit |
| --- | --- | --- | --- |
| Use React/Ant Design with FastAPI/SQLite | Accepted AI proposal: reuse mature controls while keeping tenant/transaction rules explicit and avoiding database-service setup. | Approved technical design/spec, browser workflow and real SQLite HTTP tests. | 2972cbd, 6f418c5, 6c98990 |
| Reject wholesale LMS/full-stack template import | Scope/design tradeoff: Frappe/Open edX are broader than the one-hour certificate console and have different rules. Original app starts from the empty repository and uses declared dependencies. | Research conversation; technical-design.md approaches; no imported LMS product. | 2972cbd |
| Correct broad learner-error handling ambiguity | Design-review correction: only explicit learner rejection is recoverable; audit/database failures roll back the entire operation. | Review session 01a1c62b-c1f4-7970-a3ab-17ae4c6ae0f5; test_learner_rejection_and_restart_replay and test_audit_failure_rolls_back_operation. | 6f418c5 |
| Correct initial Vite patch choice | Dependency installation surfaced an advisory. Updated to compatible 6.4.6 rather than ignoring the warning or changing architecture. | npm audit native output and subsequent install reporting zero vulnerabilities. | 6f418c5 |
| Correct missing no-store on uncaught 500 responses | Implementation-review correction: middleware did not cover the outer error handler. A newly added assertion first failed, then passed after the header was added directly. | Spec reviewer 01a1c63b-51df-79c0-a350-0d05b7d6569c; audit rollback regression; code-review.md. | 332982c |
| Keep revocation permanent; omit reissuance | Scope tradeoff: preserve one certificate per tenant/course/learner and deterministic eligibility without inventing versioned certificates. | Spec and replay/revocation tests. | 2972cbd, 6f418c5 |

No AI mistake or test result was invented. Browser locator failures and dependency setup failures are preserved in the session evidence. Performance results are local observations, not predicted guarantees.

## Follow-up review decisions

- Corrected three browser-reproduced interaction bugs: initial date sort direction, export retry action, and late revoke errors in a different detail selection. Red/green evidence: artifacts/ui-controls-red.log and artifacts/ui-controls.log.
- Restricted public actor discovery to the two declared demo identities and bounded integer inputs; added the common framework error envelope. Seven failing security/boundary cases became passing regressions.
- Chose spreadsheet-safe CSV output for formula-like input text. This intentionally prefixes selected exported cells while preserving database values; spec section 6 records the contract change.
- Honored the candidate's instruction to keep unfinished answers local. Pushed the clean business baseline first and kept answer-containing local history and raw AI snapshots out of publication. Full evidence publication remains an explicit unfinished delivery gate.

## Evidence publication

The candidate authorized evidence publication and clarified that only mianshi-Ocean belongs to this assessment. Five workspace sessions are included. Other-workspace snapshots were removed before staging; unrelated excerpts in tool output were narrowly redacted with their reason recorded. Evidence packaging continued after 00:45; native timestamps preserve that timing.
