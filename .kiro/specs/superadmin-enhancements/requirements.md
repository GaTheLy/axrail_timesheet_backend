# Requirements Document

## Introduction

This feature enhances the superadmin experience in the TimeFlow platform by differentiating the superadmin view from the standard admin view. Superadmins gain an Approval Requests dashboard section, a dedicated Approvals sidebar link and page, unrestricted edit/delete capabilities on all entities regardless of approval status, the ability to create admin-level users from the frontend, and automatic "Approved" status on all entities they create.

## Glossary

- **Superadmin_Dashboard**: The dashboard page rendered for users with userType "superadmin", extending the existing admin dashboard with an additional Approval Requests section.
- **Admin_Dashboard**: The existing dashboard page rendered for users with userType "admin", containing the current period card, active users card, and submission trends chart.
- **Sidebar**: The main navigation component rendered in `sidebar.blade.php` that displays role-based navigation links.
- **Approval_Requests_Section**: A dashboard card section displaying counts of pending projects, departments, and positions with Review buttons linking to the Approvals page.
- **Approvals_Page**: A dedicated page accessible only to superadmins that lists all pending approval items (projects, departments, positions) with Approve and Reject actions organized in tabs.
- **Entity**: A collective term for users, departments, positions, and projects managed through the Master Data section.
- **Approval_Status**: The workflow state of an entity, one of: Pending_Approval, Approved, or Rejected.
- **DashboardController**: The Laravel controller responsible for rendering dashboard data for both admin and employee views.
- **Lambda_Handler**: The AWS Lambda function that processes GraphQL mutations for CRUD operations on entities.
- **User_Creation_Form**: The modal form used by admin and superadmin to create new user accounts.

## Requirements

### Requirement 1: Superadmin Dashboard with Approval Requests Section

**User Story:** As a superadmin, I want to see an Approval Requests section on my dashboard showing counts of pending entities, so that I can quickly assess what needs my review.

#### Acceptance Criteria

1. WHILE the logged-in user has userType "superadmin", THE Superadmin_Dashboard SHALL display the same Current Week Period card and Total Active Users card as the Admin_Dashboard.
2. WHILE the logged-in user has userType "superadmin", THE Superadmin_Dashboard SHALL display the same Submission Trends chart as the Admin_Dashboard.
3. WHILE the logged-in user has userType "superadmin", THE Superadmin_Dashboard SHALL display an Approval_Requests_Section below the summary cards.
4. THE Approval_Requests_Section SHALL display the count of entities with Approval_Status "Pending_Approval" for each of the following categories: projects, departments, and positions.
5. THE Approval_Requests_Section SHALL display a "Review" button for each category that navigates to the Approvals_Page.
6. WHEN there are zero pending entities for a category, THE Approval_Requests_Section SHALL display "0" as the count for that category.
7. WHILE the logged-in user has userType "admin", THE Admin_Dashboard SHALL continue to render without the Approval_Requests_Section.

### Requirement 2: Superadmin Sidebar with Approvals Navigation

**User Story:** As a superadmin, I want an "Approvals" link in my sidebar, so that I can navigate directly to the Approvals page.

#### Acceptance Criteria

1. WHILE the logged-in user has userType "superadmin", THE Sidebar SHALL display an "Approvals" navigation link in addition to all existing admin navigation items (Master Data group, Reports group).
2. THE Sidebar SHALL render the "Approvals" link only for users with userType "superadmin".
3. WHEN the superadmin clicks the "Approvals" link, THE Sidebar SHALL navigate to the Approvals_Page.
4. WHILE the user is on the Approvals_Page, THE Sidebar SHALL highlight the "Approvals" link as active.
5. WHILE the logged-in user has userType "admin", THE Sidebar SHALL continue to render without the "Approvals" link.

### Requirement 3: Approvals Page with Tabbed Entity Review

**User Story:** As a superadmin, I want a dedicated Approvals page with tabs for each entity type, so that I can review and act on all pending approval requests in one place.

#### Acceptance Criteria

1. THE Approvals_Page SHALL display three tabs: "Projects", "Departments", and "Positions".
2. WHEN the superadmin selects a tab, THE Approvals_Page SHALL display a list of entities with Approval_Status "Pending_Approval" for the selected category.
3. THE Approvals_Page SHALL display relevant identifying information for each pending entity (name, code, created date, created by).
4. THE Approvals_Page SHALL provide an "Approve" action button for each pending entity.
5. THE Approvals_Page SHALL provide a "Reject" action button for each pending entity.
6. WHEN the superadmin clicks "Approve" on an entity, THE Approvals_Page SHALL call the corresponding approve mutation (approveDepartment, approvePosition, or approveProject) and update the list.
7. WHEN the superadmin clicks "Reject" on an entity, THE Approvals_Page SHALL prompt for a rejection reason and call the corresponding reject mutation with the provided reason.
8. WHEN an approve or reject action completes successfully, THE Approvals_Page SHALL remove the entity from the pending list and display a success notification.
9. IF an approve or reject action fails, THEN THE Approvals_Page SHALL display an error notification with the failure reason.
10. THE Approvals_Page SHALL be accessible only to users with userType "superadmin".

### Requirement 4: Superadmin Unrestricted Edit and Delete

**User Story:** As a superadmin, I want to edit and delete any entity regardless of its approval status, so that I can manage all platform data without restrictions.

#### Acceptance Criteria

1. WHILE the logged-in user has userType "superadmin", THE frontend management pages (users, departments, positions, projects) SHALL display edit and delete action buttons for all entities regardless of Approval_Status.
2. WHILE the logged-in user has userType "superadmin", THE Lambda_Handler for UpdateUser, UpdateDepartment, UpdatePosition, and UpdateProject SHALL allow the update to proceed regardless of the entity Approval_Status.
3. WHILE the logged-in user has userType "superadmin", THE Lambda_Handler for DeleteUser, DeleteDepartment, DeletePosition, and DeleteProject SHALL allow the deletion to proceed regardless of the entity Approval_Status.
4. WHILE the logged-in user has userType "admin", THE Lambda_Handler for update and delete operations SHALL continue to reject operations on entities with Approval_Status "Approved".
5. WHILE the logged-in user has userType "admin", THE frontend management pages SHALL continue to hide edit and delete buttons for entities with Approval_Status "Approved".

### Requirement 5: Superadmin User Type Selection During User Creation

**User Story:** As a superadmin, I want to choose whether a new user is created as an "admin" or a "user", so that I can provision admin accounts from the frontend.

#### Acceptance Criteria

1. WHILE the logged-in user has userType "superadmin", THE User_Creation_Form SHALL display a "Role" dropdown with options "Admin" and "User".
2. WHEN the superadmin selects "Admin" from the Role dropdown, THE User_Creation_Form SHALL submit the user creation request with userType "admin".
3. WHEN the superadmin selects "User" from the Role dropdown, THE User_Creation_Form SHALL submit the user creation request with userType "user".
4. WHILE the logged-in user has userType "admin", THE User_Creation_Form SHALL continue to display the Role field as a read-only value of "User".
5. THE Lambda_Handler for CreateUser SHALL continue to accept the userType field and create the user with the specified userType when the caller is a superadmin.

### Requirement 6: Automatic Approval for Superadmin-Created Entities

**User Story:** As a superadmin, I want all entities I create to be automatically approved, so that I do not need to go through the approval workflow for my own creations.

#### Acceptance Criteria

1. WHEN a superadmin creates a user, THE Lambda_Handler for CreateUser SHALL set the Approval_Status to "Approved".
2. WHEN a superadmin creates a department, THE Lambda_Handler for CreateDepartment SHALL set the Approval_Status to "Approved".
3. WHEN a superadmin creates a position, THE Lambda_Handler for CreatePosition SHALL set the Approval_Status to "Approved".
4. WHEN a superadmin creates a project, THE Lambda_Handler for CreateProject SHALL set the Approval_Status to "Approved".
5. WHEN an admin creates any entity, THE Lambda_Handler SHALL continue to set the Approval_Status to "Pending_Approval".
