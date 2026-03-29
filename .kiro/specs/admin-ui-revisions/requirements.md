# Requirements Document

## Introduction

This specification covers five revisions to the TimeFlow admin interface: (1) adding confirmation pop-ups for all approval and rejection actions on master data entities, (2) adding success/error feedback pop-ups after every CRUD operation across all master data pages, (3) fixing broken filters on all four master data entity pages (departments, users, positions, projects), (4) implementing a user activate/deactivate toggle for admin and superadmin users, and (5) investigating and resolving missing timesheet submissions for a specific user. These changes address usability gaps, data integrity issues, and a production data anomaly in the current admin build.

## Glossary

- **Portal**: The TimeFlow web application front-end built with Laravel/Blade templates
- **Admin_User**: A user with userType `admin` who manages platform configuration, users, and projects
- **Super_Admin**: A user with userType `superadmin` who has full system access including admin management
- **API_Service**: The AWS AppSync GraphQL API backed by Lambda resolvers and DynamoDB
- **Confirmation_Dialog**: A modal pop-up that requires the user to confirm or cancel a destructive or state-changing action before the Portal submits the request
- **Feedback_Toast**: A non-blocking notification message displayed after a CRUD operation completes, indicating success or failure with a descriptive message
- **Department_Page**: The admin page at `/admin/departments` displaying department records with filters for search and approval status
- **Position_Page**: The admin page at `/admin/positions` displaying position records with filters for search and approval status
- **Project_Page**: The admin page at `/admin/projects` displaying project records with filters for search, start date, and status
- **User_Page**: The admin page at `/admin/users` displaying user records with filters for search, department, position, and approval status
- **Approvals_Page**: The admin page at `/admin/approvals` displaying pending entities across projects, departments, and positions tabs
- **Activation_Toggle**: A UI control on the User_Page that allows an Admin_User or Super_Admin to switch a user between `active` and `inactive` status
- **Master_Data_Entity**: A Department, Position, Project, or User record managed through the admin interface

## Requirements

### Requirement 1: Confirmation Pop-Up for Approval and Rejection Actions

**User Story:** As an Admin_User or Super_Admin, I want to see a confirmation pop-up before approving or rejecting a master data entity, so that I do not accidentally approve or reject an entity.

#### Acceptance Criteria

1. WHEN a Super_Admin clicks the approve button for a Department on the Approvals_Page, THE Portal SHALL display a Confirmation_Dialog asking the Super_Admin to confirm the approval before submitting the request
2. WHEN a Super_Admin clicks the approve button for a Position on the Approvals_Page, THE Portal SHALL display a Confirmation_Dialog asking the Super_Admin to confirm the approval before submitting the request
3. WHEN a Super_Admin clicks the approve button for a Project on the Approvals_Page, THE Portal SHALL display a Confirmation_Dialog asking the Super_Admin to confirm the approval before submitting the request
4. WHEN a Super_Admin clicks the approve button for a User on the Approvals_Page, THE Portal SHALL display a Confirmation_Dialog asking the Super_Admin to confirm the approval before submitting the request
5. WHEN a Super_Admin clicks the reject button for any Master_Data_Entity on the Approvals_Page, THE Portal SHALL display the rejection reason modal which serves as the Confirmation_Dialog for rejection actions
6. WHEN the user cancels the Confirmation_Dialog, THE Portal SHALL close the dialog and take no further action on the entity
7. WHEN the user confirms the Confirmation_Dialog, THE Portal SHALL submit the approval or rejection request to the API_Service
8. THE Confirmation_Dialog SHALL display the entity name and entity type in the confirmation message so the user can verify the target entity

### Requirement 2: Success and Error Feedback After CRUD Operations

**User Story:** As an Admin_User or Super_Admin, I want to see a success or error message after every create, update, or delete operation, so that I know whether the action completed successfully without relying solely on table updates.

#### Acceptance Criteria

1. WHEN a create operation succeeds on the Department_Page, THE Portal SHALL display a Feedback_Toast with a success message indicating the department was created
2. WHEN a create operation fails on the Department_Page, THE Portal SHALL display a Feedback_Toast with an error message describing the failure reason
3. WHEN an update operation succeeds on the Department_Page, THE Portal SHALL display a Feedback_Toast with a success message indicating the department was updated
4. WHEN an update operation fails on the Department_Page, THE Portal SHALL display a Feedback_Toast with an error message describing the failure reason
5. WHEN a delete operation succeeds on the Department_Page, THE Portal SHALL display a Feedback_Toast with a success message indicating the department was deleted
6. WHEN a delete operation fails on the Department_Page, THE Portal SHALL display a Feedback_Toast with an error message describing the failure reason
7. WHEN a create, update, or delete operation succeeds on the Position_Page, THE Portal SHALL display a Feedback_Toast with a success message indicating the operation and entity type
8. WHEN a create, update, or delete operation fails on the Position_Page, THE Portal SHALL display a Feedback_Toast with an error message describing the failure reason
9. WHEN a create, update, or delete operation succeeds on the Project_Page, THE Portal SHALL display a Feedback_Toast with a success message indicating the operation and entity type
10. WHEN a create, update, or delete operation fails on the Project_Page, THE Portal SHALL display a Feedback_Toast with an error message describing the failure reason
11. WHEN a create, update, or delete operation succeeds on the User_Page, THE Portal SHALL display a Feedback_Toast with a success message indicating the operation and entity type
12. WHEN a create, update, or delete operation fails on the User_Page, THE Portal SHALL display a Feedback_Toast with an error message describing the failure reason
13. THE Feedback_Toast SHALL remain visible for 5 seconds before automatically dismissing
14. THE Feedback_Toast SHALL use green styling for success messages and red styling for error messages
15. THE Portal SHALL display the Feedback_Toast before triggering any page reload so the user can read the message


### Requirement 3: Fix Filters on All Master Data Pages

**User Story:** As an Admin_User or Super_Admin, I want all filters on the master data pages to work correctly, so that I can find and manage specific entities efficiently.

#### Acceptance Criteria

1. WHEN a user types in the search input on the Department_Page, THE Portal SHALL filter the department table rows to show only rows where the department name contains the search text (case-insensitive)
2. WHEN a user selects an approval status from the approval status filter on the Department_Page, THE Portal SHALL filter the department table rows to show only rows matching the selected approval status
3. WHEN a user applies both search text and approval status filter on the Department_Page, THE Portal SHALL show only rows matching both filter criteria simultaneously
4. WHEN a user types in the search input on the Position_Page, THE Portal SHALL filter the position table rows to show only rows where the position name contains the search text (case-insensitive)
5. WHEN a user selects an approval status from the approval status filter on the Position_Page, THE Portal SHALL filter the position table rows to show only rows matching the selected approval status
6. WHEN a user applies both search text and approval status filter on the Position_Page, THE Portal SHALL show only rows matching both filter criteria simultaneously
7. WHEN a user types in the search input on the Project_Page, THE Portal SHALL filter the project table rows to show only rows where the project name or project manager contains the search text (case-insensitive)
8. WHEN a user selects a start date from the start date filter on the Project_Page, THE Portal SHALL filter the project table rows to show only rows matching the selected start date
9. WHEN a user selects a status from the status filter on the Project_Page, THE Portal SHALL filter the project table rows to show only rows matching the selected status value
10. WHEN a user applies multiple filters on the Project_Page, THE Portal SHALL show only rows matching all active filter criteria simultaneously
11. WHEN a user types in the search input on the User_Page, THE Portal SHALL filter the user table rows to show only rows where the full name or email contains the search text (case-insensitive)
12. WHEN a user selects a department from the department filter on the User_Page, THE Portal SHALL filter the user table rows to show only rows where the department matches the selected value
13. WHEN a user selects a position from the position filter on the User_Page, THE Portal SHALL filter the user table rows to show only rows where the position matches the selected value
14. WHEN a user selects an approval status from the approval status filter on the User_Page, THE Portal SHALL filter the user table rows to show only rows matching the selected approval status
15. WHEN a user applies multiple filters on the User_Page, THE Portal SHALL show only rows matching all active filter criteria simultaneously
16. THE Portal SHALL populate the department filter dropdown on the User_Page with the list of available departments from the data
17. THE Portal SHALL populate the position filter dropdown on the User_Page with the list of available positions from the data
18. THE Portal SHALL populate the start date filter dropdown on the Project_Page with the distinct start dates from the project data
19. WHEN a user clears all filters on any Master Data page, THE Portal SHALL display all rows in the table

### Requirement 4: User Activate and Deactivate Toggle

**User Story:** As an Admin_User or Super_Admin, I want to activate and deactivate users using a toggle control, so that I can manage user access without permanently deleting user records.

#### Acceptance Criteria

1. THE User_Page SHALL display an Activation_Toggle control for each user row visible to Admin_User and Super_Admin users
2. THE Activation_Toggle SHALL visually indicate the current user status: toggled on for `active` users and toggled off for `inactive` users
3. WHEN an Admin_User or Super_Admin clicks the Activation_Toggle for an active user, THE Portal SHALL display a Confirmation_Dialog asking to confirm deactivation of the user
4. WHEN an Admin_User or Super_Admin confirms the deactivation, THE Portal SHALL call the `deactivateUser` mutation on the API_Service with the target userId
5. WHEN the `deactivateUser` mutation succeeds, THE Portal SHALL update the Activation_Toggle to the off state, update the status badge to "Inactive", and display a success Feedback_Toast
6. WHEN an Admin_User or Super_Admin clicks the Activation_Toggle for an inactive user, THE Portal SHALL display a Confirmation_Dialog asking to confirm activation of the user
7. WHEN an Admin_User or Super_Admin confirms the activation, THE Portal SHALL call the `activateUser` mutation on the API_Service with the target userId
8. WHEN the `activateUser` mutation succeeds, THE Portal SHALL update the Activation_Toggle to the on state, update the status badge to "Active", and display a success Feedback_Toast
9. IF the `deactivateUser` or `activateUser` mutation fails, THEN THE Portal SHALL revert the Activation_Toggle to the previous state and display an error Feedback_Toast with the failure reason
10. THE API_Service SHALL update the user `status` field to `inactive` when the `deactivateUser` mutation is called and to `active` when the `activateUser` mutation is called
11. THE Activation_Toggle SHALL be independent of the delete action, allowing Admin_User and Super_Admin to both deactivate and delete users
12. WHILE a user has approval_status `Pending_Approval`, THE Portal SHALL disable the Activation_Toggle for that user row since the user has not been approved yet

### Requirement 5: Investigate Missing Timesheet Submissions for Specific User

**User Story:** As a Super_Admin, I want to understand why a specific user has no timesheet submissions, so that I can resolve the data issue and ensure all employees can submit timesheets.

#### Acceptance Criteria

1. THE Portal SHALL verify that the user record for "Jason Gunawan" exists in the DynamoDB Users table and has status `active`
2. THE Portal SHALL verify that the user record for "Jason Gunawan" has a valid `userId` that matches the Cognito identity used for authentication
3. IF the user "Jason Gunawan" has a mismatched userId between DynamoDB and Cognito, THEN THE API_Service SHALL provide a mechanism to correct the userId mapping
4. THE API_Service SHALL return timesheet submissions for a user when the `listMySubmissions` query is called with the correct authenticated userId
5. IF the `listMySubmissions` query returns an empty result for a user who should have submissions, THEN THE API_Service SHALL log the query parameters and authentication context for debugging
6. WHEN the root cause is identified, THE development team SHALL document the fix and verify that the user can view and create timesheet submissions after the correction
