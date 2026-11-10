# Certificate Administration

This context manages training completion certificates for independent customer organizations.

## Language

**Tenant**: A customer organization whose administrators manage only its learners, courses, and certificates.
_Avoid_: Account, workspace

**Actor**: The administrator performing an operation on behalf of one tenant.
_Avoid_: Learner, operator account

**Learner**: A person enrolled in training within a tenant. A name does not establish identity.

**Enrollment**: A learner's participation in a course, including whether that course has been completed.

**Eligible learner**: An enrolled learner who has completed the course and has never received a certificate for that course in that tenant.

**Certificate**: A uniquely numbered record acknowledging a learner's completion of a course. Its status is active or revoked.

**Issuance**: The creation of a certificate for an eligible learner.

**Revocation**: The irreversible change of a certificate from active to revoked within this assessment's scope. The certificate remains recorded.
_Avoid_: Deletion, cancellation

**Bulk issuance operation**: One request to evaluate every enrollment in a course and report an outcome for each learner.

**Learner outcome**: The result of evaluating one learner during bulk issuance: issued, skipped with a reason, or failed with a reason.

**Audit event**: An attributable record of an actual issuance or revocation.

**Tenant-local issue date**: The calendar date of issuance in the tenant's configured time zone.
