# RP Sign-In Migration Validation Package

## Purpose
This package is provided by the GC Sign-In migration team to RP partners for UAT validation.

It contains the minimum scenario set partners should run to confirm the migration solution works for real users.

## Audience
This package is intended for RP partner UAT/QA teams to execute and report results for migration sign-off.

The focus is to prove:
1. Users can sign in/register successfully.
2. Existing users keep access to the same RP account.
3. Migration does not create duplicate accounts or lock users out.
4. Post-migration sign-in is stable.

## Scope
### Required Scenarios
Run all five required scenarios.

## Environment and Data Setup
Before testing, confirm:
1. Test environment URL(s) and callback config are correct.
2. You have test users for:
   - Brand-new user (no RP account, no GCS account)
   - Existing legacy RP user (not yet migrated)
   - Previously migrated user
3. Existing legacy test user has valid credentials for first-time migration.
4. You can capture evidence (screenshots/log references/session IDs).

## Scenario Matrix
| ID | Scenario | Type |
|---|---|---|
| R1 | New user registers and authenticates | Required |
| R2 | Existing RP user completes first-time migration | Required |
| R3 | Previously migrated user signs in again | Required |
| R4 | Previously migrated user selects Register by mistake | Required |
| R5 | Migration interrupted and resumed | Required |

## Detailed Scenarios

### R1: New User Registers and Authenticates
**Objective:** Confirm new users can onboard through GCS and access the RP.

**Preconditions:**
1. Test user has no RP account.
2. Test user has no GCS account.

**Steps:**
1. Go to RP and select `Register`.
2. Complete GCS account creation and authentication.
3. Return to RP and complete onboarding.
4. Sign out.
5. Sign in again using normal `Sign in` path.

**Expected Results:**
1. User reaches authenticated RP session after registration.
2. One RP account is created and linked correctly.
3. Subsequent sign-in works without migration prompts.

**Evidence to Capture:**
1. Final authenticated RP landing page.
2. Confirmation of account creation/linking (UI or logs).

---

### R2: Existing RP User Completes First-Time Migration
**Objective:** Confirm existing legacy users can migrate and keep their original RP account.

**Preconditions:**
1. User has existing RP account with legacy credential.
2. User does not yet have GCS account.

**Steps:**
1. Go to RP and select `Sign in`.
2. When prompted, create/sign in with GCS.
3. Complete legacy credential step to verify existing account ownership.
4. Finish migration and return to RP.
5. Sign out and sign in again.

**Expected Results:**
1. User lands in the same RP account as before migration.
2. No duplicate RP account is created.
3. Next sign-in succeeds through GCS without repeating migration.

**Evidence to Capture:**
1. Account identifier before and after migration.
2. Post-migration successful sign-in evidence.

---

### R3: Previously Migrated User Signs In Again
**Objective:** Confirm migrated users have a clean repeat sign-in experience.

**Preconditions:**
1. Test user is already migrated.

**Steps:**
1. Start a fresh session (sign out/clear session).
2. Select `Sign in`.
3. Authenticate via GCS.

**Expected Results:**
1. User is granted RP access successfully.
2. No migration or legacy credential screens appear.

**Evidence to Capture:**
1. Successful RP landing page.
2. No migration prompt shown during flow.

---

### R4: Migrated User Clicks Register by Mistake
**Objective:** Confirm accidental path selection does not create duplicates or break access.

**Preconditions:**
1. Test user is already migrated.

**Steps:**
1. On RP, select `Register` instead of `Sign in`.
2. Continue the presented flow.
3. Return to sign-in if prompted.

**Expected Results:**
1. User can recover to valid sign-in path and access RP.
2. No duplicate RP account is created.
3. Messaging is clear enough for user self-recovery.

**Evidence to Capture:**
1. UI message/redirect behavior.
2. Account record check confirming no duplicate.

---

### R5: Migration Interrupted and Resumed
**Objective:** Confirm interruption does not leave users in a broken state.

**Preconditions:**
1. User has existing RP account and has not completed migration.

**Steps:**
1. Start migration flow.
2. Close browser mid-flow (any point before final completion).
3. Reopen browser and return to RP sign-in.
4. Restart/resume flow and complete migration.

**Expected Results:**
1. User is not locked out.
2. Flow can be resumed or restarted successfully.
3. Migration completes with correct RP account linkage.
4. No duplicate accounts are created.

**Evidence to Capture:**
1. Point of interruption and restart attempt.
2. Successful completion after restart.

---

## Out of Scope for Partner Sign-Off
The following are intentionally excluded from partner UAT:
1. Cross-RP same-session behavior (single-RP partner model).
2. Legacy credential recovery behavior managed by external credential providers.

## Pass/Fail Criteria
Mark partner validation as **PASS** only if all required scenarios pass:
1. No lockout in any required scenario.
2. Existing users keep access to the same RP account.
3. No duplicate RP account creation is observed.
4. Post-migration sign-in is consistent and repeatable.
5. Interruption and resume handling are successful.

## Suggested Execution Template
Use one row per scenario execution.

| Date | Environment | Scenario ID | Tester | Result (Pass/Fail) | Defect ID | Evidence Link |
|---|---|---|---|---|---|---|
| YYYY-MM-DD | UAT/STAGE | R1 | Name | Pass | N/A | Link |
