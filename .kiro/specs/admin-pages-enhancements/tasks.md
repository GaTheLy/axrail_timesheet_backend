# Implementation Plan: Admin Pages Enhancements

## Overview

Implement four admin page enhancements: a client-side completeness filter for the Submission Page, restricted edit/delete actions on approved users (frontend + backend guards), auto-generated read-only User Code, and auto-generated read-only Role field. Changes span Blade templates, JavaScript, Python Lambda resolvers, and the GraphQL schema.

## Tasks

- [x] 1. Add `userCode` field to GraphQL schema and update CreateUser Lambda
  - [x] 1.1 Add `userCode: String` field to the `User` type in `graphql/schema.graphql`
    - Add `userCode: String` to the `User` type definition
    - Ensure `userCode` is NOT added to `CreateUserInput` (server-generated only)
    - _Requirements: 3.1, 3.2, 3.5_

  - [x] 1.2 Implement `generate_next_user_code` function in `lambdas/users/CreateUser/handler.py`
    - Scan the Users table for existing `userCode` values
    - Parse numeric suffixes, find the max, increment by 1
    - Format as `USR-{NNN}` zero-padded to 3 digits (extending beyond 3 if needed)
    - Return `USR-001` when no existing codes are found
    - _Requirements: 3.2_

  - [x] 1.3 Integrate user code generation into the CreateUser handler
    - Call `generate_next_user_code` after authorization but before writing to DynamoDB
    - Store the generated `userCode` on the new user item, ignoring any client-provided value
    - _Requirements: 3.2, 3.5_

  - [ ]* 1.4 Write property test for sequential user code generation
    - **Property 4: Sequential user code generation**
    - Generate random sets of existing `USR-NNN` codes, verify next code is `USR-{max+1}`
    - Verify `USR-001` is returned when no codes exist
    - Add test to `tests/unit/test_users.py` or a new `tests/unit/test_user_code_properties.py`
    - **Validates: Requirements 3.2**

- [x] 2. Enforce role assignment for admin-created users in CreateUser Lambda
  - [x] 2.1 Add role override logic to `lambdas/users/CreateUser/handler.py`
    - When the caller is an admin (userType: `admin`) and the new user has userType `user`, force `role = "Employee"` regardless of input
    - _Requirements: 4.4, 4.5_

  - [ ]* 2.2 Write property test for admin-created users always get Employee role
    - **Property 5: Admin-created users always get Employee role**
    - Generate random `CreateUserInput` with varying role values for admin callers
    - Verify the resulting user record always has `role = "Employee"`
    - Add test to `tests/unit/test_users.py` or a new `tests/unit/test_user_role_properties.py`
    - **Validates: Requirements 4.4**

- [x] 3. Add backend guards to UpdateUser and DeleteUser Lambdas
  - [x] 3.1 Add active-status guard to `lambdas/users/UpdateUser/handler.py`
    - After fetching the existing user record, check if `status == "active"`
    - If active, raise `ValueError("Approved users cannot be edited")` before any field updates
    - _Requirements: 2.4_

  - [x] 3.2 Add active-status guard to `lambdas/users/DeleteUser/handler.py`
    - After fetching the existing user record, check if `status == "active"`
    - If active, raise `ValueError("Approved users cannot be deleted")` before the DynamoDB delete
    - _Requirements: 2.5_

  - [ ]* 3.3 Write property test for backend rejection of mutations on active users
    - **Property 3: Backend rejects mutations on active users**
    - Generate random active users and random mutation inputs
    - Verify `updateUser` and `deleteUser` raise errors and leave the record unchanged
    - Add test to `tests/unit/test_users.py` or a new `tests/unit/test_active_user_guard_properties.py`
    - **Validates: Requirements 2.4, 2.5**

- [x] 4. Checkpoint - Ensure all backend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement frontend changes for User Management Page
  - [x] 5.1 Conditionally hide edit/delete action icons for approved users in the User Management Page Blade template
    - For each user row, check `user.status`
    - If `active`: do not render edit and delete action icons
    - If not `active`: render both icons as currently done
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 5.2 Add read-only Code field to the User Form modal
    - In "Add" mode: display a read-only input with placeholder text "Auto-generated"
    - In "Edit" mode: display a read-only input showing the existing `userCode`
    - Style with grey background (`background-color: #e9ecef`)
    - Exclude the Code field from the form submission payload
    - _Requirements: 3.1, 3.3, 3.4, 3.5_

  - [x] 5.3 Add read-only Role field to the User Form modal
    - In "Add" mode: display a read-only input pre-filled with "Employee"
    - In "Edit" mode: display a read-only input showing the existing role value
    - Style with grey background (`background-color: #e9ecef`)
    - Exclude the Role field from the editable form payload
    - _Requirements: 4.1, 4.2, 4.3, 4.5_

  - [ ]* 5.4 Write property test for action icon visibility based on user status
    - **Property 2: Action icon visibility is determined by user status**
    - Generate random user records with random statuses
    - Verify icons are hidden if and only if status is `active`
    - Add test to `tests/unit/` as `test_action_icon_visibility_properties.py`
    - **Validates: Requirements 2.1, 2.2, 2.3**

- [x] 6. Implement Submission Page completeness filter
  - [x] 6.1 Add filter dropdown to the Submission Page Blade template
    - Add a `<select>` control with options: All, Complete, Incomplete
    - Place alongside the existing period selector
    - Default to "All" on page load
    - _Requirements: 1.1, 1.5_

  - [x] 6.2 Implement client-side JavaScript filter logic
    - Read the selected filter value on change
    - Iterate over submission table rows, comparing each row's `totalHours` data attribute against the 40-hour threshold
    - Show/hide rows: Complete shows `totalHours >= 40`, Incomplete shows `totalHours < 40`, All shows everything
    - Update the submission count indicator to reflect filtered results
    - Apply filter without full page reload
    - _Requirements: 1.2, 1.3, 1.4, 1.6, 1.7_

  - [ ]* 6.3 Write property test for completeness filter partitioning
    - **Property 1: Completeness filter partitions submissions correctly**
    - Generate random lists of submissions with random `totalHours` values
    - Apply each filter mode (All, Complete, Incomplete) and verify output matches criteria
    - Verify count indicator equals the length of the filtered result
    - Add test to `tests/unit/` as `test_submission_filter_properties.py`
    - **Validates: Requirements 1.2, 1.3, 1.4, 1.7**

- [x] 7. Wire frontend components and handle error display
  - [x] 7.1 Add error handling for API rejection of active user mutations
    - When the GraphQL API returns an error for update/delete of an active user, display a toast notification with the error message
    - Ensure graceful degradation if the filter dropdown fails to initialize (default to showing all submissions)
    - _Requirements: 2.4, 2.5_

- [x] 8. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Backend tasks (1-3) are implemented first so frontend can integrate against working APIs
- Property tests validate universal correctness properties from the design document
- Python (Hypothesis) is used for backend property tests; frontend filter logic can be extracted into a testable utility for property testing
