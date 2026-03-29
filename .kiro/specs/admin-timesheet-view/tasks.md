# Implementation Plan: Admin Timesheet View

## Overview

Transform the admin/superadmin Timesheet page into a read-only "Timesheet Submissions" overview. Changes span the GraphQL schema, four Python Lambdas (CreateUser, auto-provisioning, deadline enforcement, deadline reminder), two new Blade templates (submissions view, submission detail), the Timesheet page controller routing, and the User Management form. Backend changes are implemented first, followed by frontend.

## Tasks

- [x] 1. Make role and positionId optional for admin/superadmin in CreateUser
  - [x] 1.1 Update GraphQL schema to make `role` and `positionId` optional in `CreateUserInput`
    - In `graphql/schema.graphql`, change `role: Role!` to `role: Role` and `positionId: ID!` to `positionId: ID` in `CreateUserInput`
    - _Requirements: 1.1, 1.2_

  - [x] 1.2 Update CreateUser Lambda validation to conditionally require role and positionId
    - In `lambdas/users/CreateUser/handler.py`, only validate presence of `role` and `positionId` when `userType` is `user`
    - For `admin` or `superadmin`, allow missing `role` and `positionId`; store empty string or omit
    - _Requirements: 1.1, 1.2_

  - [ ]* 1.3 Write property test: admin/superadmin user creation does not require position or role
    - **Property 1: Admin/superadmin user creation does not require position or role**
    - Generate random `CreateUserInput` with `userType` in {admin, superadmin, user}
    - Verify validation passes without positionId/role for admin/superadmin, and fails without them for user
    - Add test to `tests/unit/test_admin_timesheet_properties.py`
    - **Validates: Requirements 1.1, 1.2**

- [x] 2. Exclude admin/superadmin from auto-provisioning Lambda
  - [x] 2.1 Add userType filter to `_get_all_employees()` in `lambdas/auto_provisioning/handler.py`
    - Add `Attr("userType").eq("user")` to the existing filter expression so only `userType == "user"` users receive Draft submissions
    - _Requirements: 2.1_

  - [ ]* 2.2 Write property test: auto-provisioning excludes admin/superadmin users
    - **Property 2: Auto-provisioning excludes admin/superadmin users**
    - Generate random lists of users with mixed userTypes, run provisioning filter logic
    - Verify Draft submissions are only created for userType "user"
    - Add test to `tests/unit/test_admin_timesheet_properties.py`
    - **Validates: Requirements 2.1**

- [x] 3. Exclude admin/superadmin from deadline enforcement Lambda
  - [x] 3.1 Add userType filter to `_get_all_employees()` in `lambdas/deadline_enforcement/handler.py`
    - Add `Attr("userType").eq("user")` to the filter expression so zero-hour submissions and under-40-hours notifications only target `userType == "user"`
    - _Requirements: 2.2, 2.3_

  - [ ]* 3.2 Write property test: deadline enforcement excludes admin/superadmin users
    - **Property 3: Deadline enforcement excludes admin/superadmin users**
    - Generate random lists of users with mixed userTypes and a period
    - Verify zero-hour submissions and notification emails only target userType "user"
    - Add test to `tests/unit/test_admin_timesheet_properties.py`
    - **Validates: Requirements 2.2, 2.3**

- [x] 4. Exclude admin/superadmin from deadline reminder Lambda
  - [x] 4.1 Add userType check to `lambdas/deadline_reminder/handler.py`
    - After fetching the user record for each Draft submission, skip sending reminder email if `userType` is `admin` or `superadmin`
    - _Requirements: 2.4_

  - [ ]* 4.2 Write property test: deadline reminder excludes admin/superadmin users
    - **Property 4: Deadline reminder excludes admin/superadmin users**
    - Generate random lists of users with Draft submissions and mixed userTypes
    - Verify reminder emails are only sent to userType "user"
    - Add test to `tests/unit/test_admin_timesheet_properties.py`
    - **Validates: Requirements 2.4**

- [x] 5. Checkpoint - Ensure all backend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement Timesheet page routing for admin/superadmin
  - [x] 6.1 Update Timesheet page controller to route by userType
    - In the controller handling the `/timesheet` route, check `session('user.userType')`
    - If `admin` or `superadmin`, call `listAllSubmissions` and `listUsers` GraphQL queries, then render `timesheet-submissions` Blade template
    - If `user`, render the existing employee timesheet template unchanged
    - _Requirements: 3.1, 3.3, 3.4_

  - [ ]* 6.2 Write feature test: Timesheet page routing by userType
    - **Property 5: Timesheet page routing by userType**
    - Test that admin/superadmin sessions render the submissions view
    - Test that user sessions render the employee timesheet form
    - Add test to Laravel feature tests
    - **Validates: Requirements 3.1**

- [x] 7. Create Submissions View Blade template
  - [x] 7.1 Create `frontend/resources/views/pages/timesheet-submissions.blade.php`
    - Page title: "Timesheet Submissions"
    - Filter bar: date range picker (default current week), "All Users" dropdown populated from `listUsers`, "All Status" dropdown (All Status, Draft, Submitted)
    - Data table columns: Week Period, User Name, Total Hours, Status (color-coded badge: green for Submitted, red for Draft), Actions (eye view icon)
    - View icon links to submission detail view
    - Do NOT render "+ New Entry" button, deadline countdown, weekly total target, or "History" button
    - Do NOT render edit or delete action icons on submission rows
    - _Requirements: 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 4.1, 4.2, 4.3, 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x] 7.2 Implement client-side JavaScript filtering without page reload
    - On date range change, filter table rows by matching period
    - On user dropdown change, filter rows by employeeId
    - On status dropdown change, filter rows by status value
    - "All Users" and "All Status" selections show all rows for that dimension
    - _Requirements: 4.4, 4.5, 4.6, 4.7_

  - [ ]* 7.3 Write property test: client-side date range filtering
    - **Property 6: Client-side date range filtering**
    - Generate random submission lists with various periodIds and date ranges
    - Apply date filter, verify output contains exactly matching submissions
    - Add test to `tests/unit/test_admin_timesheet_properties.py`
    - **Validates: Requirements 4.4**

  - [ ]* 7.4 Write property test: client-side user filtering
    - **Property 7: Client-side user filtering**
    - Generate random submission lists with various employeeIds, apply user filter
    - Verify output contains exactly matching submissions; "All Users" shows all
    - Add test to `tests/unit/test_admin_timesheet_properties.py`
    - **Validates: Requirements 4.5**

  - [ ]* 7.5 Write property test: client-side status filtering
    - **Property 8: Client-side status filtering**
    - Generate random submission lists with mixed statuses, apply status filter
    - Verify output contains exactly matching submissions; "All Status" shows all
    - Add test to `tests/unit/test_admin_timesheet_properties.py`
    - **Validates: Requirements 4.6**

- [x] 8. Create Submission Detail View Blade template
  - [x] 8.1 Create `frontend/resources/views/pages/submission-detail.blade.php`
    - Header: employee name, week period, submission status, total hours
    - Entries table columns: Project Code, Saturday, Sunday, Monday, Tuesday, Wednesday, Thursday, Friday, Total Hours
    - All data read-only (no edit or delete controls)
    - Back navigation link to Submissions_View
    - Empty state message: "No entries were logged for this period" when submission has no entries
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 8.2 Add controller method and route for submission detail view
    - Add route for viewing a specific submission (e.g., `/timesheet/submissions/{submissionId}`)
    - Call `getTimesheetSubmission` GraphQL query to fetch submission and entries
    - Pass data to `submission-detail` Blade template
    - _Requirements: 3.8, 6.1_

  - [ ]* 8.3 Write feature test: submission detail view displays complete read-only data
    - **Property 10: Submission detail view displays complete read-only data**
    - Test detail view renders employee name, week period, status, total hours, and entries table
    - Test no edit/delete controls are present
    - Test empty state message when no entries exist
    - Add test to Laravel feature tests
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.5**

- [x] 9. Update User Management Form to hide Position/Role for admin userType
  - [x] 9.1 Add JavaScript to `frontend/resources/views/pages/user-management.blade.php`
    - Listen for changes on the userType dropdown in the user creation form
    - When `admin` is selected, hide the Position and Role dropdown fields
    - When `user` is selected, show the Position and Role dropdown fields
    - _Requirements: 1.3, 1.4_

  - [ ]* 9.2 Write feature test: employee-specific UI elements hidden for admin/superadmin
    - **Property 9: Employee-specific UI elements hidden for admin/superadmin**
    - Test that Position and Role dropdowns are hidden when userType is admin
    - Test that Position and Role dropdowns are visible when userType is user
    - Add test to Laravel feature tests
    - **Validates: Requirements 1.3, 1.4**

- [x] 10. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Backend Lambda changes (tasks 1-4) are implemented first so frontend can integrate against correct behavior
- Python (Hypothesis) is used for backend property tests; frontend properties are validated through Laravel feature tests
- Property tests validate universal correctness properties from the design document
- Checkpoints ensure incremental validation after backend and full implementation phases
