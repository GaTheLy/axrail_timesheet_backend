# Bugfix Requirements Document

## Introduction

This document covers five bugs in the COLABS Employee Timesheet Management System that affect user creation security, timesheet hour validation, admin visibility, dashboard UI, and project edit permissions. These bugs range from missing input validation to missing authorization checks and missing admin-level query capabilities.

---

## Bug 1: Email Domain Restriction Missing on User Creation

### Bug Analysis

#### Current Behavior (Defect)

1.1 WHEN an admin or superadmin creates a user with an email address that does not belong to the `@axrail.com` domain (e.g., `user@gmail.com`) THEN the system accepts the email and creates the user account in DynamoDB and Cognito without any domain validation error

1.2 WHEN an admin or superadmin creates a user with a malformed email that still passes uniqueness checks (e.g., `user@competitor.com`) THEN the system creates the account and sends a Cognito invitation to that external email address

#### Expected Behavior (Correct)

2.1 WHEN an admin or superadmin creates a user with an email address that does not end with `@axrail.com` THEN the system SHALL reject the request with a validation error indicating only `@axrail.com` emails are allowed, before any DynamoDB or Cognito writes occur

2.2 WHEN an admin or superadmin creates a user with a valid `@axrail.com` email address THEN the system SHALL proceed with user creation as normal (uniqueness check, DynamoDB write, Cognito account creation)

#### Unchanged Behavior (Regression Prevention)

3.1 WHEN an admin or superadmin creates a user with a valid `@axrail.com` email that is already in use THEN the system SHALL CONTINUE TO reject the request with an "email already in use" error

3.2 WHEN an admin or superadmin creates a user with valid enum values for `userType` and `role` THEN the system SHALL CONTINUE TO validate those enums and create the user successfully

3.3 WHEN an admin attempts to create a superadmin or admin account THEN the system SHALL CONTINUE TO reject the request with a permissions error

---

## Bug 2: Max 40 Hours Per Week Not Enforced (Only 24h/day Cap Exists)

### Bug Analysis

#### Current Behavior (Defect)

1.3 WHEN a user adds or updates timesheet entries such that the total weekly hours across all entries in a submission exceed 40 hours (e.g., 7 entries each with 8 hours per day = 56 hours) THEN the system accepts the entries without any weekly total validation error, as long as no single day exceeds 24 hours

1.4 WHEN a user has existing entries totaling 35 weekly hours and adds a new entry with 10 weekly hours (total = 45) THEN the system accepts the new entry because `validate_daily_totals()` only checks per-day caps, not the weekly aggregate

1.5a WHEN a user adds or updates a timesheet entry where a single day's total across all entries exceeds 8 hours but remains under 24 hours THEN the system accepts the entry because the daily cap is set to 24 hours instead of 8 hours

#### Expected Behavior (Correct)

2.3 WHEN a user adds a timesheet entry that would cause the total weekly hours across all entries in the submission to exceed 40 hours THEN the system SHALL reject the entry with a validation error indicating the 40-hour weekly maximum would be exceeded

2.4 WHEN a user updates a timesheet entry that would cause the total weekly hours across all entries in the submission to exceed 40 hours THEN the system SHALL reject the update with a validation error indicating the 40-hour weekly maximum would be exceeded

2.5 WHEN a user adds or updates a timesheet entry and the resulting total weekly hours remain at or below 40 hours THEN the system SHALL accept the entry as normal

2.5a WHEN a user adds or updates a timesheet entry where a single day's total across all entries in the submission would exceed 8 hours THEN the system SHALL reject the entry with a validation error indicating the 8-hour daily maximum would be exceeded

2.5b WHEN a user adds or updates a timesheet entry where each day's total across all entries remains at or below 8 hours THEN the system SHALL accept the entry as normal (subject to the 40-hour weekly cap)

#### Unchanged Behavior (Regression Prevention)

3.4 WHEN a user adds an entry with negative or invalid daily hour values THEN the system SHALL CONTINUE TO reject the entry with the existing validation errors

3.5 WHEN a user adds an entry to a submission that already has 27 entries THEN the system SHALL CONTINUE TO reject the entry with the max entries validation error

---

## Bug 3: No Admin/SuperAdmin Query to View All Timesheets with Filters

### Bug Analysis

#### Current Behavior (Defect)

1.5 WHEN an admin or superadmin needs to view all employee timesheet submissions THEN the system provides no query to do so; only `listMySubmissions` exists, which filters by the caller's own `employeeId`

1.6 WHEN an admin or superadmin calls `listMySubmissions` THEN the system returns only the admin's own submissions (if any), not submissions from other employees

#### Expected Behavior (Correct)

2.6 WHEN an admin or superadmin calls the new `listAllSubmissions` query without filters THEN the system SHALL return all timesheet submissions across all employees

2.7 WHEN an admin or superadmin calls `listAllSubmissions` with a `status` filter (e.g., `Draft` or `Submitted`) THEN the system SHALL return only submissions matching that status

2.8 WHEN an admin or superadmin calls `listAllSubmissions` with a `periodId` filter THEN the system SHALL return only submissions for that specific period

2.9 WHEN a regular user (non-admin, non-superadmin) attempts to call `listAllSubmissions` THEN the system SHALL reject the request with a permissions error

#### Unchanged Behavior (Regression Prevention)

3.7 WHEN a regular user calls `listMySubmissions` THEN the system SHALL CONTINUE TO return only that user's own submissions

3.8 WHEN any user calls `listMySubmissions` with a `periodId` filter THEN the system SHALL CONTINUE TO filter results by period correctly

---

## Bug 4: Dashboard Admin Remove Cards (Frontend Documentation)

### Bug Analysis

#### Current Behavior (Defect)

1.7 WHEN an admin views the admin dashboard THEN the system displays total projects, total departments, and total positions summary cards

#### Expected Behavior (Correct)

2.10 WHEN an admin views the admin dashboard THEN the system SHALL NOT display the total projects, total departments, and total positions summary cards; these cards should be removed from the dashboard UI

#### Unchanged Behavior (Regression Prevention)

3.9 WHEN an admin navigates to the admin dashboard THEN the system SHALL CONTINUE TO display all other dashboard content and functionality that is not related to the removed cards

---

## Bug 5: Project Edit Permissions Not Differentiated by Approval Status

### Bug Analysis

#### Current Behavior (Defect)

1.8 WHEN an admin attempts to edit a project with `approval_status` of "Approved" THEN the system allows the edit because `require_user_type(event, ["superadmin", "admin"])` does not differentiate based on approval status

1.9 WHEN a superadmin or admin edits any project THEN the system applies the same permission check regardless of the project's `approval_status`, treating all statuses equally

#### Expected Behavior (Correct)

2.11 WHEN an admin attempts to edit a project with `approval_status` of "Approved" THEN the system SHALL reject the request with a permissions error indicating only superadmins can edit approved projects

2.12 WHEN an admin attempts to edit a project with `approval_status` of "Pending_Approval" or "Rejected" THEN the system SHALL allow the edit to proceed

2.13 WHEN a superadmin attempts to edit a project with any `approval_status` (Pending_Approval, Approved, or Rejected) THEN the system SHALL allow the edit to proceed

#### Unchanged Behavior (Regression Prevention)

3.10 WHEN a regular user (non-admin, non-superadmin) attempts to edit any project THEN the system SHALL CONTINUE TO reject the request with a permissions error

3.11 WHEN an admin or superadmin edits a project THEN the system SHALL CONTINUE TO validate `projectCode` uniqueness, `plannedHours` positivity, and `status` enum values as before
