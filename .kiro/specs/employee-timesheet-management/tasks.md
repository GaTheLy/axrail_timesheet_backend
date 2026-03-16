# Implementation Plan: Employee Timesheet Management System

## Overview

Implement a serverless Employee Timesheet Management System on AWS using CDK (Python) for infrastructure, Python Lambda resolvers for business logic, AppSync GraphQL API, DynamoDB for persistence, and a Vite SPA frontend served via CloudFront/S3. The implementation follows the existing COLABS pipeline patterns and builds incrementally from foundational infrastructure through core business logic to reporting and automation.

## Tasks

- [x] 1. Set up CDK stack structure and shared infrastructure
  - [x] 1.1 Create the CDK stack file `colabs_pipeline_cdk/timesheet_stack.py` with base stack class
    - Define the stack class inheriting from `aws_cdk.Stack`
    - Accept environment config from `environment.py`
    - Add environment-specific constants for the timesheet system to `environment.py`
    - _Requirements: 1.1, 1.3_

  - [x] 1.2 Define all DynamoDB tables with GSIs
    - Create Users table with `userId` PK and GSIs: `email-index`, `departmentId-index`, `supervisorId-index`
    - Create Departments table with `departmentId` PK and GSI: `departmentName-index`
    - Create Positions table with `positionId` PK and GSI: `positionName-index`
    - Create Projects table with `projectId` PK and GSIs: `projectCode-index`, `approval_status-index`, `projectManagerId-index`
    - Create Timesheet_Periods table with `periodId` PK and GSI: `startDate-index`
    - Create Timesheet_Submissions table with `submissionId` PK, GSIs: `employeeId-periodId-index`, `periodId-status-index`, `status-index`, and enable DynamoDB Streams (NEW_AND_OLD_IMAGES)
    - Create Timesheet_Entries table with `entryId` PK and GSIs: `submissionId-index`, `projectCode-index`
    - Create Employee_Performance table with `userId` PK and `year` SK
    - Create Report_Distribution_Config table with `configId` PK
    - Create Main_Database table with `recordId` PK
    - _Requirements: 2.1, 2.4, 3.1, 3.2, 4.1, 5.1, 6.1, 9.1, 10.1, 11.1, 12.5, 14.1_

  - [x] 1.3 Set up Cognito User Pool with custom attributes and groups
    - Create User Pool with custom attributes: `custom:userType`, `custom:role`, `custom:departmentId`, `custom:positionId`
    - Create Cognito groups: `superadmin`, `admin`, `user`
    - Configure password policy and session settings
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [x] 1.4 Create S3 bucket for report storage and CSV uploads
    - Create bucket with lifecycle rules and structured key prefix `reports/{type}/{period}/{timestamp}.csv`
    - Configure CORS for pre-signed URL downloads
    - _Requirements: 9.6, 10.5, 14.3_

  - [x] 1.5 Create AppSync GraphQL API with Cognito authorization
    - Define AppSync API resource with Cognito User Pool as primary auth
    - Create the GraphQL schema file with all types, inputs, queries, and mutations from the design
    - _Requirements: 1.1, 1.3, 1.5_

- [x] 2. Checkpoint - Ensure CDK synth succeeds
  - Run `cdk synth` to validate all infrastructure definitions compile correctly. Ask the user if questions arise.

- [x] 3. Implement Authentication & Authorization Lambda layer
  - [x] 3.1 Create shared utility module `lambdas/shared/auth.py`
    - Implement `get_caller_identity(event)` to extract userId, userType, role from AppSync event context
    - Implement `require_role(event, allowed_roles)` decorator/helper that raises forbidden error if caller lacks required role
    - Implement `require_user_type(event, allowed_types)` helper for userType checks
    - _Requirements: 1.3, 1.5_

  - [ ]* 3.2 Write unit tests for auth utilities
    - Test `get_caller_identity` extracts claims correctly from AppSync event
    - Test `require_role` raises forbidden for unauthorized roles
    - Test `require_user_type` raises forbidden for unauthorized user types
    - _Requirements: 1.3, 1.5_

- [x] 4. Implement User Management resolvers
  - [x] 4.1 Create `lambdas/users/handler.py` with CRUD operations
    - Implement `create_user` resolver: validate caller permissions (Superadmin creates admin/user, Admin creates user only), validate email uniqueness via `email-index` GSI, validate role and userType enums, write to Users table and create Cognito user
    - Implement `update_user` resolver: validate caller permissions, persist changes with `updatedBy`/`updatedAt`
    - Implement `delete_user` resolver: validate caller permissions, remove from Users table and Cognito
    - Implement `get_user` and `list_users` resolvers with filtering support
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10_

  - [ ]* 4.2 Write unit tests for User Management resolvers
    - Test Superadmin can create admin and user accounts
    - Test Admin can only create user accounts, forbidden for admin/superadmin creation
    - Test email uniqueness enforcement
    - Test role and userType validation
    - _Requirements: 2.7, 2.8, 2.9, 2.10_

  - [x] 4.3 Wire User Management Lambda to AppSync resolvers in CDK
    - Create Lambda function resource with DynamoDB and Cognito permissions
    - Attach Lambda data source to AppSync API
    - Create resolver mappings for createUser, updateUser, deleteUser, getUser, listUsers
    - _Requirements: 2.1, 2.4_

- [x] 5. Implement Department & Position Management resolvers
  - [x] 5.1 Create `lambdas/departments/handler.py` with CRUD operations
    - Implement `create_department`, `update_department`, `delete_department`, `list_departments`
    - Enforce unique department names via `departmentName-index` GSI
    - Reject deletion if department has associated users (query `departmentId-index` on Users table)
    - Enforce Superadmin-only access for all mutations
    - _Requirements: 3.1, 3.3, 3.5, 3.6_

  - [x] 5.2 Create `lambdas/positions/handler.py` with CRUD operations
    - Implement `create_position`, `update_position`, `delete_position`, `list_positions`
    - Enforce unique position names via `positionName-index` GSI
    - Enforce Superadmin-only access for all mutations
    - _Requirements: 3.2, 3.4, 3.6_

  - [ ]* 5.3 Write unit tests for Department & Position resolvers
    - Test unique name enforcement for departments and positions
    - Test deletion rejection when associations exist
    - Test Superadmin-only authorization
    - _Requirements: 3.3, 3.4, 3.5, 3.6_

  - [x] 5.4 Wire Department & Position Lambdas to AppSync in CDK
    - Create Lambda functions with DynamoDB permissions
    - Attach data sources and resolver mappings
    - _Requirements: 3.1, 3.2_

- [x] 6. Implement Project Management resolvers
  - [x] 6.1 Create `lambdas/projects/handler.py` with CRUD and approval operations
    - Implement `create_project`: Superadmin creates with `approval_status=Approved`, Admin creates with `approval_status=Pending_Approval`
    - Implement `approve_project` and `reject_project` (Superadmin only): validate current status is `Pending_Approval`, update accordingly, record rejection reason
    - Implement `update_project` and `list_projects` with filtering by approval_status
    - Enforce unique `projectCode` via `projectCode-index` GSI
    - Validate `plannedHours` is a positive float
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.6, 4.7, 4.8, 4.9_

  - [ ]* 6.2 Write unit tests for Project Management resolvers
    - Test Superadmin creates with Approved status directly
    - Test Admin creates with Pending_Approval status
    - Test approval/rejection state transitions
    - Test projectCode uniqueness enforcement
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.6_

  - [x] 6.3 Wire Project Management Lambda to AppSync in CDK
    - Create Lambda function with DynamoDB permissions
    - Attach data source and resolver mappings for all project operations
    - _Requirements: 4.1, 4.2_

- [x] 7. Checkpoint - Ensure all tests pass for core entity management
  - Run `pytest` to validate all unit tests pass. Ensure `cdk synth` still succeeds. Ask the user if questions arise.

- [x] 8. Implement Timesheet Period Management resolvers
  - [x] 8.1 Create `lambdas/periods/handler.py` with period operations
    - Implement `create_timesheet_period`: validate startDate is Saturday, endDate is Friday, endDate = startDate + 6 days, submissionDeadline >= endDate, no overlapping periods (query `startDate-index`)
    - Implement `update_timesheet_period` and `list_timesheet_periods` with filtering
    - Implement `get_current_period`: return period where current date falls between startDate and endDate
    - Enforce Superadmin-only access for mutations
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [ ]* 8.2 Write property test for period date validation
    - **Property 1: Period date constraints**
    - For any valid period, startDate is always Saturday, endDate is always Friday, and endDate == startDate + 6 days
    - **Validates: Requirements 5.2, 5.3**

  - [ ]* 8.3 Write unit tests for Timesheet Period resolvers
    - Test Saturday/Friday validation rejects invalid days
    - Test overlap detection rejects conflicting periods
    - Test submissionDeadline >= endDate enforcement
    - _Requirements: 5.2, 5.3, 5.4, 5.5_

  - [x] 8.4 Wire Timesheet Period Lambda to AppSync in CDK
    - Create Lambda function with DynamoDB permissions
    - Attach data source and resolver mappings
    - _Requirements: 5.1_

- [x] 9. Implement Timesheet Submission & Entry resolvers
  - [x] 9.1 Create `lambdas/submissions/handler.py` with submission operations
    - Implement `create_timesheet_submission`: create with `status=Draft`, enforce one submission per employee per period via `employeeId-periodId-index` GSI
    - Implement `submit_timesheet`: validate status is Draft, transition to Submitted, record updatedAt
    - Implement `get_timesheet_submission` and `list_my_submissions`: filter by caller's employeeId, reject access to other employees' data
    - _Requirements: 6.1, 6.4, 6.6, 6.9, 6.10, 6.11_

  - [x] 9.2 Create `lambdas/entries/handler.py` with entry operations
    - Implement `add_timesheet_entry`: validate submission status is Draft or Rejected, validate projectCode references Approved project, validate max 27 entries per submission, validate daily hours (non-negative float, max 2 decimal places), compute and store row total
    - Implement `update_timesheet_entry`: same validations as add, validate submission status allows edits
    - Implement `remove_timesheet_entry`: validate submission status allows edits
    - Validate total daily hours across all entries does not exceed 24.0
    - _Requirements: 6.2, 6.3, 6.5, 6.7, 6.8, 15.1, 15.2, 15.3, 15.4, 15.5_

  - [ ]* 9.3 Write property test for timesheet entry validation
    - **Property 2: Daily hours constraint**
    - For any set of entries in a submission, the sum of hours for any single day across all entries never exceeds 24.0
    - **Validates: Requirements 15.2**

  - [ ]* 9.4 Write property test for row total computation
    - **Property 3: Row total equals sum of daily values**
    - For any timesheet entry, totalHours == saturday + sunday + monday + tuesday + wednesday + thursday + friday
    - **Validates: Requirements 6.8, 15.5**

  - [ ]* 9.5 Write unit tests for Submission & Entry resolvers
    - Test one-submission-per-period enforcement
    - Test status transition Draft to Submitted
    - Test entry editing blocked when status is Submitted or Locked
    - Test max 27 entries enforcement
    - Test employee can only see own submissions
    - _Requirements: 6.4, 6.5, 6.6, 6.7, 6.9, 6.10, 6.11_

  - [x] 9.6 Wire Submission & Entry Lambdas to AppSync in CDK
    - Create Lambda functions with DynamoDB permissions
    - Attach data sources and resolver mappings for all submission and entry operations
    - _Requirements: 6.1, 6.2_

- [x] 10. Implement Timesheet Review & Approval resolvers
  - [x] 10.1 Create `lambdas/reviews/handler.py` with review operations
    - Implement `approve_timesheet`: validate caller is Project_Manager or Tech_Lead, validate submission status is Submitted, transition to Approved, record approvedBy and approvedAt
    - Implement `reject_timesheet`: validate caller role, validate status is Submitted, transition to Rejected, record updatedBy and updatedAt
    - Implement `list_pending_timesheets`: query submissions with status Submitted for employees under reviewer's supervision (via `supervisorId-index` on Users table)
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [ ]* 10.2 Write property test for submission status transitions
    - **Property 4: Valid status transitions**
    - The only valid review transitions are Submitted to Approved and Submitted to Rejected. Any other source status must be rejected.
    - **Validates: Requirements 7.1, 7.2, 7.5**

  - [ ]* 10.3 Write unit tests for Review resolvers
    - Test approve transitions Submitted to Approved with approvedBy/approvedAt
    - Test reject transitions Submitted to Rejected
    - Test invalid transition from Draft/Locked/Approved is rejected
    - Test reviewer only sees supervised employees' submissions
    - _Requirements: 7.1, 7.2, 7.4, 7.5_

  - [x] 10.4 Wire Review Lambda to AppSync in CDK
    - Create Lambda function with DynamoDB permissions
    - Attach data source and resolver mappings
    - _Requirements: 7.1, 7.2_

- [x] 11. Checkpoint - Ensure all tests pass for core timesheet workflow
  - Run `pytest` to validate all unit tests pass. Ensure `cdk synth` still succeeds. Ask the user if questions arise.

- [x] 12. Implement Deadline Enforcement Lambda
  - [x] 12.1 Create `lambdas/deadline_enforcement/handler.py`
    - Query all periods where `submissionDeadline` has passed and `isLocked` is false
    - For each period: update all Draft submissions to Locked, update all Submitted submissions to Locked (query via `periodId-status-index`)
    - For employees with no submission for the period: create a Locked submission with zero hours
    - Mark period as `isLocked = true`
    - Log all locking actions
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [ ]* 12.2 Write unit tests for Deadline Enforcement Lambda
    - Test Draft submissions are locked after deadline
    - Test Submitted submissions are locked after deadline
    - Test missing submissions are created as Locked with zero hours
    - Test already Approved submissions are not modified
    - _Requirements: 8.1, 8.2, 8.4_

  - [x] 12.3 Create EventBridge rule and wire to Lambda in CDK
    - Create EventBridge scheduled rule (configurable cron)
    - Grant Lambda permissions to read/write DynamoDB tables (Timesheet_Periods, Timesheet_Submissions, Users)
    - _Requirements: 8.1_

- [x] 13. Implement Employee Performance Tracking
  - [x] 13.1 Create `lambdas/performance/handler.py`
    - Triggered alongside report generation when submission transitions to Approved
    - Look up or create Employee_Performance record for `(userId, year)`
    - Add approved chargeable hours to `ytdChargable_hours` and total hours to `ytdTotalHours`
    - Recalculate `ytdChargabilityPercentage = (ytdChargable_hours / ytdTotalHours) * 100`
    - _Requirements: 11.1, 11.2, 11.3, 11.4_

  - [ ]* 13.2 Write property test for chargeability calculation
    - **Property 5: Chargeability percentage consistency**
    - For any Employee_Performance record where ytdTotalHours > 0, ytdChargabilityPercentage == (ytdChargable_hours / ytdTotalHours) * 100
    - **Validates: Requirements 11.2**

  - [ ]* 13.3 Write unit tests for Performance Tracking
    - Test new record creation when none exists for employee/year
    - Test cumulative hour addition to existing record
    - Test chargeability percentage recalculation
    - _Requirements: 11.1, 11.2, 11.3_

- [x] 14. Implement Report Generator Lambda
  - [x] 14.1 Create `lambdas/reports/handler.py` for TC Summary and Project Summary
    - Implement DynamoDB Stream handler: trigger on Timesheet_Submissions status change to Approved or Locked
    - Implement TC Summary generation: per Tech_Lead per period, compute Name, Chargeable Hours, Total Hours, Current Period Chargeability, YTD Chargeability; include only Approved/Locked submissions; output CSV to S3
    - Implement Project Summary generation: per period, compute Project Charge Code, Project Name, Planned Hours, Charged Hours, Utilization, Current Biweekly Effort; include all projects; output CSV to S3
    - Implement `get_tc_summary_report` and `get_project_summary_report` resolvers returning pre-signed S3 URLs
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7_

  - [ ]* 14.2 Write property test for TC Summary chargeability
    - **Property 6: TC Summary chargeability calculation**
    - For any employee row in TC Summary, current period chargeability == (chargeable hours / total hours) * 100 when total hours > 0
    - **Validates: Requirements 9.3**

  - [ ]* 14.3 Write property test for Project Summary utilization
    - **Property 7: Project utilization calculation**
    - For any project row in Project Summary, utilization == (charged hours / planned hours) * 100 when planned hours > 0
    - **Validates: Requirements 10.3**

  - [ ]* 14.4 Write unit tests for Report Generator
    - Test TC Summary includes only Approved/Locked submissions
    - Test Project Summary includes all projects regardless of status
    - Test CSV output format matches expected columns
    - Test S3 storage with correct key prefix
    - _Requirements: 9.5, 9.6, 10.5, 10.6_

  - [x] 14.5 Wire Report Generator Lambda to DynamoDB Streams and AppSync in CDK
    - Create Lambda with DynamoDB Stream event source on Timesheet_Submissions table
    - Grant read access to all relevant DynamoDB tables and write access to S3 report bucket
    - Attach AppSync data source and resolver mappings for report download queries
    - _Requirements: 9.1, 10.1_

- [x] 15. Checkpoint - Ensure all tests pass for reporting and performance tracking
  - Run `pytest` to validate all unit tests pass. Ensure `cdk synth` still succeeds. Ask the user if questions arise.

- [x] 16. Implement Notification Service
  - [x] 16.1 Create `lambdas/notifications/handler.py`
    - Implement EventBridge-triggered handler: generate Project Summary CSV, attach and send via SES to configured recipient list
    - For each Tech_Lead: generate TC Summary CSV, attach and send via SES to that Tech_Lead's email
    - On failure: log recipient, report type, and error details
    - _Requirements: 12.1, 12.2, 12.3, 12.6_

  - [x] 16.2 Create `lambdas/notification_config/handler.py` for distribution config management
    - Implement `update_report_distribution_config` resolver: persist schedule_cron_expression, recipient_emails, enabled flag (Superadmin only)
    - Implement `get_report_distribution_config` resolver
    - _Requirements: 12.4, 12.5, 12.7_

  - [ ]* 16.3 Write unit tests for Notification Service
    - Test email sending with CSV attachment
    - Test failure logging on SES errors
    - Test config update persists correctly
    - _Requirements: 12.1, 12.3, 12.6_

  - [x] 16.4 Wire Notification Lambda and EventBridge rule in CDK
    - Create Lambda with SES, S3, and DynamoDB permissions
    - Create EventBridge rule with configurable cron schedule
    - Create Lambda for config management and wire to AppSync
    - _Requirements: 12.1, 12.4_

- [x] 17. Implement Archival Lambda
  - [x] 17.1 Create `lambdas/archival/handler.py`
    - Query all submissions for the ended biweekly period
    - Set `archived = true` on each submission, retain all entries and metadata
    - Ensure archived submissions are returned as read-only via API (add archived check to submission resolvers)
    - _Requirements: 13.1, 13.2, 13.3_

  - [ ]* 17.2 Write unit tests for Archival Lambda
    - Test submissions are marked as archived
    - Test entries and metadata are retained
    - Test archived submissions are read-only
    - _Requirements: 13.1, 13.2, 13.3_

  - [x] 17.3 Wire Archival Lambda and EventBridge rule in CDK
    - Create Lambda with DynamoDB permissions
    - Create EventBridge rule that triggers after report distribution completes
    - _Requirements: 13.4_

- [x] 18. Implement Main Database Management resolvers
  - [x] 18.1 Create `lambdas/main_database/handler.py`
    - Implement `list_main_database` resolver: return all records with type, chargeCode, projectName, budgetEffort, projectStatus
    - Implement `update_main_database_record` resolver: persist changes with updatedBy/updatedAt (Superadmin only)
    - Implement `bulk_import_csv` resolver: validate each row against schema (type, value, project_name, budget_effort, project_status), reject invalid rows with row number and error detail, persist valid rows
    - Implement `refresh_database` resolver: replace all existing records with imported data, log operation (Superadmin only)
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_

  - [ ]* 18.2 Write unit tests for Main Database Management
    - Test CSV row validation rejects invalid rows with error details
    - Test valid rows are persisted while invalid rows are skipped
    - Test refresh replaces all existing records
    - _Requirements: 14.3, 14.4, 14.5_

  - [x] 18.3 Wire Main Database Lambda to AppSync in CDK
    - Create Lambda with DynamoDB and S3 permissions
    - Attach data source and resolver mappings
    - _Requirements: 14.1_

- [x] 19. Checkpoint - Ensure all tests pass for all backend components
  - Run `pytest` to validate all unit tests pass. Ensure `cdk synth` still succeeds. Ask the user if questions arise.

- [x] 20. Integration and final wiring
  - [x] 20.1 Update submission and entry resolvers to enforce read-only on archived submissions
    - In `lambdas/submissions/handler.py`: reject edits/submissions on archived submissions
    - In `lambdas/entries/handler.py`: reject add/update/remove on entries belonging to archived submissions
    - _Requirements: 8.2, 8.3, 13.3_

  - [x] 20.2 Wire Performance Tracking Lambda to DynamoDB Streams in CDK
    - Ensure performance tracking triggers on submission status change to Approved (alongside report generation)
    - _Requirements: 11.1_

  - [x] 20.3 Update `app.py` to instantiate the timesheet stack
    - Import and instantiate the timesheet stack with environment config
    - Follow existing COLABS pipeline patterns for stack registration
    - _Requirements: 1.1_

- [x] 21. Final checkpoint - Ensure all tests pass and CDK synth succeeds
  - Run `pytest` and `cdk synth`. Verify all Lambda functions are wired, all DynamoDB tables have correct GSIs, all EventBridge rules are configured. Ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design
- All Lambda functions use Python 3.12+ runtime
- CDK infrastructure uses Python following existing COLABS patterns
- Frontend (Vite SPA) implementation is not included in this plan and should be a separate spec
