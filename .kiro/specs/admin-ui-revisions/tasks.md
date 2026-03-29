# Implementation Plan: Admin UI Revisions

## Overview

Five independent revisions to the TimeFlow admin interface: confirmation dialogs on approvals, feedback toasts on all CRUD operations, filter fixes on master data pages, user activate/deactivate toggle, and a userId mismatch data migration script. All changes target existing Blade templates and Laravel controllers, with one new Python migration script.

## Tasks

- [x] 1. Implement Confirmation Dialog for Approval Actions
  - [x] 1.1 Add approval confirmation modal HTML and JS to the Approvals page
    - Add a styled modal overlay (`approve-modal-overlay`) to `frontend/resources/views/pages/admin/approvals.blade.php` matching the existing rejection modal pattern
    - Implement `openApproveModal(entityType, entityId, entityName)` and `closeApproveModal()` functions
    - The modal must display the entity name and entity type in the confirmation message
    - Replace all `confirm()` calls on approve buttons with `openApproveModal()` calls
    - On confirm: submit the approval request to the API; on cancel: close modal, take no action
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.6, 1.7, 1.8_

  - [x] 1.2 Write property tests for confirmation dialog behavior
    - **Property 1: Approve action shows confirmation dialog**
    - **Property 2: Cancel dialog preserves entity state**
    - **Property 3: Confirmation dialog displays entity identity**
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.6, 1.8**

- [x] 2. Implement Feedback Toasts for All CRUD Operations
  - [x] 2.1 Add success/error toasts to the Departments page
    - In `frontend/resources/views/pages/admin/departments.blade.php`, ensure `showToast()` is called on create, update, and delete success/failure paths
    - Add `setTimeout` delay (1500ms) between showing toast and `window.location.reload()` so the user can read the message
    - Ensure error toasts include the failure reason from the API response
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.15_

  - [x] 2.2 Add success/error toasts to the Positions page
    - In `frontend/resources/views/pages/admin/positions.blade.php`, apply the same toast pattern as departments
    - Show success toast on create/update/delete success, error toast on failure
    - Add `setTimeout` delay before reload
    - _Requirements: 2.7, 2.8, 2.15_

  - [x] 2.3 Add success/error toasts to the Projects page
    - In `frontend/resources/views/pages/admin/projects.blade.php`, verify existing toast coverage and fill any gaps
    - Ensure all CRUD paths (create, update, delete) show appropriate toasts
    - Add `setTimeout` delay before reload if missing
    - _Requirements: 2.9, 2.10, 2.15_

  - [x] 2.4 Add success/error toasts to the Users page
    - In `frontend/resources/views/pages/user-management.blade.php`, ensure `showToast()` is called on create, update, and delete success/failure paths
    - Add `setTimeout` delay before reload
    - _Requirements: 2.11, 2.12, 2.15_

  - [x] 2.5 Write property tests for feedback toast behavior
    - **Property 4: CRUD operations produce feedback toast**
    - **Property 5: Toast styling matches message type**
    - **Validates: Requirements 2.1–2.12, 2.14**

- [x] 3. Checkpoint - Confirm confirmation dialogs and toasts work
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Fix Filters on All Master Data Pages
  - [x] 4.1 Implement filter JavaScript for the Projects page
    - Add `applyFilters()` function to `frontend/resources/views/pages/admin/projects.blade.php` matching the pattern from departments/positions pages
    - Populate the start date dropdown dynamically from distinct start dates in the table data
    - Wire up `change`/`input` event listeners on search input, start date dropdown, and status dropdown
    - Filter by: search text against name/manager columns (case-insensitive), start date exact match, status match against `data-approval-status`
    - _Requirements: 3.7, 3.8, 3.9, 3.10, 3.18_

  - [x] 4.2 Fix filter dropdowns and logic on the Users page
    - In `frontend/resources/views/pages/user-management.blade.php`, populate the department filter dropdown from `usersData` (the `@json($users)` variable)
    - Populate the position filter dropdown from `usersData`
    - Add `data-department` and `data-position` attributes to each user table row
    - Update the existing `applyFilters()` function to include department and position filter logic
    - Ensure all filters (search, department, position, approval status) work simultaneously
    - _Requirements: 3.11, 3.12, 3.13, 3.14, 3.15, 3.16, 3.17_

  - [x] 4.3 Verify existing filters on Departments and Positions pages
    - Confirm search and approval status filters work correctly on `departments.blade.php` and `positions.blade.php`
    - Fix any issues found; ensure clearing all filters shows all rows
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.19_

  - [x] 4.4 Write property tests for filter logic
    - **Property 6: Combined filters show only matching rows**
    - **Property 7: Filter dropdowns populated from data**
    - **Validates: Requirements 3.3, 3.6, 3.10, 3.15, 3.16, 3.17, 3.18**

- [x] 5. Implement User Activate/Deactivate Toggle
  - [x] 5.1 Add GraphQL mutation constants and Laravel controller methods
    - Add `DEACTIVATE_USER` and `ACTIVATE_USER` mutation constants to `GraphQLQueries.php`
    - Add `activate($userId)` and `deactivate($userId)` methods to `UserManagementController.php`
    - Each method calls the AppSync mutation via `GraphQLClient` and returns `{ success: true/false, error?: message }`
    - Add routes: `POST /admin/users/{userId}/activate` and `POST /admin/users/{userId}/deactivate` in `web.php`
    - _Requirements: 4.4, 4.7, 4.10_

  - [x] 5.2 Add Activation_Toggle UI to the Users page
    - In `frontend/resources/views/pages/user-management.blade.php`, add a toggle switch (`<label class="toggle-switch">`) in each user row's actions column
    - Set toggle checked state based on `data-user-status` attribute (checked = active)
    - Disable toggle when `approval_status === 'Pending_Approval'`
    - Add `data-user-status` attribute to each user row
    - _Requirements: 4.1, 4.2, 4.12_

  - [x] 5.3 Wire toggle click handler with confirmation dialog and API calls
    - On toggle click: show a Confirmation_Dialog asking to confirm activation/deactivation
    - On confirm: call the appropriate Laravel endpoint (`/admin/users/{userId}/activate` or `/deactivate`)
    - On success: update toggle state, update status badge text, show success Feedback_Toast
    - On failure: revert toggle to previous state, show error Feedback_Toast with failure reason
    - On cancel: revert toggle, close dialog
    - _Requirements: 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 4.11_

  - [x] 5.4 Write property tests for activate/deactivate toggle
    - **Property 8: Toggle state reflects user status**
    - **Property 9: Failed toggle reverts to previous state**
    - **Property 11: Pending users have disabled toggle**
    - **Validates: Requirements 4.1, 4.2, 4.9, 4.12**

- [x] 6. Checkpoint - Confirm filters and toggle work
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Investigate and Fix Missing Timesheet Submissions
  - [x] 7.1 Create userId mismatch migration script
    - Create `scripts/migrate_user_ids.py` that:
      - Queries DynamoDB Users table for the target user by email/name
      - Queries Cognito user pool to get the actual Cognito `sub` for the same email
      - Compares the two userIds and logs the mismatch
      - If mismatched, updates the DynamoDB `userId` using a conditional update (idempotent)
      - Logs before/after state for audit purposes
      - Verifies the Cognito user exists before attempting the update
    - _Requirements: 5.1, 5.2, 5.3_

  - [x] 7.2 Add verification step to the migration script
    - After the userId update, the script should call `listMySubmissions` (or equivalent query) to verify the user can now retrieve timesheet data
    - Log the verification result
    - Add documentation comments in the script explaining the root cause and fix
    - _Requirements: 5.4, 5.5, 5.6_

- [x] 8. Final checkpoint - Ensure all changes are complete
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- All frontend changes are in existing Blade templates — no new pages are created
- The activate/deactivate mutations already exist in the GraphQL schema and Lambda resolvers; only the Laravel proxy layer and UI are new
