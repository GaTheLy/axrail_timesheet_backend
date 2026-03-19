# Requirements Document

## Introduction

The Employee Timesheet Management System replaces the existing Google Sheets and Apps Script-based timesheet workflow with a full-stack web application built on AWS. The system enables employees to fill weekly timesheets (Monday through Friday), with automatic submission at the Friday 5PM MYT deadline. The system generates performance and project utilization reports. The system supports a biweekly reporting cycle with automated archival and email distribution of summary reports.

## Glossary

- **Timesheet_System**: The overall Employee Timesheet Management web application, including frontend and backend components
- **Auth_Service**: The authentication and authorization module powered by AWS Cognito, responsible for user login, session management, and role-based access control
- **Timesheet_API**: The AWS AppSync GraphQL API layer that handles all data operations between the frontend and the database
- **Timesheet_Database**: The set of DynamoDB tables storing all persistent data (users, projects, timesheet entries, periods, performance records)
- **Report_Generator**: The backend service (AWS Lambda) responsible for computing and producing TC Summary and Project Summary reports
- **Notification_Service**: The backend service (AWS Lambda + SES) responsible for sending scheduled email notifications with reports
- **Employee**: A user with the "user" user type and "Employee" role who fills timesheets
- **Project_Manager**: A user with the "admin" user type and "Project Manager" role who manages projects
- **Tech_Lead**: A user with the "admin" user type and "Tech Lead" role who receives TC Summary reports
- **Superadmin**: A user with the "superadmin" user type who has full system access including user and department management
- **Biweekly_Period**: A 14-day reporting cycle used for report generation and timesheet archival
- **Submission_Status**: One of Draft or Submitted
- **Approval_Status**: One of Pending_Approval, Approved, or Rejected — used for project creation requests by Admin users
- **Report_Distribution_Config**: The configurable settings for automated report delivery, including schedule_cron_expression, recipient_emails, and enabled flag
- **Chargeability_Percentage**: The ratio of chargeable hours to total hours, expressed as a percentage
- **Period_String**: A human-readable label identifying a specific timesheet period (e.g., "2025-01-06 to 2025-01-10")
- **Charged_Hours**: The number of hours an Employee records against a specific project on a specific day, stored as a float using dot notation (e.g., 1.5)

## Requirements

### Requirement 1: User Authentication and Authorization

**User Story:** As a system user, I want to securely log in and access only the features permitted by my role, so that the system remains secure and each user sees relevant functionality.

#### Acceptance Criteria

1. WHEN a user provides valid credentials, THE Auth_Service SHALL authenticate the user and return a session token
2. WHEN a user provides invalid credentials, THE Auth_Service SHALL reject the login attempt and display an error message indicating invalid credentials
3. WHILE a user is authenticated, THE Auth_Service SHALL enforce role-based access control based on the user's user type (superadmin, admin, user) and role (Project_Manager, Tech_Lead, Employee)
4. WHEN an authenticated session expires, THE Auth_Service SHALL require the user to re-authenticate before accessing protected resources
5. IF an authenticated user attempts to access a resource outside the user's permitted scope, THEN THE Auth_Service SHALL deny access and return a forbidden error


### Requirement 2: User Management

**User Story:** As a Superadmin or Admin, I want to manage user accounts within my permitted scope, so that the organization's workforce is accurately represented in the system.

#### Acceptance Criteria

1. WHEN a Superadmin submits a new admin user form with fullName, email, role, positionId, and departmentId, THE Timesheet_API SHALL create a new admin user record in the Timesheet_Database
2. WHEN a Superadmin updates an existing admin user's details, THE Timesheet_API SHALL persist the changes and record the updatedBy and updatedAt fields
3. WHEN a Superadmin deletes an admin user, THE Timesheet_API SHALL remove the admin user record and record the deletion with a timestamp and the Superadmin's userId
4. WHEN an Admin submits a new user (Employee) form with fullName, email, role, positionId, and departmentId, THE Timesheet_API SHALL create a new user record in the Timesheet_Database
5. WHEN an Admin updates an existing user (Employee) details, THE Timesheet_API SHALL persist the changes and record the updatedBy and updatedAt fields
6. WHEN an Admin deletes a user (Employee), THE Timesheet_API SHALL remove the user record and record the deletion with a timestamp and the Admin's userId
7. IF an Admin attempts to create, update, or delete an admin or superadmin account, THEN THE Timesheet_API SHALL reject the operation and return a forbidden error
8. THE Timesheet_API SHALL enforce email uniqueness across all user records
9. WHEN a user account is created, THE Timesheet_API SHALL validate that the role is one of Project_Manager, Tech_Lead, or Employee
10. WHEN a user account is created, THE Timesheet_API SHALL validate that the user type is one of superadmin, admin, or user
11. WHEN a user account is created, THE Timesheet_API SHALL set the user's status to active by default
12. WHEN a Superadmin or Admin deactivates a user, THE Timesheet_API SHALL set the user's status to inactive, disable the Cognito account, and retain all user data for historical queries
13. WHEN a Superadmin or Admin activates a previously deactivated user, THE Timesheet_API SHALL set the user's status to active and re-enable the Cognito account
14. WHILE a user has status of inactive, THE Timesheet_System SHALL exclude the user from auto-provisioning, deadline enforcement, and deadline reminders
15. THE Timesheet_API SHALL support filtering users by status (active/inactive) in the listUsers query

### Requirement 3: Department and Position Management

**User Story:** As a Superadmin, I want to manage departments and positions, so that organizational structure is maintained and users can be properly categorized.

#### Acceptance Criteria

1. WHEN a Superadmin creates a new department with a departmentName, THE Timesheet_API SHALL store the department record with createdAt and createdBy fields
2. WHEN a Superadmin creates a new position with positionName and description, THE Timesheet_API SHALL store the position record with createdAt and createdBy fields
3. THE Timesheet_API SHALL enforce unique department names across all department records
4. THE Timesheet_API SHALL enforce unique position names across all position records
5. IF a Superadmin attempts to delete a department that has associated users, THEN THE Timesheet_API SHALL reject the deletion and return an error indicating active associations exist
6. IF a non-Superadmin user attempts to create, update, or delete a department or position, THEN THE Timesheet_API SHALL reject the operation and return a forbidden error

### Requirement 4: Project Management

**User Story:** As a Superadmin or Admin, I want to create and manage projects with charge codes, planned hours, and assigned managers, so that employees can log time against valid projects.

#### Acceptance Criteria

1. WHEN a Superadmin submits a new project with projectCode, projectName, startDate, plannedHours, and projectManagerId, THE Timesheet_API SHALL create the project record directly in the Timesheet_Database
2. WHEN an Admin submits a new project request with projectCode, projectName, startDate, plannedHours, and projectManagerId, THE Timesheet_API SHALL create a project record with approval_status set to Pending_Approval
3. WHEN a Superadmin approves a Pending_Approval project, THE Timesheet_API SHALL update the approval_status to Approved and make the project available for timesheet entries
4. WHEN a Superadmin rejects a Pending_Approval project, THE Timesheet_API SHALL update the approval_status to Rejected and record the rejection reason
5. IF an Employee attempts to log time against a project that does not have approval_status of Approved, THEN THE Timesheet_API SHALL reject the timesheet entry
6. THE Timesheet_API SHALL enforce unique projectCode values across all project records
7. WHEN a Superadmin or Admin updates a project's status, THE Timesheet_API SHALL persist the new status and record updatedBy and updatedAt fields
8. THE Timesheet_API SHALL validate that plannedHours is a positive float value using dot notation
9. WHEN a Superadmin or Admin retrieves the project list, THE Timesheet_API SHALL return all projects with their current status, approval_status, planned hours, and assigned Project_Manager

### Requirement 5: Timesheet Period Management

**User Story:** As a system, I want to automatically create weekly timesheet periods (Monday through Friday) with auto-computed submission deadlines, so that employees have structured weekly cycles.

#### Acceptance Criteria

1. WHEN the auto-provisioning Lambda runs on Monday, THE Timesheet_System SHALL create a new timesheet period with startDate (Monday), endDate (Friday), auto-computed submissionDeadline (Friday 5PM MYT), and periodString
2. THE Timesheet_API SHALL validate that startDate falls on a Monday and endDate falls on a Friday for each timesheet period
3. THE Timesheet_API SHALL validate that endDate is exactly 4 days after startDate for each timesheet period
4. THE Timesheet_API SHALL auto-compute the submissionDeadline as endDate (Friday) at 5PM MYT (09:00 UTC)
5. THE Timesheet_API SHALL enforce that no two timesheet periods have overlapping date ranges

### Requirement 6: Timesheet Submission

**User Story:** As an Employee, I want to fill my weekly timesheet by selecting projects and entering daily charged hours (Monday through Friday), so that my work effort is recorded accurately.

#### Acceptance Criteria

1. WHEN the auto-provisioning Lambda runs on Monday, THE Timesheet_System SHALL create a Draft submission for each Employee for the new period
2. WHEN an Employee adds a timesheet entry, THE Timesheet_API SHALL validate that the projectCode references an existing active project with approval_status of Approved
3. THE Timesheet_API SHALL store all Charged_Hours values as float numbers using dot notation (e.g., 1.5)
4. WHILE a timesheet submission has Submission_Status of Draft, THE Timesheet_System SHALL allow the Employee to add, edit, and remove timesheet entries
5. WHILE a timesheet submission has Submission_Status of Submitted, THE Timesheet_System SHALL prevent the Employee from editing timesheet entries
6. THE Timesheet_API SHALL allow a maximum of 27 project entries per timesheet submission
7. WHEN an Employee saves a timesheet entry, THE Timesheet_API SHALL compute and store the total hours as the sum of all daily Charged_Hours for that entry
8. WHEN an Employee views timesheet data, THE Timesheet_API SHALL return only the submissions and entries belonging to that Employee
9. IF an Employee attempts to view or access another Employee's timesheet data, THEN THE Timesheet_API SHALL reject the request and return a forbidden error

### Requirement 7: Automatic Submission at Deadline

**User Story:** As a system, I want timesheets to be automatically submitted when the Friday 5PM MYT deadline passes, so that all employee hours are captured regardless of manual action.

#### Acceptance Criteria

1. WHEN the submissionDeadline for a timesheet period passes, THE Timesheet_System SHALL update all timesheet submissions for that period with Submission_Status of Draft to Submitted
2. WHILE a timesheet submission has Submission_Status of Submitted, THE Timesheet_System SHALL prevent the Employee from editing the timesheet
3. IF an Employee attempts to modify a timesheet entry belonging to a Submitted submission, THEN THE Timesheet_API SHALL reject the modification and return an error indicating the submission is submitted
4. WHEN the submissionDeadline passes and an Employee has no submission for that period, THE Timesheet_System SHALL create a submission record with Submission_Status of Submitted and zero Charged_Hours
5. WHEN the deadline enforcement runs, THE Timesheet_System SHALL mark the period as isLocked = true
6. WHEN a submission is auto-submitted with less than 40 total hours, THE Timesheet_System SHALL send an under-40-hours notification email to the Employee only

### Requirement 8: Deadline Reminder

**User Story:** As an Employee, I want to receive a reminder email before the submission deadline, so that I can complete my timesheet on time.

#### Acceptance Criteria

1. THE Timesheet_System SHALL send a reminder email to all Employees with Draft submissions 4 hours before the deadline (Friday 1PM MYT = 05:00 UTC)
2. THE reminder email SHALL include the period string and a prompt to complete the timesheet

### Requirement 9: TC Summary Report Generation

**User Story:** As a Tech_Lead, I want the TC Summary Report to be automatically generated and kept in sync based on timesheet submission events, so that I always have up-to-date team chargeability data.

#### Acceptance Criteria

1. WHEN a timesheet submission transitions to Submitted status, THE Report_Generator SHALL automatically recompute the TC Summary Report for the affected team lead and period
2. THE Report_Generator SHALL compute the TC Summary Report containing: employee name, chargeable hours, total hours, current period Chargeability_Percentage, and YTD Chargeability_Percentage for each team member under the selected team lead
3. THE Report_Generator SHALL calculate current period Chargeability_Percentage as (chargeable hours / total hours) * 100 for each employee
4. THE Report_Generator SHALL calculate YTD Chargeability_Percentage using the ytdChargable_hours and ytdTotalHours from the Employee_Performance record
5. THE Report_Generator SHALL include only employees with Submitted timesheet submissions for the selected period
6. THE Report_Generator SHALL format the TC Summary Report as a downloadable CSV file with columns: Name, Chargable Hours, Total Hours, Current Period Chargability, YTD Chargability
7. WHEN a Tech_Lead or Project_Manager requests a TC Summary Report, THE Timesheet_API SHALL return the most recently computed report for the selected team lead and period

### Requirement 10: Project Summary Report Generation

**User Story:** As a Project_Manager, I want the Project Summary Report to be automatically generated and kept in sync based on timesheet submission events, so that I always have up-to-date project utilization data.

#### Acceptance Criteria

1. WHEN a timesheet submission transitions to Submitted status, THE Report_Generator SHALL automatically recompute the Project Summary Report for the affected projects and period
2. THE Report_Generator SHALL compute the Project Summary Report containing: projectCode, projectName, plannedHours, charged hours, utilization percentage, and current biweekly effort for each project
3. THE Report_Generator SHALL calculate utilization as (total charged hours / plannedHours) * 100 for each project
4. THE Report_Generator SHALL calculate current biweekly effort as the sum of all Charged_Hours from Submitted submissions in the current Biweekly_Period for each project
5. THE Report_Generator SHALL format the Project Summary Report as a downloadable CSV file with columns: Project Charge Code, Project Name, Planned Hours, Charged Hours, Utilization, Current Biweekly Effort
6. THE Report_Generator SHALL include all projects regardless of status in the Project Summary Report
7. WHEN a Project_Manager or Tech_Lead requests a Project Summary Report, THE Timesheet_API SHALL return the most recently computed report for the selected period

### Requirement 11: Employee Performance Tracking

**User Story:** As a Tech_Lead, I want the system to maintain year-to-date performance records for each employee, so that chargeability trends can be tracked over time.

#### Acceptance Criteria

1. WHEN a timesheet submission transitions to Submitted status, THE Timesheet_API SHALL update the Employee_Performance record for the corresponding employee and year by adding the Charged_Hours to ytdChargable_hours and total hours to ytdTotalHours
2. THE Timesheet_API SHALL recalculate ytdChargabilityPercentage as (ytdChargable_hours / ytdTotalHours) * 100 each time the Employee_Performance record is updated
3. IF no Employee_Performance record exists for the employee and current year, THEN THE Timesheet_API SHALL create a new record with initial values of zero before applying the update
4. THE Timesheet_API SHALL store one Employee_Performance record per employee per year, using userId and year as the composite primary key

### Requirement 12: Configurable Automated Report Distribution

**User Story:** As a Superadmin, I want to configure the automated report distribution schedule, delivery time, and email recipients, so that reports reach the right people at the right time without manual effort.

#### Acceptance Criteria

1. WHEN the configured report distribution schedule triggers (via EventBridge rule), THE Notification_Service SHALL generate a Project Summary Report and send the report via email to the configured recipient list
2. WHEN the configured report distribution schedule triggers, THE Notification_Service SHALL generate a TC Summary Report for each Tech_Lead and send the corresponding report via email to that Tech_Lead
3. THE Notification_Service SHALL attach the generated reports as CSV files to the email notifications
4. WHEN a Superadmin updates the report distribution configuration, THE Timesheet_API SHALL persist the new schedule time, frequency, and recipient email list
5. THE Timesheet_System SHALL store the report distribution configuration including: schedule_cron_expression, recipient_emails, and enabled flag
6. IF the Notification_Service fails to send an email, THEN THE Notification_Service SHALL log the failure with the recipient email, report type, and error details for retry
7. THE Timesheet_System SHALL allow the Superadmin to enable or disable the automated report distribution without deleting the configuration

### Requirement 13: Biweekly Timesheet Archival

**User Story:** As a Superadmin, I want all timesheets from the current biweekly period to be automatically archived when the period ends, so that historical data is preserved and the active workspace remains clean.

#### Acceptance Criteria

1. WHEN a Biweekly_Period ends, THE Timesheet_System SHALL mark all timesheet submissions for that period as archived in the Timesheet_Database
2. WHEN a timesheet submission is archived, THE Timesheet_System SHALL retain all associated timesheet entries and submission metadata for historical queries
3. WHEN a user queries archived timesheets, THE Timesheet_API SHALL return the archived submissions with a read-only indicator
4. THE Timesheet_System SHALL execute the archival process after the report distribution process completes for the same Biweekly_Period

### Requirement 14: Main Database Management

**User Story:** As a Project_Manager or Superadmin, I want to view and manage the main timesheet database, so that I can correct data errors and maintain data integrity across all submissions.

#### Acceptance Criteria

1. WHEN a Project_Manager or Superadmin accesses the main database view, THE Timesheet_API SHALL return all timesheet records with fields: type, charge code, project name, budget effort, and project status
2. WHEN a Superadmin updates a record in the main database, THE Timesheet_API SHALL persist the changes and record the updatedBy and updatedAt fields
3. WHEN a Superadmin performs a bulk import from a CSV file, THE Timesheet_API SHALL validate each row against the expected schema (type, value, project_name, budget_effort, project_status) before persisting
4. IF a CSV row fails validation during bulk import, THEN THE Timesheet_API SHALL reject that row, include the row number and error detail in the response, and continue processing remaining rows
5. WHEN a Superadmin triggers a database refresh, THE Timesheet_API SHALL replace the existing main database records with the imported data and log the operation with a timestamp and the userId of the Superadmin

### Requirement 15: Timesheet Entry Data Validation

**User Story:** As an Employee, I want the system to validate my timesheet entries in real time, so that I avoid submitting incorrect or incomplete data.

#### Acceptance Criteria

1. THE Timesheet_API SHALL validate that each daily Charged_Hours value is a non-negative float with a maximum of two decimal places
2. THE Timesheet_API SHALL validate that the total Charged_Hours per day across all project entries does not exceed 24.0 hours
3. IF an Employee submits a timesheet entry with a Charged_Hours value that fails validation, THEN THE Timesheet_API SHALL reject the entry and return a specific error message indicating the validation failure
4. THE Timesheet_API SHALL validate that each timesheet entry references a valid and active projectCode before saving
5. WHEN an Employee saves a timesheet entry with daily hours for Saturday through Friday, THE Timesheet_API SHALL compute the row total as the sum of the seven daily values and store the result as a float using dot notation
