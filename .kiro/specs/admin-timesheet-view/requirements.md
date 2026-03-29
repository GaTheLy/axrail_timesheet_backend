# Requirements Document

## Introduction

This feature revises the admin and superadmin experience in the TimeFlow platform by removing their ability to submit personal timesheets and replacing the Timesheet page with a read-only view of all employee timesheet submissions. Currently, admin and superadmin users can hold positions (Employee, Tech Lead, Project Manager) and submit their own timesheets like regular employees. After this change, admin and superadmin users will no longer have any position assignment, will not have Draft submissions auto-created for them, and their Timesheet page will display a "Timesheet Submissions" overview showing other users' submissions with filtering and view capabilities.

## Glossary

- **Portal**: The TimeFlow web application front-end built with Laravel/Blade templates
- **Admin_User**: A user with userType `admin` who manages platform configuration, users, and projects
- **Super_Admin**: A user with userType `superadmin` who has full system access including admin management
- **Employee**: A user with userType `user` and role `Employee` who logs time entries against assigned projects
- **API_Service**: The AWS AppSync GraphQL API that serves as the backend data layer
- **Timesheet_Page**: The page accessible via the "Timesheet" sidebar link; renders differently based on user role
- **Submissions_View**: The admin/superadmin version of the Timesheet_Page displaying all employee timesheet submissions in a filterable table
- **Submission_Record**: A timesheet submission record containing entries for a specific period and employee, with fields including week period, user name, total hours, and status
- **Auto_Provisioning_Lambda**: The scheduled Lambda function that runs every Monday to create timesheet periods and Draft submissions for employees
- **Deadline_Enforcement_Lambda**: The scheduled Lambda function that runs every Friday at 5PM MYT to auto-submit Draft timesheets and create zero-hour submissions for employees without one
- **Submission_Status**: One of Draft or Submitted
- **View_Action**: A read-only action allowing the admin or superadmin to inspect the details of a specific employee's timesheet submission

## Requirements

### Requirement 1: Remove Position Assignment for Admin and Superadmin Users

**User Story:** As a system operator, I want admin and superadmin users to have no position (Employee/Tech Lead/PM), so that they are clearly separated from the employee timesheet workflow.

#### Acceptance Criteria

1. WHEN a Super_Admin creates a new admin user, THE API_Service SHALL not require a positionId field for users with userType `admin` or `superadmin`
2. WHEN a Super_Admin creates a new admin user, THE API_Service SHALL not require a role field value of Employee, Tech_Lead, or Project_Manager for users with userType `admin` or `superadmin`
3. THE Portal SHALL not display the Position dropdown in the User Creation Form when the selected user type is `admin`
4. THE Portal SHALL not display the Role dropdown in the User Creation Form when the selected user type is `admin`

### Requirement 2: Exclude Admin and Superadmin from Timesheet Submission Workflow

**User Story:** As a system operator, I want admin and superadmin users excluded from the timesheet submission workflow, so that they do not receive Draft submissions or deadline enforcement actions.

#### Acceptance Criteria

1. WHEN the Auto_Provisioning_Lambda creates Draft submissions on Monday, THE Auto_Provisioning_Lambda SHALL skip users with userType `admin` or `superadmin`
2. WHEN the Deadline_Enforcement_Lambda processes submissions on Friday, THE Deadline_Enforcement_Lambda SHALL skip creating zero-hour Submitted submissions for users with userType `admin` or `superadmin`
3. WHEN the Deadline_Enforcement_Lambda sends under-40-hours notification emails, THE Deadline_Enforcement_Lambda SHALL skip users with userType `admin` or `superadmin`
4. WHEN the deadline reminder Lambda sends reminder emails, THE deadline reminder Lambda SHALL skip users with userType `admin` or `superadmin`

### Requirement 3: Admin and Superadmin Timesheet Submissions View

**User Story:** As an Admin_User or Super_Admin, I want to see a "Timesheet Submissions" page when I click the Timesheet sidebar link, so that I can review all employee timesheet submissions.

#### Acceptance Criteria

1. WHEN an Admin_User or Super_Admin navigates to the Timesheet_Page, THE Portal SHALL render the Submissions_View instead of the employee timesheet entry form
2. THE Submissions_View SHALL display the page title "Timesheet Submissions"
3. WHEN the Submissions_View loads, THE Portal SHALL query the API_Service using `listAllSubmissions` to retrieve all employee submissions
4. WHEN the Submissions_View loads, THE Portal SHALL query the API_Service using `listUsers` to resolve employee names from employeeId values
5. THE Submissions_View SHALL display a data table with columns: Week Period, User Name, Total Hours, Status, and Actions
6. THE Submissions_View SHALL display the Submission_Status as a color-coded badge: green for "Approved" display label, red for "Rejected" display label
7. THE Submissions_View SHALL display a view icon (eye) in the Actions column for each Submission_Record
8. WHEN an Admin_User or Super_Admin clicks the view icon on a Submission_Record, THE Portal SHALL navigate to a read-only detail view showing the full timesheet entries for that submission

### Requirement 4: Submissions View Filtering

**User Story:** As an Admin_User or Super_Admin, I want to filter the timesheet submissions by date range, user, and status, so that I can quickly find specific submissions.

#### Acceptance Criteria

1. THE Submissions_View SHALL display a date range picker filter defaulting to the current week period
2. THE Submissions_View SHALL display an "All Users" dropdown filter populated with employee names from the API_Service using `listUsers`
3. THE Submissions_View SHALL display an "All Status" dropdown filter with options: All Status, Draft, and Submitted
4. WHEN the Admin_User or Super_Admin selects a date range, THE Submissions_View SHALL filter the displayed submissions to match the selected period
5. WHEN the Admin_User or Super_Admin selects a specific user from the dropdown, THE Submissions_View SHALL display only submissions belonging to that user
6. WHEN the Admin_User or Super_Admin selects a specific status from the dropdown, THE Submissions_View SHALL display only submissions matching that status
7. WHEN the Admin_User or Super_Admin changes any filter, THE Submissions_View SHALL update the displayed submissions without a full page reload

### Requirement 5: Hide Employee Timesheet Features for Admin and Superadmin

**User Story:** As an Admin_User or Super_Admin, I want the employee timesheet entry features hidden from my view, so that I do not see options to submit personal timesheets.

#### Acceptance Criteria

1. WHILE the logged-in user has userType `admin` or `superadmin`, THE Timesheet_Page SHALL not display the "+ New Entry" button
2. WHILE the logged-in user has userType `admin` or `superadmin`, THE Timesheet_Page SHALL not display the submission deadline countdown
3. WHILE the logged-in user has userType `admin` or `superadmin`, THE Timesheet_Page SHALL not display the weekly total hours target indicator
4. WHILE the logged-in user has userType `admin` or `superadmin`, THE Timesheet_Page SHALL not display the "History" button for personal timesheet history
5. WHILE the logged-in user has userType `admin` or `superadmin`, THE Portal SHALL not display edit or delete action icons on submission entries in the Submissions_View

### Requirement 6: Submission Detail View

**User Story:** As an Admin_User or Super_Admin, I want to view the full details of an employee's timesheet submission, so that I can review the hours logged per project per day.

#### Acceptance Criteria

1. WHEN an Admin_User or Super_Admin clicks the view icon on a Submission_Record, THE Portal SHALL display a detail view showing the employee name, week period, submission status, and total hours
2. THE detail view SHALL display a table of timesheet entries with columns: Project Code, Saturday, Sunday, Monday, Tuesday, Wednesday, Thursday, Friday, and Total Hours
3. THE detail view SHALL display all entry data as read-only without edit or delete controls
4. THE detail view SHALL provide a back navigation link to return to the Submissions_View
5. IF the selected submission has no timesheet entries, THEN THE detail view SHALL display a message indicating no entries were logged for the period
