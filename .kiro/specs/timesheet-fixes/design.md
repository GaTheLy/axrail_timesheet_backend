# Bugfix Design Document

## Introduction

This document describes the technical design for fixing five bugs in the COLABS Employee Timesheet Management System. Each fix is scoped to minimal changes in existing files, following the established patterns in the codebase.

---

## Bug 1: Email Domain Restriction on User Creation

### Changes Required

#### File: `lambdas/users/CreateUser/handler.py`

Add a constant and validation function for email domain:

```python
ALLOWED_EMAIL_DOMAIN = "@axrail.com"
```

Add a new helper function `_validate_email_domain(email)` that:
- Checks if `email.lower()` ends with `ALLOWED_EMAIL_DOMAIN`
- Raises `ValueError` with message: `"Only @axrail.com email addresses are allowed"`

Call `_validate_email_domain(email)` in `create_user()` immediately after extracting the `email` from `args`, before `_check_email_unique()`. This ensures the domain check happens before any DynamoDB or Cognito writes.

### No Other Files Affected

The Cognito User Pool (`auth_stack.py`) does not need changes since `self_sign_up_enabled=False` means all users are admin-created, and the Lambda validation is sufficient.

---

## Bug 2: Daily 8-Hour Cap and Weekly 40-Hour Cap on Timesheet Entries

### Changes Required

#### File: `lambdas/entries/shared_utils.py`

1. Change the existing constant and add a new one:

```python
MAX_DAILY_HOURS = Decimal("8.0")    # Changed from Decimal("24.0")
MAX_WEEKLY_HOURS = Decimal("40.0")  # New constant
```

2. Add a new function `validate_weekly_total(existing_entries, new_hours, exclude_entry_id=None)` that:
   - Computes the weekly total of `new_hours` across all `DAY_FIELDS`
   - Adds the `totalHours` from each existing entry (skipping `exclude_entry_id` if provided)
   - Raises `ValueError` if the combined weekly total exceeds `MAX_WEEKLY_HOURS` with message: `"Total weekly hours across all entries would be {total}, which exceeds the maximum of {MAX_WEEKLY_HOURS}"`

3. The existing `validate_daily_totals()` function already enforces the per-day cap using `MAX_DAILY_HOURS`. Changing the constant from `24.0` to `8.0` is the only change needed for the daily cap. No logic changes to `validate_daily_totals()`.

#### File: `lambdas/entries/AddTimesheetEntry/handler.py`

Add a call to `validate_weekly_total(existing_entries, hours)` after the existing `validate_daily_totals()` call. Import `validate_weekly_total` from `shared_utils`.

#### File: `lambdas/entries/UpdateTimesheetEntry/handler.py`

Add a call to `validate_weekly_total(existing_entries, hours, exclude_entry_id=entry_id)` after the existing `validate_daily_totals()` call. Import `validate_weekly_total` from `shared_utils`.

---

## Bug 3: Admin/SuperAdmin Query to View All Submissions

### Changes Required

#### File: `graphql/schema.graphql`

Add a new input type for admin-level filtering:

```graphql
input AdminSubmissionFilterInput {
  status: SubmissionStatus
  periodId: ID
  employeeId: ID
}
```

Add a new query to the `Query` type:

```graphql
listAllSubmissions(filter: AdminSubmissionFilterInput): [TimesheetSubmission!]!
```

#### New File: `lambdas/submissions/ListAllSubmissions/__init__.py`

Empty init file (follows existing pattern).

#### New File: `lambdas/submissions/ListAllSubmissions/handler.py`

Create a new Lambda handler following the `ListMySubmissions` pattern:

- Import `require_user_type` from `shared.auth` (restricts to `["superadmin", "admin"]`)
- Environment variable: `SUBMISSIONS_TABLE`
- The `list_all_submissions(event)` function:
  - Calls `require_user_type(event, ["superadmin", "admin"])` for authorization
  - Extracts optional `filter` from `event["arguments"]`
  - If `periodId` is provided: query using the existing `periodId-status-index` GSI (partition key: `periodId`, sort key: `status`)
    - If both `periodId` and `status` are provided: use key condition on both
    - If only `periodId`: use key condition on `periodId` only
  - If only `status` is provided (no `periodId`): query using the existing `status-index` GSI
  - If no filters: use `table.scan()` to return all submissions
  - If `employeeId` filter is provided: apply as a post-query filter on the results
  - Handle pagination with `LastEvaluatedKey` loop (same pattern as `ListMySubmissions`)
  - Return the list of items

#### File: `colabs_pipeline_cdk/stack/lambda_stack.py`

Add a new Lambda in `_create_submission_lambdas()` after the existing `ListMySubmissions` block:

```python
# ListAllSubmissions
fn = self._make_lambda("ListAllSubmissionsLambda", "TimesheetListAllSubmissions",
                       "submissions.ListAllSubmissions.handler.handler",
                       {"SUBMISSIONS_TABLE": self._table_names["submissions"]})
self._tables["submissions"].grant_read_data(fn)
ds = self._graphql_api.add_lambda_data_source("ListAllSubmissionsDataSource", fn)
ds.create_resolver("Query_listAllSubmissions_Resolver", type_name="Query", field_name="listAllSubmissions")
```

### DynamoDB GSIs Already Available

The submissions table already has these GSIs (from `dynamodb_stack.py`):
- `periodId-status-index` (partition: `periodId`, sort: `status`) — for period + status filtering
- `status-index` (partition: `status`) — for status-only filtering
- `employeeId-periodId-index` (partition: `employeeId`, sort: `periodId`) — not needed for this query

No new GSIs or DynamoDB changes required.

---

## Bug 4: Dashboard Admin Remove Cards (Frontend Only)

### No Backend Changes Required

This is a frontend-only change. The admin dashboard UI should remove the total projects, total departments, and total positions summary cards. No backend Lambda, GraphQL schema, or CDK changes are needed.

The frontend team should:
- Remove or hide the summary card components for total projects, departments, and positions from the admin dashboard view
- Ensure no regressions in other dashboard functionality

---

## Bug 5: Project Edit Permissions by Approval Status

### Changes Required

#### File: `lambdas/projects/UpdateProject/handler.py`

Add an authorization check after fetching the existing project and before applying updates. Insert between the `existing = table.get_item(...)` block and the `new_code = args.get("projectCode")` block:

```python
approval_status = existing.get("approval_status", "")
if approval_status == "Approved" and caller["userType"] != "superadmin":
    raise ForbiddenError(
        "Only superadmins can edit projects with approval status 'Approved'"
    )
```

This uses the existing `caller` dict (from `require_user_type`) and the already-fetched `existing` project item. The `ForbiddenError` class is already imported.

No changes to the GraphQL schema or CDK stack are needed — the existing `updateProject` mutation and resolver remain the same.

---

## Summary of Files Changed

| Bug | Files Modified | Files Created |
|-----|---------------|---------------|
| 1 | `lambdas/users/CreateUser/handler.py` | — |
| 2 | `lambdas/entries/shared_utils.py`, `lambdas/entries/AddTimesheetEntry/handler.py`, `lambdas/entries/UpdateTimesheetEntry/handler.py` | — |
| 3 | `graphql/schema.graphql`, `colabs_pipeline_cdk/stack/lambda_stack.py` | `lambdas/submissions/ListAllSubmissions/__init__.py`, `lambdas/submissions/ListAllSubmissions/handler.py` |
| 4 | — (frontend only) | — |
| 5 | `lambdas/projects/UpdateProject/handler.py` | — |
