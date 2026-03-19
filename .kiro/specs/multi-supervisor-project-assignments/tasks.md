# Implementation Plan: Multi-Supervisor Project Assignments

## Overview

Replace the single `supervisorId` field on the Users table with a many-to-many relationship via a new `Timesheet_ProjectAssignments` DynamoDB table. Implement CRUD Lambda resolvers, update all dependent components (TC Summary, ListPendingTimesheets, Notifications, Stream handler) to query the new table, and add a shared utility for supervisor lookups. Infrastructure changes include CDK stack updates, environment config, and GraphQL schema additions.

## Tasks

- [ ] 1. CDK infrastructure and environment config
  - [ ] 1.1 Add `project_assignments` entry to `TIMESHEET_TABLE_NAMES` in `colabs_pipeline_cdk/environment.py`
    - Add `"project_assignments": "Timesheet_ProjectAssignments"` to the dictionary
    - _Requirements: 8.4_

  - [ ] 1.2 Create ProjectAssignments DynamoDB table in `colabs_pipeline_cdk/stack/dynamodb_stack.py`
    - Add `project_assignments_table` with partition key `assignmentId` (String)
    - Add GSI `employeeId-index` with partition key `employeeId` (String)
    - Add GSI `supervisorId-index` with partition key `supervisorId` (String)
    - Add GSI `projectId-index` with partition key `projectId` (String)
    - Use PAY_PER_REQUEST billing mode
    - Table name pattern: `Timesheet_ProjectAssignments-{env}`
    - Export table name and ARN to SSM under `/timesheet/{env}/dynamodb/project_assignments/`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 8.1_

  - [ ]* 1.3 Write unit tests for CDK infrastructure
    - Verify synthesized CloudFormation contains ProjectAssignments table with correct partition key, GSIs, billing mode, and SSM exports
    - _Requirements: 1.2, 1.3, 1.4, 1.5, 1.6, 8.1_

- [ ] 2. GraphQL schema updates
  - [ ] 2.1 Add ProjectAssignment type, inputs, query, and mutations to `graphql/schema.graphql`
    - Add `ProjectAssignment` type with `assignmentId`, `employeeId`, `projectId`, `supervisorId`, `createdAt`, `createdBy`, `updatedAt`, `updatedBy`
    - Add `CreateProjectAssignmentInput`, `UpdateProjectAssignmentInput`, `ProjectAssignmentFilterInput` input types
    - Add `listProjectAssignments(filter: ProjectAssignmentFilterInput): [ProjectAssignment!]!` to Query type
    - Add `createProjectAssignment`, `updateProjectAssignment`, `deleteProjectAssignment` mutations
    - Verify existing `supervisorId` field on `User`, `CreateUserInput`, `UpdateUserInput` remains as optional
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 7.3_

- [ ] 3. Checkpoint - Ensure CDK synth passes
  - Ensure `cdk synth` succeeds with the new table definition, ask the user if questions arise.

- [ ] 4. Shared utility for supervisor employee lookups
  - [ ] 4.1 Create `lambdas/shared/project_assignments.py` with `get_supervised_employee_ids()` function
    - Accept `project_assignments_table_name` and `supervisor_id` parameters
    - Query `supervisorId-index` GSI on ProjectAssignments table
    - Handle pagination with `LastEvaluatedKey`
    - Return deduplicated list of `employeeId` strings
    - _Requirements: 3.1, 3.3, 4.1, 4.3, 5.1_

  - [ ]* 4.2 Write property test for `get_supervised_employee_ids()`
    - **Property 8: Supervised employee lookup returns correct unique set**
    - **Validates: Requirements 3.1, 3.3, 4.1, 4.3, 5.1**

- [ ] 5. Implement CreateProjectAssignment Lambda
  - [ ] 5.1 Create `lambdas/project_assignments/__init__.py` and `lambdas/project_assignments/CreateProjectAssignment/__init__.py`
    - _Requirements: 2.1_

  - [ ] 5.2 Create `lambdas/project_assignments/CreateProjectAssignment/handler.py`
    - Implement `handler(event, context)` as AppSync resolver
    - Use `require_user_type(event, ["superadmin", "admin"])` for authorization
    - Validate `employeeId` exists in Users table
    - Validate `projectId` exists in Projects table
    - Validate `supervisorId` exists in Users table
    - Check for duplicate `employeeId + projectId` via `employeeId-index` query
    - Generate UUID `assignmentId`, set `createdAt`/`createdBy`
    - Put item to ProjectAssignments table
    - Return created `ProjectAssignment`
    - Env vars: `PROJECT_ASSIGNMENTS_TABLE`, `USERS_TABLE`, `PROJECTS_TABLE`
    - _Requirements: 2.1, 2.5, 2.6, 2.7_

  - [ ]* 5.3 Write property test for create assignment round-trip
    - **Property 1: Create assignment round-trip**
    - **Validates: Requirements 1.1, 2.1**

  - [ ]* 5.4 Write property test for duplicate rejection
    - **Property 5: Duplicate employeeId+projectId rejected**
    - **Validates: Requirements 2.5**

  - [ ]* 5.5 Write property test for non-existent ID rejection
    - **Property 6: Non-existent referenced IDs rejected**
    - **Validates: Requirements 2.6**

  - [ ]* 5.6 Write property test for non-admin rejection
    - **Property 7: Non-admin users rejected from mutations**
    - **Validates: Requirements 2.7**

- [ ] 6. Implement UpdateProjectAssignment Lambda
  - [ ] 6.1 Create `lambdas/project_assignments/UpdateProjectAssignment/__init__.py`
    - _Requirements: 2.2_

  - [ ] 6.2 Create `lambdas/project_assignments/UpdateProjectAssignment/handler.py`
    - Implement `handler(event, context)` as AppSync resolver
    - Use `require_user_type(event, ["superadmin", "admin"])` for authorization
    - Get existing assignment by `assignmentId`, return error if not found
    - Validate any referenced `supervisorId`/`projectId` exist
    - If `projectId` changing, check for duplicate `employeeId + projectId`
    - Update item with `updatedAt`/`updatedBy`
    - Return updated `ProjectAssignment`
    - Env vars: `PROJECT_ASSIGNMENTS_TABLE`, `USERS_TABLE`, `PROJECTS_TABLE`
    - _Requirements: 2.2, 2.5, 2.6, 2.7_

  - [ ]* 6.3 Write property test for update preserves unchanged fields
    - **Property 2: Update preserves unchanged fields**
    - **Validates: Requirements 2.2**

- [ ] 7. Implement DeleteProjectAssignment Lambda
  - [ ] 7.1 Create `lambdas/project_assignments/DeleteProjectAssignment/__init__.py`
    - _Requirements: 2.3_

  - [ ] 7.2 Create `lambdas/project_assignments/DeleteProjectAssignment/handler.py`
    - Implement `handler(event, context)` as AppSync resolver
    - Use `require_user_type(event, ["superadmin", "admin"])` for authorization
    - Delete item from ProjectAssignments table by `assignmentId`
    - Return `True` on success
    - Env vars: `PROJECT_ASSIGNMENTS_TABLE`
    - _Requirements: 2.3, 2.7_

  - [ ]* 7.3 Write property test for delete removes assignment
    - **Property 3: Delete removes assignment**
    - **Validates: Requirements 2.3**

- [ ] 8. Implement ListProjectAssignments Lambda
  - [ ] 8.1 Create `lambdas/project_assignments/ListProjectAssignments/__init__.py`
    - _Requirements: 2.4_

  - [ ] 8.2 Create `lambdas/project_assignments/ListProjectAssignments/handler.py`
    - Implement `handler(event, context)` as AppSync resolver
    - Any authenticated user can access (read-only)
    - If `employeeId` filter → query `employeeId-index`
    - If `supervisorId` filter → query `supervisorId-index`
    - If `projectId` filter → query `projectId-index`
    - If no filter → scan
    - Handle pagination with `LastEvaluatedKey`
    - Return list of `ProjectAssignment` records
    - Env vars: `PROJECT_ASSIGNMENTS_TABLE`
    - _Requirements: 2.4_

  - [ ]* 8.3 Write property test for filter returns only matching records
    - **Property 4: Filter returns only matching records**
    - **Validates: Requirements 2.4**

- [ ] 9. Wire CRUD Lambdas in CDK Lambda stack
  - [ ] 9.1 Update `colabs_pipeline_cdk/stack/lambda_stack.py` to import ProjectAssignments table
    - Import table reference in `_import_resources()` using SSM parameter
    - _Requirements: 8.2, 8.3_

  - [ ] 9.2 Create 4 new Lambda functions for CRUD operations in `_create_project_assignment_lambdas()`
    - CreateProjectAssignment, UpdateProjectAssignment, DeleteProjectAssignment, ListProjectAssignments
    - Pass `PROJECT_ASSIGNMENTS_TABLE`, `USERS_TABLE`, `PROJECTS_TABLE` env vars
    - Grant read/write on ProjectAssignments table to all CRUD Lambdas
    - Grant read on Users and Projects tables to Create/Update Lambdas
    - Create AppSync data sources and resolvers for each
    - _Requirements: 8.2, 8.3_

- [ ] 10. Checkpoint - Ensure CRUD Lambdas work
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 11. Update Reports handler to use ProjectAssignments
  - [ ] 11.1 Modify `lambdas/reports/handler.py` — replace `_get_supervised_employees()` to use shared utility
    - Import `get_supervised_employee_ids` from `shared.project_assignments`
    - Replace `supervisorId-index` query on Users table with `get_supervised_employee_ids()` call
    - After getting employee IDs, batch-get user details from Users table for names/emails
    - Deduplicate employee IDs (handled by shared utility)
    - Use `PROJECT_ASSIGNMENTS_TABLE` env var
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [ ] 11.2 Modify `lambdas/reports/handler.py` — replace `_get_employee_supervisor_id()` with `_get_employee_supervisors()`
    - Query `employeeId-index` on ProjectAssignments table to find all supervisors for the submitting employee
    - Return list of distinct `supervisorId` values
    - Loop over distinct supervisors to generate TC Summary for each
    - Use `PROJECT_ASSIGNMENTS_TABLE` env var
    - _Requirements: 6.1, 6.2, 6.3_

  - [ ]* 11.3 Write property test for stream handler supervisor fan-out
    - **Property 9: Stream handler generates report per distinct supervisor**
    - **Validates: Requirements 6.1, 6.2**

  - [ ]* 11.4 Write unit tests for reports handler changes
    - Test empty assignments returns empty report
    - Test employee with multiple assignments to same supervisor is deduplicated
    - Test stream trigger generates reports for each distinct supervisor
    - _Requirements: 3.1, 3.3, 3.4, 6.1, 6.2_

- [ ] 12. Update ListPendingTimesheets to use ProjectAssignments
  - [ ] 12.1 Modify `lambdas/reviews/ListPendingTimesheets/handler.py`
    - Import `get_supervised_employee_ids` from `shared.project_assignments`
    - Replace `_get_supervised_employee_ids()` to use shared utility instead of Users table `supervisorId-index`
    - Deduplicate employee IDs (handled by shared utility)
    - Use `PROJECT_ASSIGNMENTS_TABLE` env var
    - _Requirements: 4.1, 4.2, 4.3_

  - [ ]* 12.2 Write unit tests for ListPendingTimesheets changes
    - Test supervisor with no assignments returns empty list
    - Test employee appearing in multiple assignments is included only once
    - _Requirements: 4.1, 4.3_

- [ ] 13. Update Notification Service to use ProjectAssignments
  - [ ] 13.1 Modify `lambdas/notifications/handler.py`
    - Import `get_supervised_employee_ids` from `shared.project_assignments`
    - Replace `_get_supervised_employees()` to use shared utility instead of Users table `supervisorId-index`
    - After getting employee IDs, batch-get user details from Users table for names/emails
    - Skip sending TC Summary email when tech lead has no project assignments
    - Use `PROJECT_ASSIGNMENTS_TABLE` env var
    - _Requirements: 5.1, 5.2, 5.3_

  - [ ]* 13.2 Write unit tests for Notification Service changes
    - Test tech lead with no assignments skips email
    - Test supervised employees are correctly resolved from ProjectAssignments
    - _Requirements: 5.1, 5.3_

- [ ] 14. Update CDK Lambda stack for modified Lambdas
  - [ ] 14.1 Add `PROJECT_ASSIGNMENTS_TABLE` env var and read permissions to existing Lambdas
    - Add env var and read permissions to: reports stream handler, GetTCSummaryReport, GetProjectSummaryReport, ListPendingTimesheets, notification service
    - _Requirements: 8.2, 8.3_

- [ ] 15. Checkpoint - Ensure all modified Lambdas work
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 16. Backward compatibility verification
  - [ ] 16.1 Verify `supervisorId` field remains on User type and input types in GraphQL schema
    - Confirm `supervisorId` is optional on `User`, `CreateUserInput`, `UpdateUserInput`
    - Confirm `createUser` and `updateUser` mutations continue to accept `supervisorId` without error
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [ ]* 16.2 Write property test for backward compatibility
    - **Property 10: Backward compatibility — supervisorId accepted on user mutations**
    - **Validates: Requirements 7.4**

- [ ] 17. Final checkpoint - Ensure all tests pass
  - Run full test suite with `pytest`
  - Ensure all property tests and unit tests pass
  - Ensure no regressions in existing tests
  - Ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- The shared utility `get_supervised_employee_ids()` centralizes the supervisor lookup logic to avoid duplication across reports, reviews, and notifications
- Deploy order: DynamoDB stack first, then Lambda stack (to ensure table exists before Lambda references it)
- Python is the implementation language (matching existing Lambda handlers and CDK stack)
