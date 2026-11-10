# Design Review Record

## Scope and method

Reviewed the assessment against [technical-design.md](technical-design.md), using Superpowers brainstorming/builder-check and verification-before-completion, plus Matt Pocock codebase-design, domain-modeling, and writing-for-agents. Grilling guidance was consulted to identify consequential questions; settled scope and routine implementation choices were not reopened.

The candidate confirmed formal timing: 2026-11-10 23:45 through 2026-11-11 00:45 Asia/Shanghai. Reserve the final 15 minutes for independent answers and packaging.

Independent reviewer: Codex agent `design_review`, session `01a1c62b-c1f4-7970-a3ab-17ae4c6ae0f5`. The review reported no architecture-level blocker and design coverage for A1-A7. This is document review, not runtime verification or candidate approval.

## Findings and dispositions

| ID | Finding | Disposition |
| --- | --- | --- |
| R1 | Learner-local failure classification was vague; broad exception handling could hide audit or database corruption. | Allow only explicit IssuanceRejected at the issuance seam; savepoint rollback and failed result. Audit/database/unexpected errors abort the entire operation. Test-only injection verifies the recoverable path. |
| R2 | Key-conflict and ownership rules did not spell out error precedence. | For authenticated requests: malformed input 422, unknown/foreign course 404, changed valid authorized payload with reused key 409. |
| R3 | A streaming iterator can run on a different thread from its synchronous handler. | Export owns a check_same_thread=False connection, uses it sequentially, establishes its read snapshot before headers, and closes it on completion/disconnect. |

## Decisions confirmed by the design

Use Ant Design controls with original FastAPI/SQLite business logic. Keep tenant enforcement and transaction knowledge in deep modules. Do not support reissuance, tenant time-zone changes, production authentication, or a generic background job system. Export all matching records, including revoked records, with a deterministic ID tie-breaker.

## Outstanding execution checks

- A1-A7, UI behavior, dependency compatibility, and clean startup have not been implemented or run.
- Native root and reviewer JSONL logs are available. Full export, narrow redaction, session-index linkage, final-tail capture, and completeness declaration remain pending.
- The 100,000-row export must be timed with a full response-body download, repeated, and overlapped with a list request.
- Candidate technical-design/spec review precedes application implementation. This record does not certify that every possible issue has been eliminated.
