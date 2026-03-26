# Employee Timesheet Management System — Technical Documentation

## Overview

The Employee Timesheet Management System is a serverless application built on AWS that manages employee timesheets, automated submission, reporting, and automated workflows. It uses AWS AppSync (GraphQL), Lambda (Python 3.12), DynamoDB, Cognito, EventBridge, SES, and S3, all provisioned via AWS CDK.

Key design decisions:
- Only two submission statuses: Draft and Submitted
- Period runs Monday to Friday (not Saturday to Friday)
- No manual submit — auto-submit only at Friday 5PM MYT deadline
- No approval/rejection flow
- Under-40h notification goes to employee only
- Period + submissions auto-created on Monday for all employees

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
              │ (11 tables)│              │                │   │ User Pool │
              └─────┬──────┘              └────────────────┘   └───────────┘
                    │ Streams
          ┌─────────┼─────────┐
          ▼                   ▼
  ┌───────────────┐  ┌────────────────┐
  │ Report Gen    │  │ Performance    │
  │ Lambda        │  │ Tracking Lambda│
  └───────────────┘  └────────────────┘

  ┌─────────────────────────────────────────────────────────────┐
  │              EventBridge Scheduled Rules                     │
  │  ┌──────────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐ │
  │  │Auto-Provision│ │Deadline  │ │Deadline  │ │ Archival  │ │
  │  │(Mon 00:05MYT)│ │Reminder  │ │Enforce   │ │           │ │
  │  │              │ │(Fri 1PM) │ │(Fri 5PM) │ │           │ │
  │  └──────────────┘ └──────────┘ └──────────┘ └───────────┘ │
  │  ┌──────────────┐                                          │
  │  │Notification  │                                          │
  │  │(Mon 8AM UTC) │                                          │
  │  └──────────────┘                                          │
  └─────────────────────────────────────────────────────────────┘
```


### CDK Stacks

| Stack | File | Purpose |
|---|---|---|
| TimesheetAuthStack | `colabs_pipeline_cdk/stack/auth_stack.py` | Cognito User Pool, groups, client |
| TimesheetDynamoDBStack | `colabs_pipeline_cdk/stack/dynamodb_stack.py` | All 11 DynamoDB tables with GSIs |
| TimesheetStorageStack | `colabs_pipeline_cdk/stack/storage_stack.py` | S3 report bucket |
| TimesheetApiStack | `colabs_pipeline_cdk/stack/api_stack.py` | AppSync GraphQL API |
| TimesheetLambdaStack | `colabs_pipeline_cdk/stack/lambda_stack.py` | All Lambda functions, resolvers, EventBridge rules, stream triggers |

---

## User Status (Soft Delete)

Users have a `status` field with values `active` or `inactive`:

- New users are created with `status: active` by default
- Deactivating a user sets `status: inactive` and disables their Cognito account
- Activating a user sets `status: active` and re-enables their Cognito account
- Deactivated users' data remains fully visible for historical queries and reports
- Deactivated users are excluded from:
  - Auto-provisioning (no Draft submissions created on Monday)
  - Deadline enforcement (no zero-hour Submitted submissions created)
  - Deadline reminders (no reminder emails sent)
- The `listUsers` query supports filtering by `status` field
- Only superadmins and admins can activate/deactivate users (same RBAC as other user mutations)

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

### RBAC Implementation (`lambdas/shared/auth.py`)

Two authorization helpers are used across all resolvers:

- `require_user_type(event, allowed_types)` — validates the caller's `userType` claim
- `require_role(event, allowed_roles)` — validates the caller's `role` claim

---

## Data Model

### DynamoDB Tables (11 total)

All tables use PAY_PER_REQUEST billing. Table names follow the pattern `{TableName}-{env}`.

#### Timesheet_Periods
- PK: `periodId` (UUID)
- GSI: `startDate-index`
- Fields: startDate (Monday), endDate (Friday), submissionDeadline (auto-computed Friday 5PM MYT = 09:00 UTC), periodString, biweeklyPeriodId, isLocked, createdAt, createdBy

#### Timesheet_Submissions
- PK: `submissionId` (UUID)
- GSIs: `employeeId-periodId-index`, `periodId-status-index`, `status-index`
- DynamoDB Streams: NEW_AND_OLD_IMAGES
- Fields: periodId, employeeId, status (Draft|Submitted), archived, totalHours, chargeableHours, createdAt, updatedAt, updatedBy

#### Timesheet_Entries
- PK: `entryId` (UUID)
- GSIs: `submissionId-index`, `projectCode-index`
- Fields: submissionId, projectCode, saturday–friday (daily hours), totalHours, createdAt, updatedAt

#### Users
- PK: `userId` (UUID)
- GSIs: `email-index`, `departmentId-index`, `supervisorId-index`
- Fields: email, fullName, userType (superadmin|admin|user), role (Project_Manager|Tech_Lead|Employee), status (active|inactive), positionId, departmentId, supervisorId, createdAt, createdBy, updatedAt, updatedBy
- The `status` field supports soft delete: deactivated users (status=inactive) remain visible for historical queries but are excluded from auto-provisioning, deadline enforcement, and reminders
- The `supervisorId` field is deprecated — supervisor relationships are now managed via the `Timesheet_ProjectAssignments` table, which supports many-to-many employee-project-supervisor mappings

#### Other Tables
- Departments, Positions, Projects, Employee_Performance, Report_Distribution_Config, Main_Database (unchanged from original design)

#### Timesheet_ProjectAssignments
- PK: `assignmentId` (UUID)
- GSIs: `employeeId-index`, `supervisorId-index`, `projectId-index`
- Fields: employeeId, projectId, supervisorId, createdAt, createdBy, updatedAt, updatedBy
- Stores many-to-many mappings between employees, projects, and supervisors
- Uniqueness constraint on `(employeeId, projectId)` enforced at application layer

---

## Timesheet Workflow

### Submission Status Lifecycle

```
Monday 00:05 MYT (auto-provisioning)
  │
  ▼
┌──────────┐
│  Draft   │◀──── Auto-created for each employee
└────┬─────┘
     │ Employee fills entries during the week
     │
Friday 5:05PM MYT (deadline enforcement)
     │
┌────▼─────┐
│Submitted │◀──── Auto-submitted (Draft → Submitted)
└──────────┘      Missing employees get zero-hour Submitted submission
     │
     │ Biweekly archival
     ▼
┌──────────┐
│ Archived │
└──────────┘
```

### Weekly Timeline

| Time | Event | Action |
|---|---|---|
| Monday 00:05 MYT (Sun 16:05 UTC) | Auto-provisioning | Create period + Draft submissions for all employees |
| Monday–Friday | Employee work | Employees fill timesheet entries (Draft status) |
| Friday 1PM MYT (05:00 UTC) | Deadline reminder | Email reminder to employees with Draft submissions |
| Friday 5PM MYT (09:00 UTC) | Deadline | Submission deadline |
| Friday 5:05PM MYT (09:05 UTC) | Deadline enforcement | Auto-submit all Drafts, create missing submissions, send under-40h emails, lock period |

### Validation Rules

- Periods must start on Monday, end on Friday, span exactly 4 days
- No overlapping periods allowed
- One submission per employee per period (auto-created)
- Max 27 entries per submission
- Daily hours: non-negative, max 2 decimal places, ≤24 hours per day across all entries
- Entries only allowed on Approved projects
- Entries only editable when submission status is Draft
- Archived submissions are read-only
- Required weekly hours: 40 (under-40h notification sent to employee)

---

## Automated CRON Jobs (EventBridge)

### 1. Auto-Provisioning (`lambdas/auto_provisioning/handler.py`)

- Schedule: Every Monday 00:05 MYT (Sunday 16:05 UTC)
- Computes current week's Monday–Friday dates
- Creates the period record with auto-computed deadline (Friday 5PM MYT)
- Creates a Draft submission for every active Employee in the Users table (inactive users are skipped)

### 2. Deadline Reminder (`lambdas/deadline_reminder/handler.py`)

- Schedule: Every Friday 1PM MYT (05:00 UTC)
- Finds the current active period (not locked)
- Sends reminder email to employees who still have Draft submissions

### 3. Deadline Enforcement (`lambdas/deadline_enforcement/handler.py`)

- Schedule: Every Friday 5:05PM MYT (09:05 UTC)
- Scans for periods where `submissionDeadline` has passed and `isLocked = false`
- Auto-submits all Draft submissions (Draft → Submitted)
- Creates Submitted submissions with zero hours for active employees without one (inactive users are skipped)
- Sends under-40-hours email notification to employees only
- Marks the period as `isLocked = true`

### 4. Report Generation (`lambdas/reports/handler.py`)

Triggered by DynamoDB Streams when a submission transitions to Submitted:

- Queries ProjectAssignments table to find all supervisors for the submitting employee
- Generates TC Summary CSV for each distinct supervisor
- Generates Project Summary CSV (per period)
- Uploads CSVs to S3

### 5. Email Notifications (`lambdas/notifications/handler.py`)

- Schedule: Configurable (default Monday 8AM UTC)
- Sends Project Summary CSV to configured recipients
- Sends TC Summary CSV to each Tech Lead (using ProjectAssignments to determine supervised employees)
- Skips TC Summary email for Tech Leads with no project assignments

### 6. Archival (`lambdas/archival/handler.py`)

- Schedule: Daily
- Archives submissions from ended biweekly periods

---

## Project Assignments

The system supports many-to-many relationships between employees, projects, and supervisors via the `Timesheet_ProjectAssignments` table. This replaces the single `supervisorId` field on the Users table (which is retained as deprecated for backward compatibility).

### GraphQL API

- `createProjectAssignment(input)` — Assign an employee to a project with a supervisor (admin/superadmin only)
- `updateProjectAssignment(assignmentId, input)` — Update supervisor or project on an assignment (admin/superadmin only)
- `deleteProjectAssignment(assignmentId)` — Remove an assignment (admin/superadmin only)
- `listProjectAssignments(filter)` — Query assignments by employeeId, supervisorId, or projectId (any authenticated user)

### Validation Rules

- Each `(employeeId, projectId)` combination must be unique
- Referenced `employeeId`, `projectId`, and `supervisorId` must exist in their respective tables
- Only `superadmin` and `admin` users can create, update, or delete assignments

### Impact on Existing Features

- TC Summary reports now include all employees assigned to a Tech Lead via ProjectAssignments (deduplicated)
- ListPendingTimesheets uses ProjectAssignments to determine supervised employees
- Stream-triggered report generation fans out to all supervisors for the submitting employee
- Notification service uses ProjectAssignments for TC Summary email distribution

### Shared Utility

`lambdas/shared/project_assignments.py` provides two reusable functions:
- `get_supervised_employee_ids(table_name, supervisor_id)` — Returns deduplicated employee IDs for a supervisor
- `get_employee_supervisor_ids(table_name, employee_id)` — Returns deduplicated supervisor IDs for an employee

---

## S3 Storage

- Bucket: `{TIMESHEET_REPORT_BUCKET_PREFIX}-{env}`
- Public access blocked, SSL enforced, S3-managed encryption
- Lifecycle: transition to IA after 90 days, expire after 365 days
- Report paths:
  - `reports/tc-summary/{periodId}/{timestamp}.csv`
  - `reports/project-summary/{periodId}/{timestamp}.csv`

---

## Environment Configuration

All environment-specific values are centralized in `colabs_pipeline_cdk/environment.py`. Cross-stack communication uses SSM Parameter Store under the prefix `{TIMESHEET_SSM_PREFIX}/{env}/`.

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
cdk deploy <stack> --exclusively  # Deploy a specific stack
cdk diff           # Compare deployed vs current
```

### Testing

```bash
pytest
```

### Stack Deployment Order

Deploy with `--exclusively` flag to avoid SSM parameter resolution errors:

1. `TimesheetDynamoDBStack` (tables — no dependencies)
2. `TimesheetAuthStack` (Cognito — no dependencies)
3. `TimesheetStorageStack` (S3 — no dependencies)
4. `TimesheetApiStack` (AppSync — depends on Auth via SSM)
5. `TimesheetLambdaStack` (Lambdas — depends on all above via SSM)


---

## Frontend Changes: Admin Dashboard Card Removal

The admin dashboard should remove the following summary cards:

- **Total Projects**
- **Total Departments**
- **Total Positions**

These cards are no longer needed on the admin dashboard view. All other dashboard content and functionality should remain unchanged.

This is a frontend-only change — no backend Lambda, GraphQL schema, or CDK modifications are required.
