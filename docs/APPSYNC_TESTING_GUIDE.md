# AppSync Backend Testing Guide

## Employee Timesheet Management System

**Project:** COLABS Timesheet System  
**API:** TimesheetGraphQLApi (AWS AppSync)  
**Auth:** Amazon Cognito User Pool  
**Date:** March 2026

---

## Table of Contents

- [AppSync Backend Testing Guide](#appsync-backend-testing-guide)
  - [Employee Timesheet Management System](#employee-timesheet-management-system)
  - [Table of Contents](#table-of-contents)
  - [1. Prerequisites](#1-prerequisites)
  - [2. Test User Setup](#2-test-user-setup)
  - [3. Accessing the AppSync Console](#3-accessing-the-appsync-console)
  - [4. System Flow Overview](#4-system-flow-overview)
  - [5. Test Execution Order](#5-test-execution-order)
  - [6. Test Cases](#6-test-cases)
    - [6.1 Departments](#61-departments)
    - [6.2 Positions](#62-positions)
    - [6.3 Users](#63-users)
    - [6.4 Projects](#64-projects)
    - [6.5 Timesheet Periods](#65-timesheet-periods)
    - [6.6 Timesheet Submissions](#66-timesheet-submissions)
    - [6.7 Timesheet Entries](#67-timesheet-entries)
    - [6.8 Automated Flows](#68-automated-flows)
      - [Auto-Provisioning (Monday)](#auto-provisioning-monday)
      - [Deadline Reminder (Friday 1PM MYT)](#deadline-reminder-friday-1pm-myt)
      - [Deadline Enforcement (Friday 5PM MYT)](#deadline-enforcement-friday-5pm-myt)
    - [6.9 Reports](#69-reports)
    - [6.10 Main Database](#610-main-database)
    - [6.11 Report Distribution Config](#611-report-distribution-config)
  - [7. Troubleshooting](#7-troubleshooting)
  - [8. ID Tracking Sheet](#8-id-tracking-sheet)

---

## 1. Prerequisites

- All CDK stacks deployed in order:
  1. `ColabsTimesheetDynamoDBStack-dev`
  2. `ColabsTimesheetAuthStack-dev`
  3. `ColabsTimesheetStorageStack-dev`
  4. `ColabsTimesheetApiStack-dev`
  5. `ColabsTimesheetLambdaStack-dev`
- AWS Console access with permissions to AppSync and Cognito
- A Cognito test user with `superadmin` privileges (see Section 2)

---

## 2. Test User Setup

Run these commands in your terminal to create a test user:

```bash
# Set variables
USER_POOL_ID="<your-user-pool-id>"   # From Cognito console or SSM: /timesheet/dev/auth/user-pool-id
CLIENT_ID="<your-app-client-id>"      # From Cognito > App clients
TEST_EMAIL="<test-email>"
REGION="ap-southeast-1"

# Create the user
aws cognito-idp admin-create-user \
  --user-pool-id $USER_POOL_ID \
  --username $TEST_EMAIL \
  --user-attributes \
    Name=email,Value=$TEST_EMAIL \
    Name=name,Value="Test Admin" \
    Name=custom:userType,Value=superadmin \
    Name=custom:role,Value=Project_Manager \
    Name=custom:departmentId,Value="" \
    Name=custom:positionId,Value="" \
  --temporary-password "TempPass1!" \
  --region $REGION

# Set permanent password
aws cognito-idp admin-set-user-password \
  --user-pool-id $USER_POOL_ID \
  --username $TEST_EMAIL \
  --password "YourSecurePass1!" \
  --permanent \
  --region $REGION

# Add to superadmin group
aws cognito-idp admin-add-user-to-group \
  --user-pool-id $USER_POOL_ID \
  --username $TEST_EMAIL \
  --group-name superadmin \
  --region $REGION
```

---

## 3. Accessing the AppSync Console

1. Open **AWS Console** → search for **AppSync**
2. Select your API: **TimesheetGraphQLApi-dev**
3. Click **Queries** in the left sidebar
4. Click **Login with User Pools** at the top of the query editor
5. Enter your **Client ID**, **Username** (email), and **Password**
6. You are now authenticated and can run queries/mutations

---

## 4. System Flow Overview

The timesheet system is fully automated:

```
Monday (auto)          Mon-Thu (manual)         Friday 1PM MYT        Friday 5PM MYT
┌──────────────┐      ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│ Auto-create  │      │ Employee     │      │ Reminder     │      │ Auto-submit  │
│ period +     │ ──── │ fills out    │ ──── │ email sent   │ ──── │ all Draft →  │
│ Draft subs   │      │ timesheet    │      │ to employees │      │ Submitted    │
│ for all      │      │ entries      │      │ with Draft   │      │ + under-40h  │
│ employees    │      │              │      │ submissions  │      │ email sent   │
└──────────────┘      └──────────────┘      └──────────────┘      └──────────────┘
```

- **Period:** Monday to Friday (5 working days)
- **Statuses:** Draft → Submitted (automatic only)
- **No manual submit.** No approval/rejection flow.
- **Deadline:** Always Friday 5:00 PM MYT (09:00 UTC)
- **Reminder:** Friday 1:00 PM MYT (05:00 UTC) — 4 hours before deadline

---

## 5. Test Execution Order

Tests must be run in this order because later tests depend on IDs created by earlier ones.

| Step | Component              | Creates IDs Needed By         |
|------|------------------------|-------------------------------|
| 1    | Departments            | Users                         |
| 2    | Positions              | Users                         |
| 3    | Users                  | Projects, Submissions         |
| 4    | Projects               | Timesheet Entries             |
| 5    | Timesheet Periods      | Submissions                   |
| 6    | Timesheet Submissions  | Entries                       |
| 7    | Timesheet Entries      | Reports                       |
| 8    | Automated Flows        | (EventBridge — tested via AWS Console) |
| 9    | Reports                | —                             |
| 10   | Main Database          | —                             |
| 11   | Report Distribution    | —                             |

> **Important:** Record every ID returned from create mutations in the ID Tracking Sheet (Section 8).

---

## 6. Test Cases

### 6.1 Departments

**Create Department**

```graphql
mutation {
  createDepartment(input: { departmentName: "Engineering" }) {
    departmentId
    departmentName
    createdAt
  }
}
```

| Field          | Expected                          |
|----------------|-----------------------------------|
| departmentId   | UUID generated                    |
| departmentName | "Engineering"                     |
| createdAt      | Current timestamp                 |

☐ Pass / ☐ Fail — Notes: _______________

**List Departments**

```graphql
query {
  listDepartments {
    departmentId
    departmentName
    createdAt
  }
}
```

| Expected                                      |
|-----------------------------------------------|
| Returns array containing the created department |

☐ Pass / ☐ Fail — Notes: _______________

**Update Department**

```graphql
mutation {
  updateDepartment(
    departmentId: "<DEPARTMENT_ID>"
    input: { departmentName: "Engineering Dept" }
  ) {
    departmentId
    departmentName
    updatedAt
  }
}
```

| Field          | Expected              |
|----------------|-----------------------|
| departmentName | "Engineering Dept"    |
| updatedAt      | Current timestamp     |

☐ Pass / ☐ Fail — Notes: _______________

**Delete Department** (test after all other tests are done, or use a separate department)

```graphql
mutation {
  deleteDepartment(departmentId: "<DEPARTMENT_ID>")
}
```

| Expected                                                        |
|-----------------------------------------------------------------|
| Returns `true`                                                  |
| Fails with error if users are still assigned to this department |

☐ Pass / ☐ Fail — Notes: _______________

---

### 6.2 Positions

**Create Position**

```graphql
mutation {
  createPosition(input: {
    positionName: "Software Engineer"
    description: "Develops software applications"
  }) {
    positionId
    positionName
    description
  }
}
```

☐ Pass / ☐ Fail — Notes: _______________

**List Positions**

```graphql
query {
  listPositions {
    positionId
    positionName
    description
  }
}
```

☐ Pass / ☐ Fail — Notes: _______________

**Update Position**

```graphql
mutation {
  updatePosition(
    positionId: "<POSITION_ID>"
    input: { positionName: "Senior Software Engineer" }
  ) {
    positionId
    positionName
  }
}
```

☐ Pass / ☐ Fail — Notes: _______________

**Delete Position**

```graphql
mutation {
  deletePosition(positionId: "<POSITION_ID>")
}
```

☐ Pass / ☐ Fail — Notes: _______________

---

### 6.3 Users

**Create User** (requires departmentId and positionId from previous steps)

> **Note:** Email must be an `@axrail.com` address. Non-axrail emails are rejected with a validation error.

```graphql
mutation {
  createUser(input: {
    email: "<test-user-email>@axrail.com"
    fullName: "John Doe"
    userType: admin
    role: Tech_Lead
    positionId: "<POSITION_ID>"
    departmentId: "<DEPARTMENT_ID>"
  }) {
    userId
    email
    fullName
    userType
    role
  }
}
```

☐ Pass / ☐ Fail — Notes: _______________

**Validation: Non-axrail email should fail**

```graphql
mutation {
  createUser(input: {
    email: "user@gmail.com"
    fullName: "External User"
    userType: user
    role: Employee
    positionId: "<POSITION_ID>"
    departmentId: "<DEPARTMENT_ID>"
  }) {
    userId
  }
}
```

| Expected                                              |
|-------------------------------------------------------|
| Error: "Only @axrail.com email addresses are allowed" |

☐ Pass / ☐ Fail — Notes: _______________

**List Users**

```graphql
query {
  listUsers(filter: { limit: 10 }) {
    items {
      userId
      email
      fullName
      userType
      role
    }
    nextToken
  }
}
```

☐ Pass / ☐ Fail — Notes: _______________

**List Users with Filter**

```graphql
query {
  listUsers(filter: { userType: admin, role: Tech_Lead }) {
    items {
      userId
      fullName
    }
    nextToken
  }
}
```

☐ Pass / ☐ Fail — Notes: _______________

**Update User**

```graphql
mutation {
  updateUser(
    userId: "<USER_ID>"
    input: { fullName: "John Updated" }
  ) {
    userId
    fullName
    updatedAt
  }
}
```

☐ Pass / ☐ Fail — Notes: _______________

**Delete User** (test last or use a separate user)

```graphql
mutation {
  deleteUser(userId: "<USER_ID>")
}
```

☐ Pass / ☐ Fail — Notes: _______________

**Deactivate User** (soft delete — user data remains visible)

```graphql
mutation {
  deactivateUser(userId: "<USER_ID>") {
    userId
    fullName
    status
    updatedAt
  }
}
```

| Field  | Expected   |
|--------|------------|
| status | "inactive" |

☐ Pass / ☐ Fail — Notes: _______________

**Activate User** (re-enable a deactivated user)

```graphql
mutation {
  activateUser(userId: "<USER_ID>") {
    userId
    fullName
    status
    updatedAt
  }
}
```

| Field  | Expected |
|--------|----------|
| status | "active" |

☐ Pass / ☐ Fail — Notes: _______________

**List Users filtered by status**

```graphql
query {
  listUsers(filter: { status: active }) {
    items {
      userId
      fullName
      status
    }
    nextToken
  }
}
```

| Expected                                    |
|---------------------------------------------|
| Returns only users with status = active     |

☐ Pass / ☐ Fail — Notes: _______________

**Validation: Deactivate already inactive user should fail**

```graphql
mutation {
  deactivateUser(userId: "<INACTIVE_USER_ID>") {
    userId
    status
  }
}
```

| Expected                                    |
|---------------------------------------------|
| Error: "User '...' is already inactive"     |

☐ Pass / ☐ Fail — Notes: _______________

---

### 6.4 Projects

**Create Project** (requires a valid userId as projectManagerId)

```graphql
mutation {
  createProject(input: {
    projectCode: "PRJ-001"
    projectName: "Website Redesign"
    startDate: "2026-04-01"
    plannedHours: 500.0
    projectManagerId: "<USER_ID>"
  }) {
    projectId
    projectCode
    projectName
    approval_status
  }
}
```

| Field           | Expected            |
|-----------------|---------------------|
| approval_status | "Pending_Approval"  |

☐ Pass / ☐ Fail — Notes: _______________

**List Projects**

```graphql
query {
  listProjects(filter: { limit: 10 }) {
    items {
      projectId
      projectCode
      projectName
      approval_status
      status
    }
    nextToken
  }
}
```

☐ Pass / ☐ Fail — Notes: _______________

**Approve Project** (required before timesheet entries can reference this project)

```graphql
mutation {
  approveProject(projectId: "<PROJECT_ID>") {
    projectId
    approval_status
  }
}
```

| Field           | Expected   |
|-----------------|------------|
| approval_status | "Approved" |

☐ Pass / ☐ Fail — Notes: _______________

**Reject Project** (create a second project to test this)

```graphql
mutation {
  rejectProject(projectId: "<PROJECT_ID>", reason: "Budget not approved") {
    projectId
    approval_status
    rejectionReason
  }
}
```

| Field           | Expected               |
|-----------------|------------------------|
| approval_status | "Rejected"             |
| rejectionReason | "Budget not approved"  |

☐ Pass / ☐ Fail — Notes: _______________

**Update Project** (non-approved project, as admin or superadmin)

> **Note:** Admins cannot edit projects with `approval_status = "Approved"`. Only superadmins can edit approved projects.

```graphql
mutation {
  updateProject(
    projectId: "<PROJECT_ID>"
    input: { projectName: "Website Redesign v2", plannedHours: 600.0 }
  ) {
    projectId
    projectName
    plannedHours
  }
}
```

☐ Pass / ☐ Fail — Notes: _______________

**Validation: Admin editing approved project should fail**

> Log in as an `admin` user (not superadmin) and attempt to edit an approved project.

```graphql
mutation {
  updateProject(
    projectId: "<APPROVED_PROJECT_ID>"
    input: { projectName: "Should Fail" }
  ) {
    projectId
  }
}
```

| Expected                                                                  |
|---------------------------------------------------------------------------|
| Error: "Only superadmins can edit projects with approval status 'Approved'" |

☐ Pass / ☐ Fail — Notes: _______________

---

### 6.5 Timesheet Periods

> **Note:** In production, periods are auto-created every Monday. This manual creation is for testing only.

**Create Timesheet Period** (Monday to Friday, deadline auto-calculated)

```graphql
mutation {
  createTimesheetPeriod(input: {
    startDate: "2026-03-16"
    endDate: "2026-03-20"
    periodString: "Mar 16 - Mar 20, 2026"
    biweeklyPeriodId: "2026-W12"
  }) {
    periodId
    startDate
    endDate
    submissionDeadline
    isLocked
  }
}
```

| Field              | Expected                    |
|--------------------|-----------------------------|
| startDate          | "2026-03-16" (Monday)       |
| endDate            | "2026-03-20" (Friday)       |
| submissionDeadline | "2026-03-20T09:00:00+00:00" (Fri 5PM MYT) |
| isLocked           | false                       |

☐ Pass / ☐ Fail — Notes: _______________

**Validation: Non-Monday start date should fail**

```graphql
mutation {
  createTimesheetPeriod(input: {
    startDate: "2026-03-17"
    endDate: "2026-03-21"
    periodString: "Invalid Period"
  }) {
    periodId
  }
}
```

| Expected                                    |
|---------------------------------------------|
| Error: "startDate is not a Monday"          |

☐ Pass / ☐ Fail — Notes: _______________

**Get Current Period**

```graphql
query {
  getCurrentPeriod {
    periodId
    startDate
    endDate
    isLocked
    submissionDeadline
  }
}
```

☐ Pass / ☐ Fail — Notes: _______________

**List Timesheet Periods**

```graphql
query {
  listTimesheetPeriods(filter: { isLocked: false }) {
    periodId
    startDate
    endDate
    periodString
    isLocked
  }
}
```

☐ Pass / ☐ Fail — Notes: _______________

**Update Timesheet Period**

```graphql
mutation {
  updateTimesheetPeriod(
    periodId: "<PERIOD_ID>"
    input: { periodString: "Week of Mar 16, 2026" }
  ) {
    periodId
    periodString
  }
}
```

☐ Pass / ☐ Fail — Notes: _______________

---

### 6.6 Timesheet Submissions

> **Note:** In production, submissions are auto-created every Monday for all employees. For testing, you can query existing submissions created by the auto-provisioning Lambda, or manually invoke it.

**Get Submission**

```graphql
query {
  getTimesheetSubmission(submissionId: "<SUBMISSION_ID>") {
    submissionId
    status
    totalHours
    chargeableHours
    entries {
      entryId
      projectCode
      totalHours
    }
  }
}
```

☐ Pass / ☐ Fail — Notes: _______________

**List My Submissions**

```graphql
query {
  listMySubmissions(filter: { status: Draft }) {
    submissionId
    periodId
    status
    totalHours
  }
}
```

☐ Pass / ☐ Fail — Notes: _______________

**List All Submissions (Admin/Superadmin only)**

> **Note:** This query is restricted to `admin` and `superadmin` users. Regular users will get a permissions error.

```graphql
query {
  listAllSubmissions {
    submissionId
    employeeId
    periodId
    status
    totalHours
  }
}
```

☐ Pass / ☐ Fail — Notes: _______________

**List All Submissions with Status Filter**

```graphql
query {
  listAllSubmissions(filter: { status: Submitted }) {
    submissionId
    employeeId
    periodId
    status
    totalHours
  }
}
```

| Expected                                        |
|-------------------------------------------------|
| Returns only submissions with status "Submitted"|

☐ Pass / ☐ Fail — Notes: _______________

**List All Submissions with Period Filter**

```graphql
query {
  listAllSubmissions(filter: { periodId: "<PERIOD_ID>" }) {
    submissionId
    employeeId
    status
    totalHours
  }
}
```

| Expected                                          |
|---------------------------------------------------|
| Returns only submissions for the specified period |

☐ Pass / ☐ Fail — Notes: _______________

**Validation: Regular user calling listAllSubmissions should fail**

> Log in as a regular `user` (not admin/superadmin).

```graphql
query {
  listAllSubmissions {
    submissionId
  }
}
```

| Expected                    |
|-----------------------------|
| Error: permissions/forbidden|

☐ Pass / ☐ Fail — Notes: _______________

---

### 6.7 Timesheet Entries

> **Prerequisite:** The project referenced by `projectCode` must have `approval_status = Approved` (see Step 6.4 Approve Project). You need a Draft submission to add entries to.

**Add Entry**

```graphql
mutation {
  addTimesheetEntry(
    submissionId: "<SUBMISSION_ID>"
    input: {
      projectCode: "PRJ-001"
      saturday: 0
      sunday: 0
      monday: 8
      tuesday: 8
      wednesday: 8
      thursday: 8
      friday: 8
    }
  ) {
    entryId
    submissionId
    projectCode
    totalHours
  }
}
```

| Field      | Expected |
|------------|----------|
| totalHours | 40       |

☐ Pass / ☐ Fail — Notes: _______________

**Update Entry**

```graphql
mutation {
  updateTimesheetEntry(
    entryId: "<ENTRY_ID>"
    input: {
      projectCode: "PRJ-001"
      saturday: 0
      sunday: 0
      monday: 7.5
      tuesday: 7.5
      wednesday: 7.5
      thursday: 7.5
      friday: 7.5
    }
  ) {
    entryId
    totalHours
  }
}
```

| Field      | Expected |
|------------|----------|
| totalHours | 37.5     |

☐ Pass / ☐ Fail — Notes: _______________

**Remove Entry**

```graphql
mutation {
  removeTimesheetEntry(entryId: "<ENTRY_ID>")
}
```

| Expected      |
|---------------|
| Returns `true`|

☐ Pass / ☐ Fail — Notes: _______________

**Validation Tests (expected to fail with errors):**

| Test Case                        | Input                              | Expected Error                          |
|----------------------------------|------------------------------------|-----------------------------------------|
| Negative hours                   | `monday: -1`                       | "Daily hours must be non-negative"      |
| Unapproved project               | Use a non-approved project code    | "does not have approval_status"         |
| Exceed daily max (8h)            | `monday: 9`                        | "exceeds the maximum of 8"             |
| Exceed weekly max (40h)          | Multiple entries totaling >40h     | "exceeds the maximum of 40"            |
| Max entries per submission (27)  | Add 28th entry                     | "Maximum allowed is 27"                |
| Non-editable submission          | Add entry to Submitted submission  | "Cannot modify entries"                |

---

### 6.8 Automated Flows

These are EventBridge-triggered Lambdas. They cannot be tested via AppSync directly. Test them via the AWS Console.

#### Auto-Provisioning (Monday)

**How to test:**
1. Go to AWS Console → Lambda → `TimesheetAutoProvisioning-dev`
2. Click **Test** → create a test event with `{}` as the payload
3. Click **Test** to invoke

| Expected                                                    |
|-------------------------------------------------------------|
| New period created for current week (Mon-Fri)               |
| Draft submissions created for all Employee-role users       |
| Response: `{"created": true, "periodId": "...", "submissionsCreated": N}` |

☐ Pass / ☐ Fail — Notes: _______________

#### Deadline Reminder (Friday 1PM MYT)

**How to test:**
1. Go to AWS Console → Lambda → `TimesheetDeadlineReminder-dev`
2. Click **Test** → create a test event with `{}` as the payload
3. Click **Test** to invoke

| Expected                                                    |
|-------------------------------------------------------------|
| Reminder emails sent to employees with Draft submissions    |
| Response: `{"reminders_sent": N}`                           |

> **Note:** Requires SES to be configured and email addresses verified in sandbox mode.

☐ Pass / ☐ Fail — Notes: _______________

#### Deadline Enforcement (Friday 5PM MYT)

**How to test:**
1. Go to AWS Console → Lambda → `TimesheetDeadlineEnforcement-dev`
2. Click **Test** → create a test event with `{}` as the payload
3. Click **Test** to invoke

| Expected                                                    |
|-------------------------------------------------------------|
| All Draft submissions auto-submitted (Draft → Submitted)    |
| Missing submissions created as Submitted with 0 hours       |
| Under-40-hours email sent to employees below 40h            |
| Period marked as isLocked = true                            |
| Response: `{"submittedPeriods": N}`                         |

☐ Pass / ☐ Fail — Notes: _______________

**Verify after deadline enforcement:**

```graphql
query {
  listMySubmissions(filter: { status: Submitted }) {
    submissionId
    periodId
    status
    totalHours
  }
}
```

| Expected                                    |
|---------------------------------------------|
| Previously Draft submissions now Submitted  |

☐ Pass / ☐ Fail — Notes: _______________

---

### 6.9 Reports

**TC Summary Report**

```graphql
query {
  getTCSummaryReport(techLeadId: "<USER_ID>", periodId: "<PERIOD_ID>") {
    url
    expiresAt
  }
}
```

| Expected                              |
|---------------------------------------|
| Returns a pre-signed S3 URL           |

☐ Pass / ☐ Fail — Notes: _______________

**Project Summary Report**

```graphql
query {
  getProjectSummaryReport(periodId: "<PERIOD_ID>") {
    url
    expiresAt
  }
}
```

☐ Pass / ☐ Fail — Notes: _______________

---

### 6.10 Main Database

**List Main Database**

```graphql
query {
  listMainDatabase {
    recordId
    type
    chargeCode
    projectName
    budgetEffort
    projectStatus
  }
}
```

☐ Pass / ☐ Fail — Notes: _______________

**Update Record** (requires an existing record)

```graphql
mutation {
  updateMainDatabaseRecord(
    id: "<RECORD_ID>"
    input: { projectName: "Updated Project", budgetEffort: 1000.0 }
  ) {
    recordId
    projectName
    budgetEffort
  }
}
```

☐ Pass / ☐ Fail — Notes: _______________

**Bulk Import CSV**

> Upload a CSV file to S3 bucket `colabs-timesheet-reports-dev` first.

```graphql
mutation {
  bulkImportCSV(file: {
    bucket: "colabs-timesheet-reports-dev"
    key: "imports/test-data.csv"
  }) {
    totalRows
    successCount
    failureCount
    errors {
      row
      message
    }
  }
}
```

☐ Pass / ☐ Fail — Notes: _______________

**Refresh Database**

```graphql
mutation {
  refreshDatabase(file: {
    bucket: "colabs-timesheet-reports-dev"
    key: "imports/refresh-data.csv"
  }) {
    recordsImported
    previousRecordsRemoved
    timestamp
  }
}
```

☐ Pass / ☐ Fail — Notes: _______________

---

### 6.11 Report Distribution Config

**Get Config**

```graphql
query {
  getReportDistributionConfig {
    configId
    schedule_cron_expression
    recipient_emails
    enabled
  }
}
```

☐ Pass / ☐ Fail — Notes: _______________

**Update Config**

```graphql
mutation {
  updateReportDistributionConfig(input: {
    schedule_cron_expression: "cron(0 8 ? * MON *)"
    recipient_emails: ["<recipient-email-1>", "<recipient-email-2>"]
    enabled: true
  }) {
    configId
    schedule_cron_expression
    recipient_emails
    enabled
  }
}
```

☐ Pass / ☐ Fail — Notes: _______________

---

## 7. Troubleshooting

| Error                                    | Cause                                              | Fix                                                       |
|------------------------------------------|----------------------------------------------------|------------------------------------------------------------|
| "Access denied"                          | User missing `custom:userType` or wrong group      | Verify Cognito user attributes and group membership        |
| "Event is missing identity claims"       | Not authenticated in AppSync console               | Click "Login with User Pools" and re-authenticate          |
| "not found"                              | Referenced ID doesn't exist                        | Check ID Tracking Sheet, ensure prerequisite step was run  |
| "does not have approval_status"          | Project not approved yet                           | Run `approveProject` mutation first                        |
| "Cannot modify entries"                  | Submission not in Draft status                     | Submission was already auto-submitted; create a new period |
| "already in use"                         | Duplicate department/position name                 | Use a different name                                       |
| "startDate is not a Monday"             | Period start date is not Monday                    | Use a Monday date for startDate                            |
| "Only @axrail.com email addresses..."    | Email domain not allowed                           | Use an `@axrail.com` email address for user creation       |
| "exceeds the maximum of 8"              | Single day hours exceed 8h cap                     | Reduce hours for that day to 8 or below                    |
| "exceeds the maximum of 40"             | Weekly total hours exceed 40h cap                  | Reduce total weekly hours across all entries to 40 or below|
| "Only superadmins can edit projects..."  | Admin trying to edit an approved project           | Log in as superadmin, or edit a non-approved project       |
| Lambda timeout                           | Cold start or heavy operation                      | Retry — first invocation may be slow                       |
| SES email not sent                       | SES in sandbox mode                                | Verify sender and recipient emails in SES console          |

---

## 8. ID Tracking Sheet

Use this table to record IDs as you test. You will need these for subsequent steps.

| Resource              | ID Value | Notes          |
|-----------------------|----------|----------------|
| Department ID         |          |                |
| Department ID (spare) |          | For delete test|
| Position ID           |          |                |
| Position ID (spare)   |          | For delete test|
| User ID               |          |                |
| User ID (spare)       |          | For delete test|
| Project ID (approved) |          |                |
| Project ID (rejected) |          | For reject test|
| Period ID             |          |                |
| Submission ID         |          |                |
| Entry ID              |          |                |
| Main DB Record ID     |          |                |

---

**Tested By:** ________________________  
**Date:** ________________________  
**Environment:** ☐ dev  ☐ staging  ☐ prod  
**Overall Result:** ☐ All Passed  ☐ Partial  ☐ Failed  
**Notes:** ____________________________________________________________
