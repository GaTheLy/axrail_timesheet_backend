# Requirements Document

## Introduction

TimeFlow is a workforce portal front-end prototype for the COLABS Employee Timesheet Management System. The prototype provides a web-based interface for employees to view dashboards, manage timesheet entries, review timesheet history, and update profile settings. It integrates with the existing AWS backend (AppSync GraphQL API, Cognito authentication, DynamoDB) and supports four user roles: General Employee, Tech Lead/PM, Admin, and Super Admin. This initial phase focuses on the General Employee role screens.

The prototype is built using HTML, CSS, and PHP/Laravel and resides in a dedicated `frontend/` directory at the workspace root, intended for eventual migration to its own workspace.

## Glossary

- **Portal**: The TimeFlow web application front-end that employees interact with via a browser
- **Employee**: A user with userType `user` and role `Employee` who logs time entries against assigned projects
- **Tech_Lead_PM**: A user with userType `user` and role `Tech_Lead` or `Project_Manager` who supervises employees and reviews timesheets
- **Admin_User**: A user with userType `admin` who manages platform configuration, users, and projects
- **Super_Admin**: A user with userType `superadmin` who has full system access including admin management
- **Auth_Service**: The AWS Cognito User Pool that handles user authentication and token management
- **API_Service**: The AWS AppSync GraphQL API that serves as the backend data layer
- **Dashboard_Page**: The main landing page after login showing summary cards, weekly activity chart, and recent time entries
- **Timesheet_Page**: The page where employees view, add, edit, and delete time entries for the current week
- **History_Page**: The page displaying past timesheet entries with date range filtering
- **Settings_Page**: The page for managing user profile information and password changes
- **Sidebar_Navigation**: The persistent left-side navigation panel with links to Dashboard, Timesheet, and Settings pages
- **Entry_Modal**: The modal dialog for adding or editing a timesheet entry
- **Summary_Card**: A UI card component on the Dashboard displaying a key metric (period, deadline, hours)
- **Submission**: A timesheet submission record containing entries for a specific period and employee
- **Period**: A weekly timesheet period running Monday through Friday

## Requirements

### Requirement 1: User Authentication

**User Story:** As an Employee, I want to sign in to the TimeFlow portal with my email and password, so that I can securely access my timesheet data.

#### Acceptance Criteria

1. THE Portal SHALL display a login page with email and password input fields, a "Remember this device" checkbox, a "Forgot password?" link, and a "Sign In" button
2. WHEN an Employee submits valid credentials, THE Auth_Service SHALL authenticate the user and THE Portal SHALL redirect to the Dashboard_Page
3. IF invalid credentials are submitted, THEN THE Portal SHALL display an error message indicating authentication failure without revealing which field is incorrect
4. WHEN an Employee checks "Remember this device" and signs in successfully, THE Portal SHALL persist the session token using the Cognito refresh token (30-day validity)
5. THE Portal SHALL display the TimeFlow branding and "© 2026 Team Alpha" footer on the login page
6. WHEN an authenticated session token expires, THE Portal SHALL redirect the Employee to the login page
7. WHEN an Employee clicks "Forgot password?", THE Portal SHALL initiate the Cognito forgot-password flow and display a password reset form

### Requirement 2: Sidebar Navigation

**User Story:** As an Employee, I want a persistent sidebar navigation, so that I can quickly switch between Dashboard, Timesheet, and Settings pages.

#### Acceptance Criteria

1. THE Portal SHALL display a Sidebar_Navigation on all authenticated pages containing links to Dashboard_Page, Timesheet_Page, and Settings_Page
2. THE Sidebar_Navigation SHALL visually highlight the currently active page link
3. THE Sidebar_Navigation SHALL display the authenticated user's full name and role at the bottom of the sidebar
4. WHEN an Employee clicks a navigation link, THE Portal SHALL navigate to the corresponding page without a full page reload where technically feasible

### Requirement 3: Dashboard Page

**User Story:** As an Employee, I want to see a dashboard with my timesheet summary, so that I can quickly understand my current week's status.

#### Acceptance Criteria

1. WHEN the Dashboard_Page loads, THE Portal SHALL display a welcome message containing the Employee's full name
2. WHEN the Dashboard_Page loads, THE Portal SHALL display three Summary_Cards: Current Week Period (start and end dates), Submission Deadline (with a countdown timer showing days, hours, and minutes remaining), and Personal Summary (total charged hours for the current period)
3. WHEN the Dashboard_Page loads, THE Portal SHALL query the API_Service using `getCurrentPeriod` to retrieve the active period data
4. WHEN the Dashboard_Page loads, THE Portal SHALL query the API_Service using `listMySubmissions` filtered by the current period to retrieve the Employee's submission and entries
5. THE Dashboard_Page SHALL display a Weekly Activity bar chart showing daily charged hours (Monday through Friday) compared against a daily target
6. THE Dashboard_Page SHALL display a Recent Time Entries table showing the most recent entries with columns: Date, Project Code, Description, and Charged Hours
7. THE Dashboard_Page SHALL include a "View Timesheet" link that navigates to the Timesheet_Page
8. IF the API_Service returns an error, THEN THE Dashboard_Page SHALL display a user-friendly error message and a retry option

### Requirement 4: Timesheet Page — View Current Week Entries

**User Story:** As an Employee, I want to view my current week's timesheet entries, so that I can track my logged hours.

#### Acceptance Criteria

1. WHEN the Timesheet_Page loads, THE Portal SHALL display the current week date range as a header (e.g., "Mon, Jun 16 – Fri, Jun 20")
2. WHEN the Timesheet_Page loads, THE Portal SHALL display the submission deadline with a countdown badge showing remaining time
3. THE Timesheet_Page SHALL display a table of Current Week Entries with columns: Date, Project Code, Description, Charged Hours, and Actions (edit and delete icons)
4. THE Timesheet_Page SHALL display the Weekly Total showing total charged hours and the 40-hour weekly target
5. THE Timesheet_Page SHALL provide a search bar to filter entries by project code or description text
6. THE Timesheet_Page SHALL provide a project filter dropdown to filter entries by a specific project code
7. THE Timesheet_Page SHALL include a "History" button that navigates to the History_Page
8. THE Timesheet_Page SHALL include a "+ New Entry" button that opens the Entry_Modal for adding a new entry
9. WHEN the Timesheet_Page loads, THE Portal SHALL query the API_Service using `listMySubmissions` filtered by the current period to retrieve entries

### Requirement 5: Timesheet Page — Add New Entry

**User Story:** As an Employee, I want to add a new time entry, so that I can log hours worked on a project.

#### Acceptance Criteria

1. WHEN the Employee clicks "+ New Entry", THE Portal SHALL open the Entry_Modal with fields: Project Code dropdown, Description text field, Date picker, and Charged Hours input
2. THE Entry_Modal SHALL populate the Project Code dropdown by querying the API_Service using `listProjects` filtered to Approved projects only
3. WHEN the Employee fills all required fields and clicks "Save Changes", THE Portal SHALL call the API_Service mutation `addTimesheetEntry` with the submission ID and entry input
4. IF the `addTimesheetEntry` mutation succeeds, THEN THE Portal SHALL close the Entry_Modal and refresh the entries table to show the new entry
5. IF the `addTimesheetEntry` mutation fails, THEN THE Portal SHALL display the error message returned by the API_Service within the Entry_Modal
6. THE Entry_Modal SHALL validate that Charged Hours is a non-negative number with a maximum of 2 decimal places before submission
7. THE Entry_Modal SHALL validate that all required fields (Project Code, Date, Charged Hours) are filled before enabling the "Save Changes" button
8. WHEN the Employee clicks "Cancel", THE Portal SHALL close the Entry_Modal without saving changes

### Requirement 6: Timesheet Page — Edit Entry

**User Story:** As an Employee, I want to edit an existing time entry, so that I can correct mistakes in my logged hours.

#### Acceptance Criteria

1. WHEN the Employee clicks the edit icon on an entry row, THE Portal SHALL open the Entry_Modal pre-populated with the existing entry data
2. WHEN the Employee modifies fields and clicks "Save Changes", THE Portal SHALL call the API_Service mutation `updateTimesheetEntry` with the entry ID and updated input
3. IF the `updateTimesheetEntry` mutation succeeds, THEN THE Portal SHALL close the Entry_Modal and refresh the entries table with the updated data
4. IF the `updateTimesheetEntry` mutation fails, THEN THE Portal SHALL display the error message returned by the API_Service within the Entry_Modal
5. WHILE the Submission status is "Submitted", THE Portal SHALL disable the edit icon and prevent entry modifications

### Requirement 7: Timesheet Page — Delete Entry

**User Story:** As an Employee, I want to delete a time entry, so that I can remove incorrectly logged hours.

#### Acceptance Criteria

1. WHEN the Employee clicks the delete icon on an entry row, THE Portal SHALL display a confirmation dialog asking the Employee to confirm deletion
2. WHEN the Employee confirms deletion, THE Portal SHALL call the API_Service mutation `removeTimesheetEntry` with the entry ID
3. IF the `removeTimesheetEntry` mutation succeeds, THEN THE Portal SHALL remove the entry from the table and update the Weekly Total
4. IF the `removeTimesheetEntry` mutation fails, THEN THE Portal SHALL display the error message returned by the API_Service
5. WHILE the Submission status is "Submitted", THE Portal SHALL disable the delete icon and prevent entry deletion

### Requirement 8: Timesheet History Page

**User Story:** As an Employee, I want to view my past timesheet entries, so that I can review my historical time logs.

#### Acceptance Criteria

1. WHEN the History_Page loads, THE Portal SHALL query the API_Service using `listMySubmissions` to retrieve all past submissions
2. THE History_Page SHALL display a date range picker allowing the Employee to filter entries by start and end dates
3. THE History_Page SHALL display a count of total entries tracked within the selected date range
4. THE History_Page SHALL display a table with columns: Date, Project, Description, and Charged Hours
5. THE History_Page SHALL display the Weekly Total for the selected period
6. WHEN the Employee selects a date range, THE Portal SHALL filter the displayed entries to match the selected period

### Requirement 9: Settings Page — Profile Management

**User Story:** As an Employee, I want to view and update my profile settings, so that I can keep my information current.

#### Acceptance Criteria

1. WHEN the Settings_Page loads, THE Portal SHALL display the Profile Settings section with the Employee's avatar, Full Name, Email Address, and Department
2. THE Settings_Page SHALL populate profile fields by querying the API_Service using `getUser` with the authenticated user's ID
3. THE Settings_Page SHALL populate the Department dropdown by querying the API_Service using `listDepartments`
4. THE Settings_Page SHALL allow the Employee to upload a new avatar image
5. THE Portal SHALL display the Email Address field as read-only since email changes require admin action

### Requirement 10: Settings Page — Password Change

**User Story:** As an Employee, I want to change my password, so that I can maintain account security.

#### Acceptance Criteria

1. THE Settings_Page SHALL display a Security section with Current Password, New Password, and Confirm Password fields, and a "Save Changes" button
2. WHEN the Employee fills all password fields and clicks "Save Changes", THE Portal SHALL call the Auth_Service to change the password using the Cognito change-password API
3. IF the password change succeeds, THEN THE Portal SHALL display a success notification
4. IF the password change fails, THEN THE Portal SHALL display the specific error (e.g., incorrect current password, password policy violation)
5. THE Portal SHALL validate that New Password and Confirm Password fields match before submitting the change request
6. THE Portal SHALL validate that the New Password meets the Cognito password policy: minimum 8 characters, at least one uppercase letter, one lowercase letter, one digit, and one symbol

### Requirement 11: Role-Based Access Control

**User Story:** As a system operator, I want the portal to enforce role-based access, so that users only see features appropriate to their role.

#### Acceptance Criteria

1. THE Portal SHALL support four user roles: Employee (userType: user, role: Employee), Tech_Lead_PM (userType: user, role: Tech_Lead or Project_Manager), Admin_User (userType: admin), and Super_Admin (userType: superadmin)
2. WHEN an Employee authenticates, THE Portal SHALL read the `custom:userType` and `custom:role` claims from the Cognito ID token to determine the user's role
3. THE Portal SHALL render navigation items and page access based on the authenticated user's role
4. IF an unauthenticated user attempts to access any page other than the login page, THEN THE Portal SHALL redirect to the login page
5. THE Portal SHALL store the authenticated user's role information in the client session for use in UI rendering decisions

### Requirement 12: Responsive Layout and Branding

**User Story:** As an Employee, I want the portal to be visually consistent and usable on different screen sizes, so that I can access my timesheet from various devices.

#### Acceptance Criteria

1. THE Portal SHALL use the TimeFlow brand identity including the TimeFlow logo, consistent color scheme, and typography across all pages
2. THE Portal SHALL render correctly on desktop viewports (1024px width and above)
3. THE Portal SHALL render correctly on tablet viewports (768px to 1023px width)
4. THE Portal SHALL collapse the Sidebar_Navigation into a hamburger menu on viewports narrower than 768px
5. THE Portal SHALL display the "© 2026 Team Alpha" footer on the login page

### Requirement 13: API Integration Layer

**User Story:** As a developer, I want a centralized API integration layer, so that all GraphQL queries and mutations are managed consistently.

#### Acceptance Criteria

1. THE Portal SHALL use a centralized API service module to execute all GraphQL queries and mutations against the API_Service
2. THE Portal SHALL include the Cognito JWT access token in the Authorization header of every API_Service request
3. IF an API request returns an authentication error (401/403), THEN THE Portal SHALL redirect the user to the login page
4. THE Portal SHALL implement request loading states showing a spinner or skeleton UI while API calls are in progress
5. IF an API request fails due to a network error, THEN THE Portal SHALL display a notification with a retry option

### Requirement 14: Frontend Project Structure

**User Story:** As a developer, I want the frontend prototype organized in a clean directory structure, so that the codebase is maintainable and ready for migration.

#### Acceptance Criteria

1. THE Portal SHALL reside in a `frontend/` directory at the workspace root, separate from the existing CDK and Lambda code
2. THE Portal SHALL use HTML, CSS, and PHP (or Laravel framework) as the technology stack
3. THE Portal SHALL store environment-specific configuration (AppSync endpoint URL, Cognito User Pool ID, Cognito Client ID, AWS region) in a single configuration file
4. THE Portal SHALL organize page templates, shared components (sidebar, modals), static assets (CSS, JS, images), and API service modules into clearly separated directories
