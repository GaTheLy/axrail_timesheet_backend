# Requirements Document

## Introduction

The Employee Timesheet Management System currently supports only a single `supervisorId` per user, meaning an employee can only be associated with one supervisor/tech lead. This limits the system when employees work across multiple projects with different tech leads. This feature introduces a many-to-many relationship between employees, projects, and supervisors via a new ProjectAssignments table, and updates all dependent components (TC Summary report, ListPendingTimesheets, notifications, GraphQL API) to use project-based assignments instead of the single `supervisorId` field.

## Glossary

- **Assignment_Service**: The backend component (Lambda resolvers and DynamoDB) responsible for creating, updating, deleting, and querying project assignments.
- **ProjectAssignment**: A record that maps an employee to a project and a supervisor (tech lead). Stored in the Timesheet_ProjectAssignments DynamoDB table.
- **TC_Summary_Generator**: The Lambda function that generates TC Summary CSV reports for a given tech lead and period.
- **Notification_Service**: The Lambda function that distributes automated reports via email on a schedule.
- **Review_Service**: The Lambda resolvers responsible for listing pending timesheets and approving/rejecting them.
- **Report_Resolver**: The AppSync resolver that returns pre-signed S3 URLs for TC Summary and Project Summary reports.
- **Users_Table**: The existing DynamoDB table storing user records, currently containing a single `supervisorId` attribute.
- **ProjectAssignments_Table**: A new DynamoDB table with partition key `assignmentId`, and GSIs on `employeeId`, `supervisorId`, and `projectId` to support efficient lookups.
- **Auto_Provisioning_Service**: The Lambda function triggered weekly to create timesheet periods and draft submissions.
- **Deadline_Enforcement_Service**: The Lambda function that auto-submits timesheets after the deadline.

## Requirements

### Requirement 1: ProjectAssignments Table

**User Story:** As a system administrator, I want a dedicated table to store employee-project-supervisor mappings, so that employees can be assigned to multiple projects with different supervisors.

#### Acceptance Criteria

1. THE Assignment_Service SHALL store each ProjectAssignment with a unique `assignmentId` (partition key), along with `employeeId`, `projectId`, `supervisorId`, `createdAt`, `createdBy`, `updatedAt`, and `updatedBy` attributes.
2. THE ProjectAssignments_Table SHALL provide a GSI named `employeeId-index` with partition key `employeeId` to support querying all assignments for a given employee.
3. THE ProjectAssignments_Table SHALL provide a GSI named `supervisorId-index` with partition key `supervisorId` to support querying all employees under a given supervisor.
4. THE ProjectAssignments_Table SHALL provide a GSI named `projectId-index` with partition key `projectId` to support querying all assignments for a given project.
5. THE ProjectAssignments_Table SHALL be defined in the DynamoDB CDK stack with PAY_PER_REQUEST billing mode and environment-suffixed table name following the pattern `Timesheet_ProjectAssignments-{env}`.
6. THE ProjectAssignments_Table table name and ARN SHALL be exported to SSM Parameter Store under the path `/timesheet/{env}/dynamodb/project_assignments/`.

### Requirement 2: GraphQL API for Project Assignments

**User Story:** As an admin, I want GraphQL mutations and queries to manage project assignments, so that I can assign employees to projects with specific supervisors through the API.

#### Acceptance Criteria

1. THE Assignment_Service SHALL expose a `createProjectAssignment` mutation that accepts `employeeId`, `projectId`, and `supervisorId` as required inputs and returns the created ProjectAssignment.
2. THE Assignment_Service SHALL expose an `updateProjectAssignment` mutation that accepts an `assignmentId` and optional `supervisorId` or `projectId` fields and returns the updated ProjectAssignment.
3. THE Assignment_Service SHALL expose a `deleteProjectAssignment` mutation that accepts an `assignmentId` and returns a boolean indicating success.
4. THE Assignment_Service SHALL expose a `listProjectAssignments` query that accepts optional filter parameters `employeeId`, `supervisorId`, and `projectId` and returns a list of ProjectAssignment records.
5. WHEN a `createProjectAssignment` mutation is received with an `employeeId` and `projectId` combination that already exists, THEN THE Assignment_Service SHALL return a descriptive error indicating the duplicate assignment.
6. WHEN a `createProjectAssignment` or `updateProjectAssignment` mutation references a non-existent `employeeId`, `projectId`, or `supervisorId`, THEN THE Assignment_Service SHALL return a descriptive validation error.
7. THE Assignment_Service SHALL restrict `createProjectAssignment`, `updateProjectAssignment`, and `deleteProjectAssignment` mutations to users with `superadmin` or `admin` userType.

### Requirement 3: TC Summary Report Update

**User Story:** As a tech lead, I want the TC Summary report to show all employees assigned to me via project assignments, so that I can see chargeability data for everyone I supervise across all projects.

#### Acceptance Criteria

1. WHEN generating a TC Summary report for a tech lead, THE TC_Summary_Generator SHALL query the ProjectAssignments_Table using the `supervisorId-index` GSI to find all employees assigned to the tech lead.
2. THE TC_Summary_Generator SHALL replace the existing `supervisorId-index` query on the Users_Table with the ProjectAssignments_Table query for determining supervised employees.
3. WHEN an employee is assigned to the same tech lead through multiple projects, THE TC_Summary_Generator SHALL include the employee only once in the TC Summary report.
4. WHEN a tech lead has no project assignments, THE TC_Summary_Generator SHALL return an empty report.

### Requirement 4: ListPendingTimesheets Update

**User Story:** As a tech lead or project manager, I want to see pending timesheets for all employees assigned to me via project assignments, so that I can review timesheets for everyone I supervise.

#### Acceptance Criteria

1. WHEN listing pending timesheets for a reviewer, THE Review_Service SHALL query the ProjectAssignments_Table using the `supervisorId-index` GSI to determine the set of supervised employee IDs.
2. THE Review_Service SHALL replace the existing `supervisorId-index` query on the Users_Table with the ProjectAssignments_Table query in the ListPendingTimesheets resolver.
3. WHEN an employee is assigned to the reviewer through multiple projects, THE Review_Service SHALL include each pending timesheet for that employee only once in the results.

### Requirement 5: Notification Service Update

**User Story:** As a tech lead, I want the automated TC Summary email to include all employees assigned to me via project assignments, so that the emailed report matches the on-demand report.

#### Acceptance Criteria

1. WHEN generating TC Summary CSV for email distribution, THE Notification_Service SHALL query the ProjectAssignments_Table using the `supervisorId-index` GSI to find supervised employees.
2. THE Notification_Service SHALL replace the existing `supervisorId-index` query on the Users_Table with the ProjectAssignments_Table query for determining supervised employees.
3. WHEN a tech lead has no project assignments, THE Notification_Service SHALL skip sending a TC Summary email to that tech lead.

### Requirement 6: Stream-Triggered Report Generation Update

**User Story:** As a system operator, I want the DynamoDB Stream-triggered report generation to use project assignments, so that TC Summary reports are generated for the correct supervisors when a timesheet is submitted.

#### Acceptance Criteria

1. WHEN a timesheet submission status changes to Submitted, THE TC_Summary_Generator SHALL query the ProjectAssignments_Table using the `employeeId-index` GSI to find all supervisors assigned to the submitting employee.
2. THE TC_Summary_Generator SHALL generate a TC Summary report for each distinct supervisor found in the employee's project assignments.
3. THE TC_Summary_Generator SHALL replace the existing single `supervisorId` lookup on the Users_Table with the ProjectAssignments_Table query for determining which supervisors need report regeneration.

### Requirement 7: Backward Compatibility and Migration

**User Story:** As a system administrator, I want existing supervisor relationships to be migrated to the new ProjectAssignments table, so that the transition does not break existing functionality.

#### Acceptance Criteria

1. THE Assignment_Service SHALL retain the existing `supervisorId` field on the Users_Table as a deprecated attribute during the migration period.
2. WHEN the system reads supervisor relationships, THE Assignment_Service SHALL read from the ProjectAssignments_Table as the primary source.
3. THE GraphQL schema SHALL retain the `supervisorId` field on the User type and input types as an optional deprecated field.
4. THE `createUser` and `updateUser` mutations SHALL continue to accept `supervisorId` as an optional input without error.

### Requirement 8: CDK Infrastructure

**User Story:** As a DevOps engineer, I want the CDK stack to provision the new ProjectAssignments table and grant Lambda functions the required permissions, so that the feature is deployable through the existing CI/CD pipeline.

#### Acceptance Criteria

1. THE DynamoDB CDK stack SHALL create the ProjectAssignments_Table with the partition key, GSIs, and SSM exports defined in Requirement 1.
2. THE Lambda CDK stack SHALL grant read and write permissions on the ProjectAssignments_Table to all Lambda functions that manage or query project assignments.
3. THE Lambda CDK stack SHALL pass the ProjectAssignments_Table name as an environment variable `PROJECT_ASSIGNMENTS_TABLE` to all Lambda functions that require access.
4. THE CDK stack SHALL register the `project_assignments` table name in the `TIMESHEET_TABLE_NAMES` dictionary in `environment.py`.
