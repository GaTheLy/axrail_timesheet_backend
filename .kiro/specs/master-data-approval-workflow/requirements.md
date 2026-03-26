# Requirements Document

## Introduction

This specification defines a unified approval workflow for all Master Data entities in the TimeFlow platform: Departments, Positions, Projects, and Users. Currently, only superadmins can create departments and positions, and projects already have a partial approval flow. This feature extends creation permissions to admin users while introducing a consistent approval lifecycle across all four entity types. Admin-created entities start with a "Pending" status and require superadmin approval before becoming active. Superadmin-created entities are auto-approved. Approved entities are protected from modification and deletion.

## Glossary

- **Portal**: The TimeFlow web application front-end built with Laravel/Blade templates
- **Admin_User**: A user with userType `admin` who can create and manage Master Data entities subject to approval
- **Super_Admin**: A user with userType `superadmin` who has full system access including the ability to approve or reject entities
- **API_Service**: The AWS AppSync GraphQL API backed by Lambda resolvers and DynamoDB
- **Master_Data_Entity**: A Department, Position, Project, or User record managed through the admin interface
- **Approval_Status**: The lifecycle state of a Master_Data_Entity, one of: `Pending_Approval`, `Approved`, or `Rejected`
- **Department_Page**: The admin page at `/admin/departments` displaying department records with name, status, and action icons
- **Position_Page**: The admin page at `/admin/positions` displaying position records with name, description, status, and action icons
- **Project_Page**: The admin page at `/admin/projects` displaying project records with code, name, status, approval status, and action icons
- **User_Page**: The admin page at `/admin/users` displaying user records with code, name, email, role, status, and action icons
- **Approval_Action**: The approve or reject action available to a Super_Admin on a pending Master_Data_Entity
- **Rejection_Reason**: A text explanation provided by the Super_Admin when rejecting a Master_Data_Entity

## Requirements

### Requirement 1: Approval Status Field on All Master Data Entities

**User Story:** As a Super_Admin, I want all Master Data entities to have a consistent approval status field, so that I can track and manage the approval lifecycle of every entity uniformly.

#### Acceptance Criteria

1. THE API_Service SHALL include an `approval_status` field of type ApprovalStatus (`Pending_Approval`, `Approved`, `Rejected`) on Department, Position, Project, and User entity types
2. THE API_Service SHALL include an optional `rejectionReason` field of type String on Department, Position, and User entity types to match the existing Project schema
3. THE Department_Page SHALL display the approval_status value for each department record in the table
4. THE Position_Page SHALL display the approval_status value for each position record in the table
5. THE User_Page SHALL display the approval_status value for each user record in the table


### Requirement 2: Auto-Assignment of Approval Status on Entity Creation

**User Story:** As an Admin_User, I want to create Master Data entities that enter a pending state, so that a Super_Admin can review and approve them before they become active.

#### Acceptance Criteria

1. WHEN an Admin_User creates a Department, THE API_Service SHALL set the approval_status to `Pending_Approval`
2. WHEN an Admin_User creates a Position, THE API_Service SHALL set the approval_status to `Pending_Approval`
3. WHEN an Admin_User creates a Project, THE API_Service SHALL set the approval_status to `Pending_Approval`
4. WHEN an Admin_User creates a User, THE API_Service SHALL set the approval_status to `Pending_Approval`
5. WHEN a Super_Admin creates a Department, THE API_Service SHALL set the approval_status to `Approved`
6. WHEN a Super_Admin creates a Position, THE API_Service SHALL set the approval_status to `Approved`
7. WHEN a Super_Admin creates a Project, THE API_Service SHALL set the approval_status to `Approved`
8. WHEN a Super_Admin creates a User, THE API_Service SHALL set the approval_status to `Approved`
9. THE API_Service SHALL determine the creator's userType from the authenticated request context to assign the correct approval_status

### Requirement 3: Admin Permission to Create Departments and Positions

**User Story:** As an Admin_User, I want to create departments and positions, so that I can manage organizational structure without requiring superadmin intervention for every new entry.

#### Acceptance Criteria

1. WHEN an Admin_User calls the createDepartment mutation, THE API_Service SHALL accept the request and create the department with approval_status `Pending_Approval`
2. WHEN an Admin_User calls the createPosition mutation, THE API_Service SHALL accept the request and create the position with approval_status `Pending_Approval`
3. THE Portal SHALL display the "Add Department" button on the Department_Page for Admin_User users
4. THE Portal SHALL display the "Add Position" button on the Position_Page for Admin_User users
5. IF a user with userType `user` attempts to create a Department or Position, THEN THE API_Service SHALL reject the request and return an authorization error

### Requirement 4: Superadmin Approve and Reject Actions

**User Story:** As a Super_Admin, I want to approve or reject pending Master Data entities, so that I can control which entities become active in the system.

#### Acceptance Criteria

1. WHEN a Super_Admin approves a Department, THE API_Service SHALL update the department approval_status from `Pending_Approval` to `Approved`
2. WHEN a Super_Admin approves a Position, THE API_Service SHALL update the position approval_status from `Pending_Approval` to `Approved`
3. WHEN a Super_Admin approves a User, THE API_Service SHALL update the user approval_status from `Pending_Approval` to `Approved`
4. WHEN a Super_Admin rejects a Department with a Rejection_Reason, THE API_Service SHALL update the department approval_status from `Pending_Approval` to `Rejected` and store the Rejection_Reason
5. WHEN a Super_Admin rejects a Position with a Rejection_Reason, THE API_Service SHALL update the position approval_status from `Pending_Approval` to `Rejected` and store the Rejection_Reason
6. WHEN a Super_Admin rejects a User with a Rejection_Reason, THE API_Service SHALL update the user approval_status from `Pending_Approval` to `Rejected` and store the Rejection_Reason
7. IF an Admin_User attempts to approve or reject a Master_Data_Entity, THEN THE API_Service SHALL reject the request and return an authorization error
8. IF a Super_Admin attempts to approve or reject an entity that is not in `Pending_Approval` status, THEN THE API_Service SHALL reject the request and return an error indicating the entity is not pending approval
9. THE API_Service SHALL record the Super_Admin's userId in the `updatedBy` field and the current timestamp in the `updatedAt` field when processing an approve or reject action

### Requirement 5: Protection of Approved Entities

**User Story:** As a Super_Admin, I want approved entities to be protected from modification and deletion, so that approved data maintains integrity and cannot be accidentally altered.

#### Acceptance Criteria

1. WHILE a Department has approval_status `Approved`, THE API_Service SHALL reject update requests for that department and return an error indicating approved entities cannot be edited
2. WHILE a Position has approval_status `Approved`, THE API_Service SHALL reject update requests for that position and return an error indicating approved entities cannot be edited
3. WHILE a Project has approval_status `Approved`, THE API_Service SHALL reject update requests for that project and return an error indicating approved entities cannot be edited
4. WHILE a User has approval_status `Approved`, THE API_Service SHALL reject update requests for that user and return an error indicating approved entities cannot be edited
5. WHILE a Master_Data_Entity has approval_status `Approved`, THE API_Service SHALL reject delete requests for that entity and return an error indicating approved entities cannot be deleted
6. WHILE a Master_Data_Entity has approval_status `Pending_Approval` or `Rejected`, THE API_Service SHALL allow update and delete requests from Admin_User and Super_Admin users


### Requirement 6: UI Display of Approval Status and Conditional Actions

**User Story:** As an Admin_User or Super_Admin, I want the Master Data pages to visually distinguish entities by approval status and show appropriate actions, so that I can quickly identify pending items and take action.

#### Acceptance Criteria

1. THE Department_Page SHALL display a status badge for each department showing the current approval_status with distinct visual styling: green for `Approved`, yellow for `Pending_Approval`, red for `Rejected`
2. THE Position_Page SHALL display a status badge for each position showing the current approval_status with distinct visual styling: green for `Approved`, yellow for `Pending_Approval`, red for `Rejected`
3. THE User_Page SHALL display a status badge for each user showing the current approval_status with distinct visual styling: green for `Approved`, yellow for `Pending_Approval`, red for `Rejected`
4. WHILE a Master_Data_Entity has approval_status `Approved`, THE Portal SHALL hide the edit and delete action icons for that entity row
5. WHILE a Master_Data_Entity has approval_status `Pending_Approval` or `Rejected`, THE Portal SHALL display the edit and delete action icons for that entity row
6. WHILE a Master_Data_Entity has approval_status `Pending_Approval` and the logged-in user is a Super_Admin, THE Portal SHALL display approve and reject action buttons for that entity row
7. WHILE a Master_Data_Entity has approval_status `Pending_Approval` and the logged-in user is an Admin_User, THE Portal SHALL hide the approve and reject action buttons for that entity row
8. WHEN a Super_Admin clicks the reject action button, THE Portal SHALL display a modal dialog prompting for a Rejection_Reason before submitting the rejection

### Requirement 7: Approval Status Filtering on Master Data Pages

**User Story:** As an Admin_User or Super_Admin, I want to filter Master Data entities by approval status, so that I can focus on pending items that need attention.

#### Acceptance Criteria

1. THE Department_Page SHALL display a filter control allowing selection of: All, Pending_Approval, Approved, or Rejected
2. THE Position_Page SHALL display a filter control allowing selection of: All, Pending_Approval, Approved, or Rejected
3. THE User_Page SHALL display a filter control allowing selection of: All, Pending_Approval, Approved, or Rejected
4. WHEN a user selects an approval status filter, THE Portal SHALL display only entities matching the selected approval_status
5. WHEN a user selects "All", THE Portal SHALL display all entities regardless of approval_status
6. THE Portal SHALL default the approval status filter to "All" when a Master Data page loads

### Requirement 8: GraphQL Schema Updates for Approval Mutations

**User Story:** As a developer, I want the GraphQL schema to include approval and rejection mutations for Departments, Positions, and Users, so that the API supports the full approval workflow consistently across all entity types.

#### Acceptance Criteria

1. THE API_Service SHALL expose an `approveDepartment(departmentId: ID!)` mutation that returns the updated Department
2. THE API_Service SHALL expose a `rejectDepartment(departmentId: ID!, reason: String!)` mutation that returns the updated Department
3. THE API_Service SHALL expose an `approvePosition(positionId: ID!)` mutation that returns the updated Position
4. THE API_Service SHALL expose a `rejectPosition(positionId: ID!, reason: String!)` mutation that returns the updated Position
5. THE API_Service SHALL expose an `approveUser(userId: ID!)` mutation that returns the updated User
6. THE API_Service SHALL expose a `rejectUser(userId: ID!, reason: String!)` mutation that returns the updated User
7. THE API_Service SHALL include `approval_status` and `rejectionReason` fields in the Department and Position GraphQL types
8. THE API_Service SHALL include `approval_status` and `rejectionReason` fields in the User GraphQL type, with `approval_status` being separate from the existing `status` field
