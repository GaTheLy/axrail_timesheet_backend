# Implementation Plan: Employee Timesheet Management System

## Overview

Implement a serverless Employee Timesheet Management System on AWS using CDK (Python) for infrastructure, Python Lambda resolvers for business logic, AppSync GraphQL API, DynamoDB for persistence. The system uses Monday–Friday weekly periods with only two statuses (Draft, Submitted), automatic submission at Friday 5PM MYT deadline, and no manual submit or approval/rejection flow.

## Tasks

- [x] 1. Set up CDK stack structure and shared infrastructure
  - [x] 1.1 Create CDK stacks (DynamoDB, Auth, Storage, Api, Lambda)
  - [x] 1.2 Define all DynamoDB tables with GSIs
  - [x] 1.3 Set up Cognito User Pool with custom attributes and groups
  - [x] 1.4 Create S3 bucket for report storage
  - [x] 1.5 Create AppSync GraphQL API with Cognito authorization

- [x] 2. Implement Authentication & Authorization Lambda layer
  - [x] 2.1 Create shared utility module `lambdas/shared/auth.py`
  - [x] 2.2 Write unit tests for auth utilities

- [x] 3. Implement User Management resolvers
  - [x] 3.1 Create `lambdas/users/` handlers (Create, Update, Delete, Get, List)
  - [x] 3.2 Write unit tests
  - [x] 3.3 Wire to AppSync in CDK

- [x] 4. Implement Department & Position Management resolvers
  - [x] 4.1 Create `lambdas/departments/` and `lambdas/positions/` handlers
  - [x] 4.2 Write unit tests
  - [x] 4.3 Wire to AppSync in CDK

- [x] 5. Implement Project Management resolvers
  - [x] 5.1 Create `lambdas/projects/` handlers
  - [x] 5.2 Write unit tests
  - [x] 5.3 Wire to AppSync in CDK

- [x] 6. Implement Timesheet Period Management resolvers
  - [x] 6.1 Create `lambdas/periods/` handlers (Create, Update, List, GetCurrent)
  - [x] 6.2 Create `lambdas/periods/shared_utils.py` with Mon-Fri validation and deadline auto-computation
  - [x] 6.3 Write property tests for period date validation (Mon start, Fri end, 4-day span)
  - [x] 6.4 Write unit tests
  - [x] 6.5 Wire to AppSync in CDK

- [x] 7. Implement Timesheet Submission & Entry resolvers
  - [x] 7.1 Create `lambdas/submissions/` handlers (CreateTimesheetSubmission, GetTimesheetSubmission, ListMySubmissions)
  - [x] 7.2 Create `lambdas/entries/` handlers (Add, Update, Remove) with shared_utils
  - [x] 7.3 EDITABLE_STATUSES = {"Draft"} only
  - [x] 7.4 Write property tests for daily hours and row total
  - [x] 7.5 Write unit tests
  - [x] 7.6 Wire to AppSync in CDK

- [x] 8. Implement Auto-Provisioning Lambda
  - [x] 8.1 Create `lambdas/auto_provisioning/handler.py`
  - [x] 8.2 Auto-creates weekly Mon-Fri period + Draft submissions for all employees
  - [x] 8.3 Wire EventBridge rule (Sunday 16:05 UTC = Monday 00:05 MYT)

- [x] 9. Implement Deadline Reminder Lambda
  - [x] 9.1 Create `lambdas/deadline_reminder/handler.py`
  - [x] 9.2 Sends reminder emails to employees with Draft submissions
  - [x] 9.3 Wire EventBridge rule (Friday 05:00 UTC = Friday 1PM MYT)

- [x] 10. Implement Deadline Enforcement Lambda
  - [x] 10.1 Create `lambdas/deadline_enforcement/handler.py`
  - [x] 10.2 Draft → Submitted auto-submit, create missing Submitted submissions
  - [x] 10.3 Send under-40h notification to employee only
  - [x] 10.4 Mark period as isLocked = true
  - [x] 10.5 Write unit tests
  - [x] 10.6 Wire EventBridge rule (Friday 09:05 UTC = Friday 5:05PM MYT)

- [x] 11. Implement Employee Performance Tracking
  - [x] 11.1 Create `lambdas/performance/handler.py` — triggers on Submitted status
  - [x] 11.2 Write unit tests

- [x] 12. Implement Report Generator Lambda
  - [x] 12.1 Create `lambdas/reports/handler.py` — triggers on Submitted status via DynamoDB Streams
  - [x] 12.2 TC Summary and Project Summary generation
  - [x] 12.3 Write unit tests

- [x] 13. Implement Notification Service
  - [x] 13.1 Create `lambdas/notifications/handler.py`
  - [x] 13.2 Create `lambdas/notification_config/` handlers
  - [x] 13.3 Write unit tests

- [x] 14. Implement Archival Lambda
  - [x] 14.1 Create `lambdas/archival/handler.py`
  - [x] 14.2 Write unit tests

- [x] 15. Implement Main Database Management resolvers
  - [x] 15.1 Create `lambdas/main_database/` handlers
  - [x] 15.2 Write unit tests

- [x] 16. Integration and final wiring
  - [x] 16.1 Update `app.py` to instantiate all stacks
  - [x] 16.2 Wire all Lambdas, EventBridge rules, and DynamoDB Streams in CDK

- [x] 17. Refactor: Remove approval/rejection flow
  - [x] 17.1 Remove review mutations from GraphQL schema
  - [x] 17.2 Remove Approved/Rejected/Locked statuses — only Draft and Submitted
  - [x] 17.3 Change periods from Sat-Fri to Mon-Fri (4-day span)
  - [x] 17.4 Auto-compute submissionDeadline (Friday 5PM MYT)
  - [x] 17.5 Remove manual submit — auto-submit only at deadline
  - [x] 17.6 Update deadline enforcement: Draft→Submitted (not Locked)
  - [x] 17.7 Add auto-provisioning Lambda (Monday period + Draft submissions)
  - [x] 17.8 Add deadline reminder Lambda (Friday 1PM MYT)
  - [x] 17.9 Update reports/performance to trigger on Submitted (not Approved)
  - [x] 17.10 Remove review Lambdas from CDK wiring
  - [x] 17.11 Update all test files for new flow
  - [x] 17.12 Delete dead test files (test_reviews.py, test_submission_status_transition_properties.py)
  - [x] 17.13 Update spec documents (requirements.md, design.md, tasks.md)
  - [x] 17.14 Update TIMESHEET_SYSTEM.md documentation

## Notes

- Only two submission statuses: Draft and Submitted
- Period runs Monday to Friday (not Saturday to Friday)
- No manual submit — auto-submit only at Friday 5PM MYT deadline
- No approval/rejection flow at all
- Under-40h notification goes to employee only (not supervisor)
- Period + submissions auto-created on Monday for all employees
- Deadline reminder sent 4 hours before deadline (Friday 1PM MYT)
- Deploy stacks with `--exclusively` flag to avoid SSM parameter resolution errors
- Deploy order: DynamoDB → Auth → Storage → Api → Lambda
