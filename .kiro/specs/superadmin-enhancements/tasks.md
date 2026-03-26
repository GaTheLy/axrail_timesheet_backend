# Implementation Plan: Superadmin Enhancements

## Overview

Backend-first approach: start with Lambda handler changes (superadmin bypass + auto-approve), then Laravel controllers/routes, then Blade frontend templates. Each task builds incrementally so nothing is orphaned.

## Tasks

- [x] 1. Lambda handler superadmin bypass for Update operations
  - [x] 1.1 Add superadmin bypass to UpdateDepartment, UpdatePosition, UpdateProject, UpdateUser handlers
    - In each handler, change the approval_status guard from `if existing.get("approval_status") == "Approved"` to `if existing.get("approval_status") == "Approved" and caller["userType"] != "superadmin"`
    - _Requirements: 4.2, 4.4_

  - [x] 1.2 Add superadmin bypass to DeleteDepartment, DeletePosition, DeleteProject, DeleteUser handlers
    - Same guard change as 1.1 but in the delete handlers
    - _Requirements: 4.3, 4.4_

  - [x] 1.3 Add auto-approve logic to CreateDepartment, CreatePosition, CreateProject handlers
    - Add `approval_status = "Approved" if caller["userType"] == "superadmin" else "Pending_Approval"` matching the existing CreateUser pattern
    - Verify CreateProject handler has the approval_status logic (it was recently created and may be missing it)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ]* 1.4 Write property test: Superadmin unrestricted update and delete (Property 7)
    - **Property 7: Superadmin unrestricted update and delete**
    - Use Hypothesis to generate random entities with random approval_status values, call update/delete with superadmin caller, assert no approval_status error raised
    - **Validates: Requirements 4.2, 4.3**

  - [ ]* 1.5 Write property test: Admin restricted on approved entities (Property 8)
    - **Property 8: Admin restricted on approved entities**
    - Use Hypothesis to generate random entities with approval_status "Approved", call update/delete with admin caller, assert ValueError raised
    - **Validates: Requirements 4.4**

  - [ ]* 1.6 Write property test: Superadmin-created entities are auto-approved (Property 9)
    - **Property 9: Superadmin-created entities are auto-approved**
    - Use Hypothesis to generate random valid entity creation inputs with superadmin caller, assert resulting approval_status is "Approved"
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.4**

  - [ ]* 1.7 Write property test: Admin-created entities are pending (Property 10)
    - **Property 10: Admin-created entities are pending**
    - Use Hypothesis to generate random valid entity creation inputs with admin caller, assert resulting approval_status is "Pending_Approval"
    - **Validates: Requirements 6.5**

- [x] 2. Checkpoint - Verify Lambda changes
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Laravel routes and ApprovalsController
  - [x] 3.1 Create ApprovalsController with index, approve, and reject methods
    - `index()`: Fetch all pending projects, departments, positions via GraphQL LIST queries, filter by `approval_status === 'Pending_Approval'`, render `approvals.blade.php`
    - `approve($type, $id)`: Map type to correct GraphQL mutation (approveDepartment, approvePosition, approveProject), return JSON response
    - `reject($type, $id)`: Same mapping but include `reason` from request body, return JSON response
    - _Requirements: 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10_

  - [x] 3.2 Register routes for the Approvals page
    - Add `GET /admin/approvals` → `ApprovalsController@index`
    - Add `POST /admin/approvals/{type}/{id}/approve` → `ApprovalsController@approve`
    - Add `POST /admin/approvals/{type}/{id}/reject` → `ApprovalsController@reject`
    - Protect routes with superadmin role middleware or in-controller guard
    - _Requirements: 3.10_

  - [ ]* 3.3 Write unit tests for ApprovalsController access control
    - Test that non-superadmin users get 403/redirect on `/admin/approvals`
    - Test approve/reject methods call correct GraphQL mutations
    - _Requirements: 3.10_

- [x] 4. DashboardController changes for pending counts
  - [x] 4.1 Update DashboardController::adminDashboard() to pass pending entity counts
    - When `$user['userType'] === 'superadmin'`, query LIST_DEPARTMENTS, LIST_POSITIONS, LIST_PROJECTS, count items where `approval_status === 'Pending_Approval'`
    - Pass `$pendingProjects`, `$pendingDepartments`, `$pendingPositions` to the view
    - For admin users, do not query or pass these variables
    - _Requirements: 1.3, 1.4, 1.6, 1.7_

  - [ ]* 4.2 Write unit tests for DashboardController pending counts
    - Test superadmin gets pending counts passed to view
    - Test admin does not get pending count variables
    - _Requirements: 1.4, 1.7_

- [x] 5. Checkpoint - Verify controller layer
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Sidebar and Dashboard Blade template changes
  - [x] 6.1 Add "Approvals" link to sidebar.blade.php for superadmin
    - Inside the existing `@if($userType === 'superadmin')` block, add an "Approvals" nav item linking to `/admin/approvals`
    - Highlight when `request()->is('admin/approvals*')`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 6.2 Add Approval Requests section to dashboard-admin.blade.php
    - Conditionally render when `$userType === 'superadmin'`
    - Display three cards (Projects, Departments, Positions) with pending counts and "Review" links to `/admin/approvals`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7_

- [x] 7. Approvals page (new Blade template)
  - [x] 7.1 Create approvals.blade.php with tabbed entity review
    - Three tabs: Projects, Departments, Positions
    - Each tab shows a table with columns: Name, Code, Created Date, Created By, Actions (Approve/Reject)
    - Approve button triggers AJAX POST to `/admin/approvals/{type}/{id}/approve`
    - Reject button opens a reason modal, then AJAX POST to `/admin/approvals/{type}/{id}/reject` with reason
    - Success/error toast notifications on action completion
    - JS handles tab switching and AJAX calls
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9_

- [x] 8. Unrestricted edit/delete on frontend for superadmin
  - [x] 8.1 Update departments.blade.php, positions.blade.php, projects.blade.php, user-management.blade.php
    - Change edit/delete button visibility condition from `@if($approvalStatus !== 'Approved')` to `@if($approvalStatus !== 'Approved' || $userType === 'superadmin')`
    - _Requirements: 4.1, 4.5_

- [x] 9. User creation role dropdown for superadmin
  - [x] 9.1 Update user-management.blade.php create form with role dropdown
    - When `$userType === 'superadmin'`, replace read-only Role input with a `<select>` dropdown with options "Admin" and "User"
    - Update JS save handler to include selected `userType` value in the POST body
    - For admin callers, keep existing read-only input
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 10. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Backend Lambda changes come first (tasks 1-2) so the API layer is ready before frontend work
- Existing approve/reject mutations are already working — no GraphQL schema changes needed
- No new DynamoDB tables or schema changes required
- Property-based tests use Hypothesis (Python) for Lambda handlers
