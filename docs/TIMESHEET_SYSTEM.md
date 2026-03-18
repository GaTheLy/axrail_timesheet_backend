# Employee Timesheet Management System — Technical Documentation

## Overview

The Employee Timesheet Management System is a serverless application built on AWS that manages employee timesheets, approvals, reporting, and automated workflows. It uses AWS AppSync (GraphQL), Lambda (Python 3.12), DynamoDB, Cognito, EventBridge, SES, and S3, all provisioned via AWS CDK.

---

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────────┐
│   Clients   │────▶│ AWS AppSync  │────▶│  Lambda Resolvers │
│  (GraphQL)  │     │  (Cognito)   │     │   (Python 3.12)   │
└─────────────┘     └──────────────┘     └────────┬─────────┘
                                                   │
                    ┌──────────────────────────────┼──────────────────┐
                    │                              │                  │
              ┌─────▼─────┐              ┌────────▼───────┐   ┌─────▼─────┐
              │  DynamoDB  │              │   S3 (Reports) │   │  Cognito  │
              │ (10 tables)│              │                │   │ User Pool │
              └─────┬──────┘              └────────────────┘   └───────────┘
                    │ Streams
          ┌─────────┼─────────┐
          ▼                   ▼
  ┌───────────────┐  ┌────────────────┐
  │ Report Gen    │  │ Performance    │
  │ Lambda        │  │ Tracking Lambda│
  └───────────────┘  └────────────────┘

  ┌─────────────────────────────────────────────┐
  │           EventBridge Scheduled Rules        │
  │  ┌──────────────┐ ┌──────────┐ ┌──────────┐│
  │  │Deadline Lock │ │Notify/   │ │ Archival ││
  │  │Enforcement   │ │Email     │ │          ││
  │  └──────────────┘ └──────────┘ └──────────┘│
  └─────────────────────────────────────────────┘
```

### CDK Stacks

| Stack | File | Purpose |
|---|---|---|
| TimesheetAuthStack | `colabs_pipeline_cdk/stack/auth_stack.py` | Cognito User Pool, groups, client |
| TimesheetDynamoDBStack | `colabs_pipeline_cdk/stack/dynamodb_stack.py` | All 10 DynamoDB tables with GSIs |
| TimesheetStorageStack | `colabs_pipeline_cdk/stack/storage_stack.py` | S3 report bucket |
| TimesheetApiStack | `colabs_pipeline_cdk/stack/api_stack.py` | AppSync GraphQL API |
| TimesheetLambdaStack | `colabs_pipeline_cdk/stack/lambda_stack.py` | All Lambda functions, resolvers, EventBridge rules, stream triggers |

---

## Authentication & Authorization

### Cognito User Pool

- Sign-in via email
- Self-sign-up disabled (admin-created accounts only)
- Password policy: min 8 chars, uppercase, lowercase, digits, symbols
- Temp password validity: 7 days
- Token validity: access/ID 1 hour, refresh 30 days

### Custom Attributes

| Attribute | Description |
|---|---|
| `custom:userType` | `superadmin`, `admin`, `user` |
| `custom:role` | `Project_Manager`, `Tech_Lead`, `Employee` |
| `custom:departmentId` | UUID of assigned department |
| `custom:positionId` | UUID of assigned position |

### Cognito Groups

Users are assigned to groups matching their `userType`: `superadmin`, `admin`, `user`.

### RBAC Implementation (`lambdas/shared/auth.py`)

Two authorization helpers are used across all resolvers:

- `require_user_type(event, allowed_types)` — validates the caller's `userType` claim
- `require_role(event, allowed_roles)` — validates the caller's `role` claim

Both extract identity from `event["identity"]["claims"]` (AppSync Cognito integration) and raise `ForbiddenError` on unauthorized access.

### Permission Matrix

| Operation | Required Permission |
|---|---|
| Create admin user | `superadmin` |
| Create regular user | `superadmin` or `admin` |
| Delete user | `superadmin` or `admin` (scoped) |
| Approve/Reject project | `superadmin` |
| Create project | `superadmin` or `admin` |
| Approve/Reject timesheet | `Project_Manager` or `Tech_Lead` |
| List pending timesheets | `Project_Manager` or `Tech_Lead` |
| Download reports | `Project_Manager` or `Tech_Lead` |
| Create/submit own timesheet | Any authenticated user |
| Manage departments/positions | `superadmin` or `admin` |

---

## Data Model

### DynamoDB Tables (10 total)

All tables use PAY_PER_REQUEST billing. Table names follow the pattern `{TableName}-{env}`.

#### Users
- PK: `userId` (UUID)
- GSIs: `email-index`, `departmentId-index`, `supervisorId-index`
- Fields: email, fullName, userType, role, positionId, departmentId, supervisorId, createdAt, createdBy, updatedAt, updatedBy

#### Departments
- PK: `departmentId` (UUID)
- GSI: `departmentName-index`
- Fields: departmentName, createdAt, createdBy, updatedAt, updatedBy

#### Positions
- PK: `positionId` (UUID)
- GSI: `positionName-index`
- Fields: positionName, description, createdAt, createdBy, updatedAt, updatedBy

#### Projects
- PK: `projectId` (UUID)
- GSIs: `projectCode-index`, `approval_status-index`, `projectManagerId-index`
- Fields: projectCode, projectName, startDate, plannedHours, projectManagerId, status, approval_status, rejectionReason, createdAt/By, updatedAt/By

#### Timesheet_Periods
- PK: `periodId` (UUID)
- GSI: `startDate-index`
- Fields: startDate, endDate, submissionDeadline, periodString, biweeklyPeriodId, isLocked, createdAt, createdBy

#### Timesheet_Submissions
- PK: `submissionId` (UUID)
- GSIs: `employeeId-periodId-index`, `periodId-status-index`, `status-index`
- DynamoDB Streams: NEW_AND_OLD_IMAGES
- Fields: periodId, employeeId, status, archived, totalHours, chargeableHours, approvedBy, approvedAt, createdAt, updatedAt, updatedBy

#### Timesheet_Entries
- PK: `entryId` (UUID)
- GSIs: `submissionId-index`, `projectCode-index`
- Fields: submissionId, projectCode, saturday–friday (daily hours), totalHours, createdAt, updatedAt

#### Employee_Performance
- PK: `userId` / SK: `year` (composite key)
- Fields: ytdChargable_hours, ytdTotalHours, ytdChargabilityPercentage, updatedAt

#### Report_Distribution_Config
- PK: `configId` (singleton: `"default"`)
- Fields: schedule_cron_expression, recipient_emails, enabled, updatedAt, updatedBy

#### Main_Database
- PK: `recordId` (UUID)
- Fields: type, chargeCode, projectName, budgetEffort, projectStatus, createdAt, updatedAt, updatedBy

---

## GraphQL API

### Queries

| Query | Auth | Description |
|---|---|---|
| `getUser(userId)` | Any | Get user by ID |
| `listUsers(filter)` | Any | List users with optional filters (userType, role, department, supervisor) |
| `listDepartments` | Any | List all departments |
| `listPositions` | Any | List all positions |
| `listProjects(filter)` | Any | List projects with optional filters (approval_status, PM, status) |
| `getCurrentPeriod` | Any | Get the active timesheet period |
| `listTimesheetPeriods(filter)` | Any | List periods with optional date/lock filters |
| `getTimesheetSubmission(submissionId)` | Owner or admin | Get submission with all entries |
| `listMySubmissions(filter)` | Owner | List caller's own submissions |
| `listPendingTimesheets` | PM/TL | List Submitted timesheets for supervised employees |
| `getTCSummaryReport(techLeadId, periodId)` | PM/TL | Pre-signed S3 URL for TC Summary CSV |
| `getProjectSummaryReport(periodId)` | PM/TL | Pre-signed S3 URL for Project Summary CSV |
| `listMainDatabase` | Any | List all main database records |
| `getReportDistributionConfig` | Any | Get report distribution settings |

### Mutations

| Mutation | Auth | Description |
|---|---|---|
| `createUser(input)` | superadmin/admin | Create user + Cognito account |
| `updateUser(userId, input)` | superadmin/admin | Update user fields (role, position, etc.) |
| `deleteUser(userId)` | superadmin/admin | Delete from DynamoDB + Cognito |
| `createDepartment(input)` | superadmin/admin | Create department (unique name enforced) |
| `updateDepartment(departmentId, input)` | superadmin/admin | Update department name |
| `deleteDepartment(departmentId)` | superadmin/admin | Delete (blocked if users associated) |
| `createPosition(input)` | superadmin/admin | Create position (unique name enforced) |
| `updatePosition(positionId, input)` | superadmin/admin | Update position |
| `deletePosition(positionId)` | superadmin/admin | Delete position |
| `createProject(input)` | superadmin/admin | Create project (auto-approved if superadmin) |
| `approveProject(projectId)` | superadmin | Approve Pending_Approval project |
| `rejectProject(projectId, reason)` | superadmin | Reject with reason |
| `updateProject(projectId, input)` | superadmin/admin | Update project fields |
| `createTimesheetPeriod(input)` | superadmin/admin | Create period (Sat–Fri, 6 days, no overlaps) |
| `updateTimesheetPeriod(periodId, input)` | superadmin/admin | Update deadline/metadata |
| `createTimesheetSubmission(periodId)` | Any user | Create Draft submission (one per employee per period) |
| `submitTimesheet(submissionId)` | Owner | Transition Draft/Rejected → Submitted |
| `addTimesheetEntry(submissionId, input)` | Owner | Add entry (max 27, approved projects only) |
| `updateTimesheetEntry(entryId, input)` | Owner | Update entry hours/project |
| `removeTimesheetEntry(entryId)` | Owner | Remove entry |
| `approveTimesheet(submissionId)` | PM/TL | Submitted → Approved |
| `rejectTimesheet(submissionId)` | PM/TL | Submitted → Rejected |
| `updateMainDatabaseRecord(id, input)` | superadmin/admin | Update main DB record |
| `bulkImportCSV(file)` | superadmin/admin | Import CSV from S3 |
| `refreshDatabase(file)` | superadmin/admin | Replace all records from CSV |
| `updateReportDistributionConfig(input)` | superadmin/admin | Update email schedule/recipients |

---

## Lambda Functions (45 total)

### Directory Structure

```
lambdas/
├── shared/auth.py                          # RBAC utilities
├── users/                                  # 5 handlers
│   ├── CreateUser/handler.py
│   ├── UpdateUser/handler.py
│   ├── DeleteUser/handler.py
│   ├── GetUser/handler.py
│   └── ListUsers/handler.py
├── departments/                            # 4 handlers
│   ├── CreateDepartment/handler.py
│   ├── UpdateDepartment/handler.py
│   ├── DeleteDepartment/handler.py
│   └── ListDepartments/handler.py
├── positions/                              # 4 handlers
│   ├── CreatePosition/handler.py
│   ├── UpdatePosition/handler.py
│   ├── DeletePosition/handler.py
│   └── ListPositions/handler.py
├── projects/                               # 5 handlers
│   ├── CreateProject/handler.py
│   ├── ApproveProject/handler.py
│   ├── RejectProject/handler.py
│   ├── UpdateProject/handler.py
│   └── ListProjects/handler.py
├── periods/                                # 4 handlers
│   ├── CreateTimesheetPeriod/handler.py
│   ├── UpdateTimesheetPeriod/handler.py
│   ├── ListTimesheetPeriods/handler.py
│   ├── GetCurrentPeriod/handler.py
│   └── shared_utils.py
├── submissions/                            # 4 handlers
│   ├── CreateTimesheetSubmission/handler.py
│   ├── SubmitTimesheet/handler.py
│   ├── GetTimesheetSubmission/handler.py
│   └── ListMySubmissions/handler.py
├── entries/                                # 3 handlers
│   ├── AddTimesheetEntry/handler.py
│   ├── UpdateTimesheetEntry/handler.py
│   ├── RemoveTimesheetEntry/handler.py
│   └── shared_utils.py
├── reviews/                                # 3 handlers
│   ├── ApproveTimesheet/handler.py
│   ├── RejectTimesheet/handler.py
│   ├── ListPendingTimesheets/handler.py
│   └── shared_utils.py
├── reports/                                # 3 handlers
│   ├── handler.py                          # Stream-triggered report generator
│   ├── GetTCSummaryReport/handler.py
│   └── GetProjectSummaryReport/handler.py
├── performance/handler.py                  # Stream-triggered YTD tracking
├── deadline_enforcement/handler.py         # EventBridge-triggered
├── notifications/handler.py                # EventBridge-triggered
├── archival/handler.py                     # EventBridge-triggered
├── notification_config/                    # 2 handlers
│   ├── GetReportDistributionConfig/handler.py
│   └── UpdateReportDistributionConfig/handler.py
└── main_database/                          # 4 handlers
    ├── ListMainDatabase/handler.py
    ├── UpdateMainDatabaseRecord/handler.py
    ├── BulkImportCSV/handler.py
    ├── RefreshDatabase/handler.py
    └── shared_utils.py
```

---

## Timesheet Workflow

### Submission Status Lifecycle

```
                  ┌──────────┐
                  │  Draft   │◀──── createTimesheetSubmission
                  └────┬─────┘
                       │ submitTimesheet
                  ┌────▼─────┐
           ┌──────│ Submitted│──────┐
           │      └──────────┘      │
  approveTimesheet          rejectTimesheet
           │                        │
     ┌─────▼────┐            ┌──────▼───┐
     │ Approved │            │ Rejected │
     └──────────┘            └────┬─────┘
                                  │ submitTimesheet (resubmit)
                             ┌────▼─────┐
                             │ Submitted│
                             └──────────┘

  Deadline passes (EventBridge) ──▶ Draft/Submitted → Locked
  Missing employees ──▶ Locked (zero hours, auto-created)
```

### Validation Rules

- Periods must start on Saturday, end on Friday, span exactly 6 days
- No overlapping periods allowed
- One submission per employee per period
- Max 27 entries per submission
- Daily hours: non-negative, max 2 decimal places, ≤24 hours per day across all entries
- Entries only allowed on Approved projects
- Entries only editable when submission status is Draft or Rejected
- Archived submissions are read-only

---

## Approval Workflow

### Project Approval

1. Admin creates project → `approval_status = "Pending_Approval"`
2. Superadmin creates project → `approval_status = "Approved"` (auto-approved)
3. Superadmin calls `approveProject` → Pending_Approval → Approved
4. Superadmin calls `rejectProject(reason)` → Pending_Approval → Rejected

### Timesheet Approval

1. Employee submits timesheet → status = Submitted
2. Project Manager or Tech Lead reviews supervised employees' submissions via `listPendingTimesheets`
3. `approveTimesheet` → Submitted → Approved (triggers DynamoDB Stream events)
4. `rejectTimesheet` → Submitted → Rejected (employee can resubmit)

---

## Automated CRON Jobs (EventBridge)

### 1. Deadline Enforcement (`lambdas/deadline_enforcement/handler.py`)

- Scans for periods where `submissionDeadline` has passed and `isLocked = false`
- Locks all Draft and Submitted submissions for expired periods (status → Locked)
- Creates Locked submissions with zero hours for employees who never submitted
- Marks the period as `isLocked = true`

### 2. Report Generation (`lambdas/reports/handler.py`)

Triggered by DynamoDB Streams when a submission transitions to Approved or Locked:

- Generates TC Summary CSV (per Tech Lead): Name, Chargeable Hours, Total Hours, Current Period Chargeability, YTD Chargeability
- Generates Project Summary CSV (per period): Project Code, Name, Planned Hours, Charged Hours, Utilization, Biweekly Effort
- Uploads CSVs to S3 under `reports/tc-summary/{periodId}/` and `reports/project-summary/{periodId}/`

### 3. Email Notifications (`lambdas/notifications/handler.py`)

- Reads `Report_Distribution_Config` to check if enabled
- Determines the current active period
- Sends Project Summary CSV to all configured `recipient_emails` via SES
- For each Tech Lead, generates and sends their TC Summary CSV via SES
- Graceful failure handling: logs errors per recipient without crashing

### 4. Archival (`lambdas/archival/handler.py`)

- Finds the most recently ended biweekly period
- Sets `archived = true` on all submissions in that biweekly cycle
- Retains all entries and metadata (no data deletion)

---

## Reporting Engine

### TC Summary Report

| Column | Description |
|---|---|
| Name | Employee full name |
| Chargeable Hours | Hours on chargeable projects for the period |
| Total Hours | All hours for the period |
| Current Period Chargeability | (Chargeable / Total) × 100 |
| YTD Chargeability | From Employee_Performance table |

- Only includes Approved/Locked submissions
- Scoped to employees supervised by the requesting Tech Lead

### Project Summary Report

| Column | Description |
|---|---|
| Project Charge Code | Unique project code |
| Project Name | Project display name |
| Planned Hours | Budget hours from project record |
| Charged Hours | Sum of entry hours for the period |
| Utilization | (Charged / Planned) × 100 |
| Current Biweekly Effort | Hours across the biweekly period cycle |

- Includes all projects regardless of status
- Reports stored in S3 with pre-signed URL access (1 hour expiry)

### YTD Performance Tracking (`lambdas/performance/handler.py`)

- Triggered by DynamoDB Streams on submission approval
- Atomically increments `ytdChargable_hours` and `ytdTotalHours` using DynamoDB ADD
- Recalculates `ytdChargabilityPercentage` after each update
- Keyed by (userId, year) composite key

---

## S3 Storage

- Bucket: `{TIMESHEET_REPORT_BUCKET_PREFIX}-{env}`
- Public access blocked, SSL enforced, S3-managed encryption
- Lifecycle: transition to IA after 90 days, expire after 365 days
- CORS enabled for GET requests
- Report paths:
  - `reports/tc-summary/{periodId}/{timestamp}.csv`
  - `reports/project-summary/{periodId}/{timestamp}.csv`

---

## Environment Configuration

All environment-specific values are centralized in `colabs_pipeline_cdk/environment.py`. Cross-stack communication uses SSM Parameter Store under the prefix `{TIMESHEET_SSM_PREFIX}/{env}/`.

### SSM Parameter Paths

| Path | Value |
|---|---|
| `.../dynamodb/{table}/table-name` | DynamoDB table name |
| `.../dynamodb/{table}/table-arn` | DynamoDB table ARN |
| `.../dynamodb/submissions/stream-arn` | Submissions stream ARN |
| `.../auth/user-pool-id` | Cognito User Pool ID |
| `.../auth/user-pool-arn` | Cognito User Pool ARN |
| `.../api/graphql-api-id` | AppSync API ID |
| `.../api/graphql-api-url` | AppSync GraphQL URL |
| `.../api/graphql-api-arn` | AppSync API ARN |
| `.../storage/report-bucket-name` | S3 bucket name |
| `.../storage/report-bucket-arn` | S3 bucket ARN |

---

## Development

### Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### CDK Commands

```bash
cdk synth          # Synthesize CloudFormation templates
cdk ls             # List all stacks
cdk deploy <stack> # Deploy a specific stack
cdk diff           # Compare deployed vs current
```

### Testing

```bash
pytest
```

### Stack Deployment Order

1. `TimesheetAuthStack` (Cognito — no dependencies)
2. `TimesheetDynamoDBStack` (tables — no dependencies)
3. `TimesheetStorageStack` (S3 — no dependencies)
4. `TimesheetApiStack` (AppSync — depends on Auth via SSM)
5. `TimesheetLambdaStack` (Lambdas — depends on all above via SSM)
