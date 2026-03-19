# Implementation Plan

---

## Bug 1: Email Domain Restriction on User Creation

- [x] 1. Write bug condition exploration test for email domain restriction
  - **Property 1: Bug Condition** - Non-axrail Email Accepted
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bug exists
  - **Scoped PBT Approach**: Scope the property to emails not ending with `@axrail.com` (e.g., `user@gmail.com`, `user@competitor.com`)
  - Bug Condition: `isBugCondition(email)` where `not email.lower().endswith("@axrail.com")`
  - Test that `create_user()` with a non-`@axrail.com` email raises a `ValueError` (expected behavior from design)
  - Run test on UNFIXED code - expect FAILURE (currently the system accepts any email domain)
  - Document counterexamples found (e.g., `create_user(email="user@gmail.com")` succeeds instead of raising ValueError)
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 1.2, 2.1_

- [x] 2. Write preservation property tests for email domain restriction (BEFORE implementing fix)
  - **Property 2: Preservation** - Valid axrail.com Email Creation Unchanged
  - **IMPORTANT**: Follow observation-first methodology
  - Observe: `create_user(email="valid@axrail.com", ...)` proceeds to uniqueness check and creation on unfixed code
  - Observe: `create_user(email="duplicate@axrail.com", ...)` raises "email already in use" error on unfixed code
  - Observe: admin creating superadmin/admin account raises permissions error on unfixed code
  - Write property-based tests: for all valid `@axrail.com` emails, existing behavior (uniqueness check, enum validation, permission checks) is preserved
  - Verify tests pass on UNFIXED code
  - _Requirements: 3.1, 3.2, 3.3_

- [x] 3. Fix email domain restriction on user creation

  - [x] 3.1 Add `ALLOWED_EMAIL_DOMAIN` constant and `_validate_email_domain(email)` function to `lambdas/users/CreateUser/handler.py`
    - Add `ALLOWED_EMAIL_DOMAIN = "@axrail.com"` constant
    - Add `_validate_email_domain(email)` that checks `email.lower().endswith(ALLOWED_EMAIL_DOMAIN)` and raises `ValueError("Only @axrail.com email addresses are allowed")`
    - Call `_validate_email_domain(email)` in `create_user()` after extracting email from args, before `_check_email_unique()`
    - _Bug_Condition: isBugCondition(email) where not email.lower().endswith("@axrail.com")_
    - _Expected_Behavior: Reject with ValueError before any DynamoDB or Cognito writes_
    - _Preservation: Valid @axrail.com emails continue through normal creation flow_
    - _Requirements: 2.1, 2.2, 3.1, 3.2, 3.3_

  - [x] 3.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Non-axrail Email Rejected
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior (non-axrail emails raise ValueError)
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from step 1
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - _Requirements: 2.1_

  - [x] 3.3 Verify preservation tests still pass
    - **Property 2: Preservation** - Valid axrail.com Email Creation Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm all existing behavior for valid emails, duplicate checks, and permission checks still works

---

## Bug 2: Daily 8-Hour Cap and Weekly 40-Hour Cap

- [x] 4. Write bug condition exploration test for hour caps
  - **Property 1: Bug Condition** - Exceeding 8h/day or 40h/week Accepted
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bug exists
  - **Scoped PBT Approach**: Scope to two concrete failing cases:
    - Case A (daily): A single day with >8 hours but ≤24 hours (e.g., 10 hours on Monday) — currently accepted
    - Case B (weekly): Entries totaling >40 weekly hours where no single day exceeds 24 hours — currently accepted
  - Bug Condition: `isBugCondition(entry)` where `any day > 8.0` OR `weekly_total > 40.0` (but each day ≤ 24.0)
  - Test that `validate_daily_totals()` rejects entries with any day >8h, and `validate_weekly_total()` rejects entries with weekly total >40h
  - Run test on UNFIXED code - expect FAILURE (daily cap is 24h, weekly cap doesn't exist)
  - Document counterexamples found
  - _Requirements: 1.3, 1.4, 1.5a, 2.3, 2.4, 2.5a_

- [x] 5. Write preservation property tests for hour caps (BEFORE implementing fix)
  - **Property 2: Preservation** - Valid Entries Within Caps Unchanged
  - **IMPORTANT**: Follow observation-first methodology
  - Observe: Adding an entry with ≤8h per day and ≤40h weekly total succeeds on unfixed code
  - Observe: Adding an entry with negative hours raises validation error on unfixed code
  - Observe: Adding a 28th entry to a submission raises max entries error on unfixed code
  - Write property-based tests: for all entries where each day ≤8h and weekly total ≤40h, existing acceptance behavior is preserved
  - Write property-based tests: for invalid entries (negative hours, max entries exceeded), existing rejection behavior is preserved
  - Verify tests pass on UNFIXED code
  - _Requirements: 2.5, 2.5b, 3.4, 3.5_

- [x] 6. Fix daily 8-hour cap and weekly 40-hour cap

  - [x] 6.1 Change `MAX_DAILY_HOURS` and add `MAX_WEEKLY_HOURS` and `validate_weekly_total()` in `lambdas/entries/shared_utils.py`
    - Change `MAX_DAILY_HOURS` from `Decimal("24.0")` to `Decimal("8.0")`
    - Add `MAX_WEEKLY_HOURS = Decimal("40.0")` constant
    - Add `validate_weekly_total(existing_entries, new_hours, exclude_entry_id=None)` function that:
      - Computes weekly total of `new_hours` across all `DAY_FIELDS`
      - Adds `totalHours` from each existing entry (skipping `exclude_entry_id` if provided)
      - Raises `ValueError` if combined weekly total exceeds `MAX_WEEKLY_HOURS`
    - _Bug_Condition: isBugCondition(entry) where any day > 8.0 OR weekly_total > 40.0_
    - _Expected_Behavior: Reject with ValueError when daily >8h or weekly >40h_
    - _Preservation: Entries within caps continue to be accepted; negative hours and max entries still rejected_
    - _Requirements: 2.3, 2.4, 2.5, 2.5a, 2.5b_

  - [x] 6.2 Add `validate_weekly_total` call in `lambdas/entries/AddTimesheetEntry/handler.py`
    - Import `validate_weekly_total` from `shared_utils`
    - Call `validate_weekly_total(existing_entries, hours)` after existing `validate_daily_totals()` call
    - _Requirements: 2.3, 2.5_

  - [x] 6.3 Add `validate_weekly_total` call in `lambdas/entries/UpdateTimesheetEntry/handler.py`
    - Import `validate_weekly_total` from `shared_utils`
    - Call `validate_weekly_total(existing_entries, hours, exclude_entry_id=entry_id)` after existing `validate_daily_totals()` call
    - _Requirements: 2.4, 2.5_

  - [x] 6.4 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Exceeding Caps Now Rejected
    - **IMPORTANT**: Re-run the SAME test from task 4 - do NOT write a new test
    - The test from task 4 encodes the expected behavior (>8h/day and >40h/week rejected)
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from step 4
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - _Requirements: 2.3, 2.4, 2.5a_

  - [x] 6.5 Verify preservation tests still pass
    - **Property 2: Preservation** - Valid Entries Within Caps Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 5 - do NOT write new tests
    - Run preservation property tests from step 5
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm entries within caps still accepted, negative hours and max entries still rejected

---

## Bug 3: Admin/SuperAdmin listAllSubmissions Query

- [x] 7. Write bug condition exploration test for listAllSubmissions
  - **Property 1: Bug Condition** - No Admin Query for All Submissions
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bug exists
  - **Scoped PBT Approach**: Scope to concrete case: admin/superadmin calling `list_all_submissions()` — handler does not exist yet
  - Bug Condition: `isBugCondition(caller)` where `caller.userType in ["admin", "superadmin"]` and query is `listAllSubmissions`
  - Test that `list_all_submissions(event)` exists and returns all submissions for admin callers
  - Test that `list_all_submissions(event)` with status filter returns only matching submissions
  - Test that `list_all_submissions(event)` rejects non-admin callers with permissions error
  - Run test on UNFIXED code - expect FAILURE (handler doesn't exist)
  - Document counterexamples found (e.g., ImportError because module doesn't exist)
  - _Requirements: 1.5, 1.6, 2.6, 2.7, 2.8, 2.9_

- [x] 8. Write preservation property tests for listAllSubmissions (BEFORE implementing fix)
  - **Property 2: Preservation** - listMySubmissions Behavior Unchanged
  - **IMPORTANT**: Follow observation-first methodology
  - Observe: Regular user calling `listMySubmissions` returns only their own submissions on unfixed code
  - Observe: `listMySubmissions` with `periodId` filter returns correctly filtered results on unfixed code
  - Write property-based tests: for all regular users, `listMySubmissions` continues to return only their own submissions
  - Write property-based tests: `periodId` filtering on `listMySubmissions` continues to work correctly
  - Verify tests pass on UNFIXED code
  - _Requirements: 3.7, 3.8_

- [x] 9. Fix: Add listAllSubmissions query and Lambda

  - [x] 9.1 Add `AdminSubmissionFilterInput` and `listAllSubmissions` query to `graphql/schema.graphql`
    - Add `input AdminSubmissionFilterInput { status: SubmissionStatus, periodId: ID, employeeId: ID }`
    - Add `listAllSubmissions(filter: AdminSubmissionFilterInput): [TimesheetSubmission!]!` to `Query` type
    - _Requirements: 2.6, 2.7, 2.8, 2.9_

  - [x] 9.2 Create `lambdas/submissions/ListAllSubmissions/__init__.py` (empty)
    - _Requirements: 2.6_

  - [x] 9.3 Create `lambdas/submissions/ListAllSubmissions/handler.py`
    - Import `require_user_type` from `shared.auth` (restrict to `["superadmin", "admin"]`)
    - Use `SUBMISSIONS_TABLE` environment variable
    - Implement `list_all_submissions(event)`:
      - Call `require_user_type(event, ["superadmin", "admin"])` for authorization
      - Extract optional `filter` from `event["arguments"]`
      - If `periodId` provided: query `periodId-status-index` GSI (with optional `status` key condition)
      - If only `status` provided: query `status-index` GSI
      - If no filters: use `table.scan()`
      - If `employeeId` filter provided: apply as post-query filter
      - Handle pagination with `LastEvaluatedKey` loop
      - Return list of items
    - _Bug_Condition: No handler exists for admin-level submission listing_
    - _Expected_Behavior: Admin/superadmin can list all submissions with optional filters_
    - _Preservation: listMySubmissions behavior unchanged_
    - _Requirements: 2.6, 2.7, 2.8, 2.9_

  - [x] 9.4 Add Lambda and resolver in `colabs_pipeline_cdk/stack/lambda_stack.py`
    - Add new Lambda in `_create_submission_lambdas()` after `ListMySubmissions` block
    - Use `_make_lambda("ListAllSubmissionsLambda", "TimesheetListAllSubmissions", "submissions.ListAllSubmissions.handler.handler", {"SUBMISSIONS_TABLE": ...})`
    - Grant `read_data` on submissions table
    - Add Lambda data source and create resolver for `Query.listAllSubmissions`
    - _Requirements: 2.6_

  - [x] 9.5 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Admin Query Returns All Submissions
    - **IMPORTANT**: Re-run the SAME test from task 7 - do NOT write a new test
    - The test from task 7 encodes the expected behavior (admin can list all submissions with filters)
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from step 7
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - _Requirements: 2.6, 2.7, 2.8, 2.9_

  - [x] 9.6 Verify preservation tests still pass
    - **Property 2: Preservation** - listMySubmissions Behavior Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 8 - do NOT write new tests
    - Run preservation property tests from step 8
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm listMySubmissions still returns only caller's own submissions with correct filtering

---

## Bug 4: Dashboard Admin Remove Cards (Frontend Documentation)

- [x] 10. Document frontend changes for dashboard card removal
  - **Note**: This is a frontend-only change — no backend code modifications needed
  - Document that the admin dashboard should remove total projects, total departments, and total positions summary cards
  - Ensure no regressions in other dashboard functionality
  - No exploration or preservation tests needed (no backend code to test)
  - _Requirements: 2.10, 3.9_

---

## Bug 5: Project Edit Permissions by Approval Status

- [x] 11. Write bug condition exploration test for project edit permissions
  - **Property 1: Bug Condition** - Admin Can Edit Approved Projects
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bug exists
  - **Scoped PBT Approach**: Scope to concrete failing case: admin editing a project with `approval_status == "Approved"`
  - Bug Condition: `isBugCondition(caller, project)` where `caller.userType == "admin"` AND `project.approval_status == "Approved"`
  - Test that `update_project()` raises `ForbiddenError` when admin edits an approved project
  - Run test on UNFIXED code - expect FAILURE (admin can currently edit approved projects)
  - Document counterexamples found (e.g., admin successfully edits approved project instead of getting ForbiddenError)
  - _Requirements: 1.8, 1.9, 2.11_

- [x] 12. Write preservation property tests for project edit permissions (BEFORE implementing fix)
  - **Property 2: Preservation** - Existing Project Edit Permissions Unchanged
  - **IMPORTANT**: Follow observation-first methodology
  - Observe: Admin editing a project with `approval_status == "Pending_Approval"` succeeds on unfixed code
  - Observe: Admin editing a project with `approval_status == "Rejected"` succeeds on unfixed code
  - Observe: Superadmin editing a project with any `approval_status` succeeds on unfixed code
  - Observe: Regular user editing any project raises permissions error on unfixed code
  - Observe: `projectCode` uniqueness, `plannedHours` positivity, and `status` enum validation still enforced on unfixed code
  - Write property-based tests: for all non-bug-condition cases (admin + non-Approved, superadmin + any status, regular user + any), existing behavior is preserved
  - Verify tests pass on UNFIXED code
  - _Requirements: 2.12, 2.13, 3.10, 3.11_

- [x] 13. Fix project edit permissions by approval status

  - [x] 13.1 Add approval status check in `lambdas/projects/UpdateProject/handler.py`
    - After fetching existing project with `table.get_item(...)` and before `new_code = args.get("projectCode")` block
    - Get `approval_status = existing.get("approval_status", "")`
    - If `approval_status == "Approved"` and `caller["userType"] != "superadmin"`, raise `ForbiddenError("Only superadmins can edit projects with approval status 'Approved'")`
    - Uses existing `caller` dict from `require_user_type` and already-fetched `existing` project item
    - `ForbiddenError` is already imported
    - _Bug_Condition: isBugCondition(caller, project) where caller.userType == "admin" AND project.approval_status == "Approved"_
    - _Expected_Behavior: Raise ForbiddenError for non-superadmin editing approved projects_
    - _Preservation: Admin can edit Pending_Approval/Rejected projects; superadmin can edit any; regular user still rejected; validations unchanged_
    - _Requirements: 2.11, 2.12, 2.13, 3.10, 3.11_

  - [x] 13.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Admin Editing Approved Project Rejected
    - **IMPORTANT**: Re-run the SAME test from task 11 - do NOT write a new test
    - The test from task 11 encodes the expected behavior (admin editing approved project raises ForbiddenError)
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from step 11
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - _Requirements: 2.11_

  - [x] 13.3 Verify preservation tests still pass
    - **Property 2: Preservation** - Existing Project Edit Permissions Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 12 - do NOT write new tests
    - Run preservation property tests from step 12
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm admin can still edit non-approved projects, superadmin can edit any, regular user still rejected, validations unchanged

---

## Final Checkpoint

- [x] 14. Checkpoint - Ensure all tests pass
  - Run full test suite with `pytest`
  - Ensure all bug condition exploration tests pass (tasks 1, 4, 7, 11)
  - Ensure all preservation property tests pass (tasks 2, 5, 8, 12)
  - Ensure no regressions in existing tests
  - Ask the user if questions arise
