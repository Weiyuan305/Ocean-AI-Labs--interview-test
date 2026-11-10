# Independent Code Review

Baseline: 2972cbd. Reviewed implementation: 6f418c5 and 6c98990. Scope: backend, English frontend, startup and tests. Superpowers requested fresh-context review; Matt Pocock's two-axis review kept standards and specification findings separate.

## Standards axis

Reviewer session: 01a1c63b-74ee-7b40-8661-7b62ac296117.

No important actionable standards findings. Tenant and transaction behavior is concentrated in small module interfaces; list/export share query construction. Minor deferred finding: actor/course SQL remains directly in app.py rather than the query module. It is localized; extracting it under the time box does not improve the demonstrated behavior.

## Specification axis

Reviewer session: 01a1c63b-51df-79c0-a350-0d05b7d6569c.

No confirmed P0/P1 tenancy, idempotency, or transaction defect. No unrequested product scope.

| Finding | Resolution / evidence |
| --- | --- |
| Catch-all 500 error response bypassed no-store middleware | Added a failing assertion to the audit-rollback test, observed missing header, then set the header directly in the exception handler. The regression passes. |
| Detail did not show revoked_at | Added Revoked at (UTC) to the drawer for revoked certificates. Browser smoke checks that label after confirmed revocation. |
| Late revoke response could temporarily replace another selected certificate's detail | Removed direct application of the returned detail. Refresh now reloads the currently selected ID through its cancellable effect. |
| Disconnect cleanup not verified | Real HTTP performance test terminates a stream early and confirms subsequent requests succeed. This is a functional cleanup check, not a file-descriptor leak soak test. |
| Stale actor response not verified | Browser smoke holds a real East response, switches to Bob, releases it, and checks West remains visible without East rows/results. |

The first browser runs exposed test-locator mistakes: both drawer and confirmation modal had dialog roles, and the search field's native role was searchbox rather than textbox. Locators were corrected against the rendered DOM; application behavior was not weakened to satisfy the test.

## Remaining verification limits

The same-actor drawer race now has a passing dedicated delayed-failure browser regression. Long-duration connection-leak testing and Windows startup are not performed. See verification.md for the final measured run and warnings.

## Expanded review after the initial business-code push

Baseline: 332982c. The user requested business code be pushed before continuing review, with unfinished candidate answers excluded. That baseline was pushed to remote main; subsequent fixes retain that clean ancestry. A private local backup branch and raw AI snapshots are not published because they contain candidate-owned answer material.

### Standards axis

The original standards review identified no important violations. The independent follow-up standards review found zero actionable regressions: validation and HTTP errors remain centralized, CSV escaping has a focused helper, and response ownership is explicit. The localized HTTP lookup tradeoff remains documented.

### Specification axis

| Finding | Regression and disposition |
| --- | --- |
| Default issue-date descending sort could never cycle to ascending | Reproduced in browser; explicit two-direction cycle now passes for initial click and all five headers. |
| Export failure Retry refreshed the list instead of downloading | Reproduced in browser; independent export error state and Retry export now produce a download. |
| Late failed revoke could show an error in another selected drawer | Reproduced by holding a failed revoke, closing its drawer and opening another; selection-generation checks now discard obsolete error/cleanup. |

Follow-up independent inspection found no concrete regression in these fixes.

### Security and performance review

| Finding | Regression and disposition |
| --- | --- |
| Demo actor discovery returned credentials for additional database actors | New test inserted a third actor and reproduced the leak; explicit matching of the two public demo identities now excludes it. |
| Oversized page/course/detail/revoke IDs caused SQLite overflow and HTTP 500 | Four failing HTTP cases now return 422 through positive signed-64 ID bounds and an offset-safe page limit. |
| Unknown framework routes did not use the error envelope | Failing 404 regression now passes; HTTP exceptions use the common envelope. |
| Imported formula-like names could execute when opened as spreadsheet cells | Export regression initially failed; dangerous prefixes now receive a leading apostrophe. The exact CSV transformation is recorded as a security amendment in spec section 6. Database values are unchanged. |

Seven new backend cases failed before implementation and passed afterward. Follow-up independent checks confirmed maximum-boundary behavior and the normal CSV route; no blocking regression was found. No concrete SQL injection or tenant escape was identified. Demo authentication remains intentionally public. The full 100,000-row real HTTP export test passed after CSV escaping changed; see verification.md for actual measurements. This review is not a claim of exhaustive security proof or sustained-load testing.
