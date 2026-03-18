# AppSync Backend Testing Guide

## Employee Timesheet Management System

**Project:** COLABS Timesheet System  
**API:** TimesheetGraphQLApi (AWS AppSync)  
**Auth:** Amazon Cognito User Pool  
**Date:** March 2026

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Test User Setup](#2-test-user-setup)
3. [Accessing the AppSync Console](#3-accessing-the-appsync-console)
4. [Test Execution Order](#4-test-execution-order)
5. [Test Cases](#5-test-cases)
   - 5.1 [Departments](#51-departments)
   - 5.2 [Positions](#52-positions)
   - 5.3 [Users](#53-users)
   - 5.4 [Projects](#54-projects)
   - 5.5 [Timesheet Periods](#55-timesheet-periods)
   - 5.6 [Timesheet Submissions](#56-timesheet-submissions)
   - 5.7 [Timesheet Entries](#57-timesheet-entries)
   - 5.8 [Submit & Review Flow](#58-submit--review-flow)
   - 5.9 [Reports](#59-reports)
   - 5.10 [Main Database](#510-main-database)
   - 5.11 [Report Distribution Config](#511-report-distribution-config)
6. [Troubleshooting](#6-troubleshooting)
7. [ID Tracking Sheet](#7-id-tracking-sheet)

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

## 4. Test Execution Order

Tests must be run in this order because later tests depend on IDs created by earlier ones.

| Step | Component              | Creates IDs Needed By         |
|------|------------------------|-------------------------------|
| 1    | Departments            | Users                         |
| 2    | Positions              | Users                         |
| 3    | Users                  | Projects, Submissions         |
| 4    | Projects               | Timesheet Entries             |
| 5    | Timesheet Periods      | Submissions                   |
| 6    | Timesheet Submissions  | Entries, Submit/Review        |
| 7    | Timesheet Entries      | Submit/Review                 |
| 8    | Submit & Review Flow   | Reports                       |
| 9    | Reports                | —                             |
| 10   | Main Database          | —                             |
| 11   | Report Distribution    | —                             |

> **Important:** Record every ID returned from create mutations in the ID Tracking Sheet (Section 7).

---

## 5. Test Cases

### 5.1 Departments

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

### 5.2 Positions

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

### 5.3 Users

**Create User** (requires departmentId and positionId from previous steps)

```graphql
mutation {
  createUser(input: {
    email: "<test-user-email>"
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

---

### 5.4 Projects

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

**Update Project**

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

---

### 5.5 Timesheet Periods

**Create Timesheet Period**

```graphql
mutation {
  createTimesheetPeriod(input: {
    startDate: "2026-03-14"
    endDate: "2026-03-27"
    submissionDeadline: "2026-03-28T23:59:59Z"
    periodString: "Mar 14 - Mar 27, 2026"
    biweeklyPeriodId: "2026-W12"
  }) {
    periodId
    startDate
    endDate
    isLocked
  }
}
```

| Field    | Expected |
|----------|----------|
| isLocked | false    |

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
    input: { submissionDeadline: "2026-03-29T23:59:59Z" }
  ) {
    periodId
    submissionDeadline
  }
}
```

☐ Pass / ☐ Fail — Notes: _______________

---

### 5.6 Timesheet Submissions

**Create Submission** (requires a valid periodId)

```graphql
mutation {
  createTimesheetSubmission(periodId: "<PERIOD_ID>") {
    submissionId
    periodId
    employeeId
    status
    totalHours
  }
}
```

| Field  | Expected |
|--------|----------|
| status | "Draft"  |

☐ Pass / ☐ Fail — Notes: _______________

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

---

### 5.7 Timesheet Entries

> **Prerequisite:** The project referenced by `projectCode` must have `approval_status = Approved` (see Step 5.4 Approve Project).

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
| Exceed daily max (24h)           | `monday: 25`                       | "exceeds the maximum of 24"            |
| Max entries per submission (27)  | Add 28th entry                     | "Maximum allowed is 27"                |
| Non-editable submission          | Add entry to Submitted submission  | "Cannot modify entries"                |

---

### 5.8 Submit & Review Flow

> **Note:** Re-add an entry before submitting if you removed it in the previous step.

**Submit Timesheet**

```graphql
mutation {
  submitTimesheet(submissionId: "<SUBMISSION_ID>") {
    submissionId
    status
  }
}
```

| Field  | Expected    |
|--------|-------------|
| status | "Submitted" |

☐ Pass / ☐ Fail — Notes: _______________

**List Pending Timesheets** (for reviewers/supervisors)

```graphql
query {
  listPendingTimesheets {
    submissionId
    employeeId
    status
    totalHours
  }
}
```

☐ Pass / ☐ Fail — Notes: _______________

**Approve Timesheet**

```graphql
mutation {
  approveTimesheet(submissionId: "<SUBMISSION_ID>") {
    submissionId
    status
    approvedBy
    approvedAt
  }
}
```

| Field      | Expected   |
|------------|------------|
| status     | "Approved" |
| approvedBy | Your userId|
| approvedAt | Timestamp  |

☐ Pass / ☐ Fail — Notes: _______________

**Reject Timesheet** (create a new submission and submit it first)

```graphql
mutation {
  rejectTimesheet(submissionId: "<SUBMISSION_ID>") {
    submissionId
    status
  }
}
```

| Field  | Expected   |
|--------|------------|
| status | "Rejected" |

☐ Pass / ☐ Fail — Notes: _______________

---

### 5.9 Reports

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

### 5.10 Main Database

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

### 5.11 Report Distribution Config

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

## 6. Troubleshooting

| Error                                    | Cause                                              | Fix                                                       |
|------------------------------------------|----------------------------------------------------|------------------------------------------------------------|
| "Access denied"                          | User missing `custom:userType` or wrong group      | Verify Cognito user attributes and group membership        |
| "Event is missing identity claims"       | Not authenticated in AppSync console               | Click "Login with User Pools" and re-authenticate          |
| "not found"                              | Referenced ID doesn't exist                        | Check ID Tracking Sheet, ensure prerequisite step was run  |
| "does not have approval_status"          | Project not approved yet                           | Run `approveProject` mutation first                        |
| "Cannot modify entries"                  | Submission not in Draft/Rejected status            | Create a new submission or reject the current one          |
| "already in use"                         | Duplicate department/position name                 | Use a different name                                       |
| Lambda timeout                           | Cold start or heavy operation                      | Retry — first invocation may be slow                       |

---

## 7. ID Tracking Sheet

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
| Submission ID (spare) |          | For reject test|
| Entry ID              |          |                |
| Main DB Record ID     |          |                |

---

**Tested By:** ________________________  
**Date:** ________________________  
**Environment:** ☐ dev  ☐ staging  ☐ prod  
**Overall Result:** ☐ All Passed  ☐ Partial  ☐ Failed  
**Notes:** ____________________________________________________________
