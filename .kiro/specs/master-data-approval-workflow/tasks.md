# Implementation Plan: Master Data Approval Workflow

## Overview

Extend the TimeFlow platform with a unified approval workflow for Departments, Positions, and Users, following the existing Project approval pattern. Backend Lambda resolvers are implemented first (new approve/reject handlers + modifications to create/update/delete handlers), followed by GraphQL schema updates, CDK wiring, and frontend changes across Blade templates, controllers, and routes.

## Tasks

- [x] 1. Update GraphQL schema with approval fields and mutations
  - [x] 1.1 Add `approval_status` and `rejectionReason` fields to Department, Position, and User types in `graphql/schema.graphql`
    - Add `approval_status: ApprovalStatus!` and `rejectionReason: String` to the `Department` type
    - Add `approval_status: ApprovalStatus!` and `rejectionReason: String` to the `Position` type
    - Add `approval_status: ApprovalStatus!` and `rejectionReason: String` to the `User` type (separate from existing `status` field)
    - _Requirements: 1.1, 1.2, 8.7, 8.8_

  - [x] 1.2 Add six new approval/rejection mutations to the Mutation type in `graphql/schema.graphql`
    - `approveDepartment(departmentId: ID!): Department!`
    - `rejectDepartment(departmentId: ID!, reason: String!): Department!`
    - `approvePosition(positionId: ID!): Position!`
    - `rejectPosition(positionId: ID!, reason: String!): Position!`
    - `approveUser(userId: ID!): User!`
    - `rejectUser(userId: ID!, reason: String!): User!`
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

- [x] 2. Implement new approve/reject Lambda resolvers for Departments
  - [x] 2.1 Create `lambdas/departments/ApproveDepartment/handler.py`
    - Call `require_user_type(event, ["superadmin"])` for authorization
    - Fetch department by `departmentId`, raise error if not found
    - Validate `approval_status == "Pending_Approval"`, raise error otherwise
    - Update `approval_status` to `Approved`, set `updatedBy` and `updatedAt`
    - Return the full updated item
    - Follow the existing `ApproveProject` handler pattern
    - _Requirements: 4.1, 4.7, 4.8, 4.9_

  - [x] 2.2 Create `lambdas/departments/RejectDepartment/handler.py`
    - Call `require_user_type(event, ["superadmin"])` for authorization
    - Fetch department by `departmentId`, raise error if not found
    - Validate `approval_status == "Pending_Approval"`, raise error otherwise
    - Validate rejection reason is non-empty
    - Update `approval_status` to `Rejected`, store `rejectionReason`, set `updatedBy` and `updatedAt`
    - Return the full updated item
    - _Requirements: 4.4, 4.7, 4.8, 4.9_

  - [ ]* 2.3 Write property test for ApproveDepartment (Property 3)
    - **Property 3: Approving a pending entity transitions it to Approved**
    - Generate random pending departments, verify approve transitions to `Approved`
    - **Validates: Requirements 4.1**

  - [ ]* 2.4 Write property test for RejectDepartment (Property 4)
    - **Property 4: Rejecting a pending entity transitions it to Rejected and stores the reason**
    - Generate random pending departments and non-empty reason strings, verify transition and reason storage
    - **Validates: Requirements 4.4**

- [x] 3. Implement new approve/reject Lambda resolvers for Positions
  - [x] 3.1 Create `lambdas/positions/ApprovePosition/handler.py`
    - Mirror the `ApproveDepartment` handler pattern for positions
    - Call `require_user_type(event, ["superadmin"])`, validate entity exists and is pending
    - Update `approval_status` to `Approved`, set audit fields
    - _Requirements: 4.2, 4.7, 4.8, 4.9_

  - [x] 3.2 Create `lambdas/positions/RejectPosition/handler.py`
    - Mirror the `RejectDepartment` handler pattern for positions
    - Validate rejection reason is non-empty
    - Update `approval_status` to `Rejected`, store `rejectionReason`, set audit fields
    - _Requirements: 4.5, 4.7, 4.8, 4.9_

  - [ ]* 3.3 Write property test for ApprovePosition (Property 3)
    - **Property 3: Approving a pending entity transitions it to Approved**
    - Generate random pending positions, verify approve transitions to `Approved`
    - **Validates: Requirements 4.2**

  - [ ]* 3.4 Write property test for RejectPosition (Property 4)
    - **Property 4: Rejecting a pending entity transitions it to Rejected and stores the reason**
    - Generate random pending positions and non-empty reason strings
    - **Validates: Requirements 4.5**

- [x] 4. Implement new approve/reject Lambda resolvers for Users
  - [x] 4.1 Create `lambdas/users/ApproveUser/handler.py`
    - Mirror the `ApproveDepartment` handler pattern for users
    - Call `require_user_type(event, ["superadmin"])`, validate entity exists and is pending
    - Update `approval_status` to `Approved`, set audit fields
    - _Requirements: 4.3, 4.7, 4.8, 4.9_

  - [x] 4.2 Create `lambdas/users/RejectUser/handler.py`
    - Mirror the `RejectDepartment` handler pattern for users
    - Validate rejection reason is non-empty
    - Update `approval_status` to `Rejected`, store `rejectionReason`, set audit fields
    - _Requirements: 4.6, 4.7, 4.8, 4.9_

  - [ ]* 4.3 Write property test for ApproveUser (Property 3)
    - **Property 3: Approving a pending entity transitions it to Approved**
    - Generate random pending users, verify approve transitions to `Approved`
    - **Validates: Requirements 4.3**

  - [ ]* 4.4 Write property test for RejectUser (Property 4)
    - **Property 4: Rejecting a pending entity transitions it to Rejected and stores the reason**
    - Generate random pending users and non-empty reason strings
    - **Validates: Requirements 4.6**


- [ ]* 5. Write cross-entity property tests for authorization and state guards
  - [ ]* 5.1 Write property test for admin users cannot approve/reject (Property 5)
    - **Property 5: Admin users cannot approve or reject entities**
    - Generate random entities × admin callers, verify authorization error and no state change
    - **Validates: Requirements 4.7**

  - [ ]* 5.2 Write property test for non-pending entities cannot be approved/rejected (Property 6)
    - **Property 6: Non-pending entities cannot be approved or rejected**
    - Generate random approved/rejected entities × superadmin callers, verify error and no state change
    - **Validates: Requirements 4.8**

  - [ ]* 5.3 Write property test for audit fields on approve/reject (Property 7)
    - **Property 7: Approval and rejection actions record audit fields**
    - Generate random pending entities × superadmin callers, verify `updatedBy` and `updatedAt` are set correctly
    - **Validates: Requirements 4.9**

- [x] 6. Modify CreateDepartment and CreatePosition Lambdas for admin access and approval status
  - [x] 6.1 Update `lambdas/departments/CreateDepartment/handler.py`
    - Change `require_user_type` from `["superadmin"]` to `["superadmin", "admin"]`
    - Determine caller's userType from event context
    - Set `approval_status` to `Approved` for superadmin, `Pending_Approval` for admin
    - Set `rejectionReason` to empty string
    - _Requirements: 2.1, 2.5, 2.9, 3.1_

  - [x] 6.2 Update `lambdas/positions/CreatePosition/handler.py`
    - Change `require_user_type` from `["superadmin"]` to `["superadmin", "admin"]`
    - Determine caller's userType from event context
    - Set `approval_status` to `Approved` for superadmin, `Pending_Approval` for admin
    - Set `rejectionReason` to empty string
    - _Requirements: 2.2, 2.6, 2.9, 3.2_

  - [x] 6.3 Update `lambdas/users/CreateUser/handler.py`
    - Add `approval_status` assignment based on caller's userType (superadmin → `Approved`, admin → `Pending_Approval`)
    - Set `rejectionReason` to empty string
    - _Requirements: 2.4, 2.8, 2.9_

  - [ ]* 6.4 Write property test for creation approval status (Property 1)
    - **Property 1: Creation approval status is determined by creator's userType**
    - Generate random entity inputs × {admin, superadmin} callers, verify correct approval_status
    - **Validates: Requirements 2.1, 2.2, 2.4, 2.5, 2.6, 2.8**

  - [ ]* 6.5 Write property test for regular user creation rejection (Property 2)
    - **Property 2: Regular users cannot create Departments or Positions**
    - Generate random dept/position inputs × user callers, verify authorization error
    - **Validates: Requirements 3.5**

- [x] 7. Modify Update and Delete Lambdas to protect approved entities
  - [x] 7.1 Add approved-entity guard to `lambdas/departments/UpdateDepartment/handler.py`
    - After fetching the existing record, check if `approval_status == "Approved"`
    - If approved, raise `ValueError("Cannot update department: approved entities cannot be edited")`
    - Allow updates for `Pending_Approval` and `Rejected` entities
    - _Requirements: 5.1, 5.6_

  - [x] 7.2 Add approved-entity guard to `lambdas/positions/UpdatePosition/handler.py`
    - Same pattern as 7.1 for positions
    - _Requirements: 5.2, 5.6_

  - [x] 7.3 Add approved-entity guard to `lambdas/projects/UpdateProject/handler.py`
    - Same pattern as 7.1 for projects
    - _Requirements: 5.3, 5.6_

  - [x] 7.4 Add approved-entity guard to `lambdas/users/UpdateUser/handler.py`
    - Same pattern as 7.1 for users
    - _Requirements: 5.4, 5.6_

  - [x] 7.5 Add approved-entity guard to `lambdas/departments/DeleteDepartment/handler.py`
    - After fetching the existing record, check if `approval_status == "Approved"`
    - If approved, raise `ValueError("Cannot delete department: approved entities cannot be deleted")`
    - _Requirements: 5.5_

  - [x] 7.6 Add approved-entity guard to `lambdas/positions/DeletePosition/handler.py`
    - Same pattern as 7.5 for positions
    - _Requirements: 5.5_

  - [x] 7.7 Add approved-entity guard to `lambdas/users/DeleteUser/handler.py`
    - Same pattern as 7.5 for users
    - _Requirements: 5.5_

  - [ ]* 7.8 Write property test for approved entity protection (Property 8)
    - **Property 8: Approved entities are protected from update and delete**
    - Generate random approved entities × any caller × any input, verify error and no change
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5**

  - [ ]* 7.9 Write property test for non-approved entity mutability (Property 9)
    - **Property 9: Non-approved entities allow update and delete**
    - Generate random pending/rejected entities × admin/superadmin callers, verify no approval-related error
    - **Validates: Requirements 5.6**

- [x] 8. Update CDK stack to wire new Lambda resolvers
  - [x] 8.1 Add ApproveDepartment and RejectDepartment Lambda functions and AppSync resolvers in `colabs_pipeline_cdk/stack/lambda_stack.py`
    - Add Lambda function definitions for both handlers
    - Grant DynamoDB read/write access to the Departments table
    - Create AppSync resolver mappings for the new mutations
    - Follow the existing ApproveProject/RejectProject CDK pattern
    - _Requirements: 8.1, 8.2_

  - [x] 8.2 Add ApprovePosition and RejectPosition Lambda functions and AppSync resolvers in `colabs_pipeline_cdk/stack/lambda_stack.py`
    - Same pattern as 8.1 for positions
    - _Requirements: 8.3, 8.4_

  - [x] 8.3 Add ApproveUser and RejectUser Lambda functions and AppSync resolvers in `colabs_pipeline_cdk/stack/lambda_stack.py`
    - Same pattern as 8.1 for users
    - _Requirements: 8.5, 8.6_

- [x] 9. Create data migration script for existing records
  - [x] 9.1 Create `scripts/migrate_approval_status.py`
    - Scan Departments, Positions, and Users tables
    - For records missing `approval_status`, set `approval_status = "Approved"` and `rejectionReason = ""`
    - Log the number of records updated per table
    - _Requirements: 1.1_

- [x] 10. Checkpoint - Ensure all backend tests pass
  - Ensure all tests pass, run `cdk synth` to validate CDK changes, ask the user if questions arise.


- [x] 11. Update GraphQLQueries.php with new mutations and query fields
  - [x] 11.1 Add six new mutation constants to `frontend/app/GraphQL/GraphQLQueries.php`
    - `APPROVE_DEPARTMENT`, `REJECT_DEPARTMENT`
    - `APPROVE_POSITION`, `REJECT_POSITION`
    - `APPROVE_USER`, `REJECT_USER`
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

  - [x] 11.2 Update `LIST_DEPARTMENTS`, `LIST_POSITIONS`, and `LIST_USERS_FULL` query constants to include `approval_status` and `rejectionReason` fields
    - _Requirements: 1.1, 1.2_

- [x] 12. Add approve/reject controller methods and routes
  - [x] 12.1 Add `approve` and `reject` methods to `DepartmentController`
    - `approve` calls `APPROVE_DEPARTMENT` mutation via GraphQL
    - `reject` calls `REJECT_DEPARTMENT` mutation with reason parameter
    - Return JSON response with success/error
    - _Requirements: 4.1, 4.4_

  - [x] 12.2 Add `approve` and `reject` methods to `PositionController`
    - Same pattern as 12.1 for positions
    - _Requirements: 4.2, 4.5_

  - [x] 12.3 Add `approve` and `reject` methods to `UserManagementController`
    - Same pattern as 12.1 for users
    - _Requirements: 4.3, 4.6_

  - [x] 12.4 Add POST routes for approve/reject actions in `routes/web.php`
    - `POST /admin/departments/{id}/approve` → `DepartmentController@approve`
    - `POST /admin/departments/{id}/reject` → `DepartmentController@reject`
    - `POST /admin/positions/{id}/approve` → `PositionController@approve`
    - `POST /admin/positions/{id}/reject` → `PositionController@reject`
    - `POST /admin/users/{id}/approve` → `UserManagementController@approve`
    - `POST /admin/users/{id}/reject` → `UserManagementController@reject`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

- [x] 13. Update Blade templates with approval status badges and conditional actions
  - [x] 13.1 Update `departments.blade.php`
    - Add approval status badge column with color coding (green/yellow/red)
    - Conditionally hide edit/delete icons when `approval_status == "Approved"`
    - Show approve/reject buttons for superadmin on `Pending_Approval` entities
    - Hide approve/reject buttons for admin users
    - Add rejection reason modal dialog
    - Add approval status filter dropdown (All, Pending_Approval, Approved, Rejected) defaulting to "All"
    - Implement client-side JavaScript filter logic
    - Add "Add Department" button visibility for admin users
    - _Requirements: 1.3, 3.3, 6.1, 6.4, 6.5, 6.6, 6.7, 6.8, 7.1, 7.4, 7.5, 7.6_

  - [x] 13.2 Update `positions.blade.php`
    - Same approval status badge, conditional actions, filter, and modal pattern as 13.1
    - Add "Add Position" button visibility for admin users
    - _Requirements: 1.4, 3.4, 6.2, 6.4, 6.5, 6.6, 6.7, 6.8, 7.2, 7.4, 7.5, 7.6_

  - [x] 13.3 Update `user-management.blade.php`
    - Same approval status badge, conditional actions, filter, and modal pattern as 13.1
    - _Requirements: 1.5, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 7.3, 7.4, 7.5, 7.6_

  - [x] 13.4 Update `projects.blade.php`
    - Conditionally hide edit/delete icons when `approval_status == "Approved"`
    - Ensure existing approve/reject buttons remain for superadmin on pending projects
    - _Requirements: 6.4, 6.5_

  - [ ]* 13.5 Write property test for approval status filter logic (Property 10)
    - **Property 10: Approval status filter returns only matching entities**
    - Generate random entity lists with mixed statuses × filter values, verify correct filtering
    - Extract filter logic into a testable JavaScript utility or Python equivalent
    - **Validates: Requirements 7.4, 7.5**

- [x] 14. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, verify frontend renders correctly, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Backend tasks (1–9) are implemented first, then frontend tasks (11–13)
- Checkpoints at task 10 (backend) and task 14 (frontend) ensure incremental validation
- The existing Project approval flow (ApproveProject/RejectProject) is the reference implementation for all new handlers
- Property tests use Python Hypothesis library targeting Lambda business logic with mocked DynamoDB
- Existing records without `approval_status` are handled by the migration script (task 9) and default-at-read-time logic
