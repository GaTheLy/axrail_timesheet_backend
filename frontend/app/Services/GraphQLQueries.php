<?php

namespace App\Services;

/**
 * Centralized GraphQL query and mutation string constants.
 *
 * All GraphQL operations used across controllers are defined here
 * to ensure consistency and single-source-of-truth alignment with
 * the GraphQL schema (graphql/schema.graphql).
 */
class GraphQLQueries
{
    /**
     * Fetch the current active timesheet period.
     *
     * Used by: DashboardController, TimesheetController
     */
    public const GET_CURRENT_PERIOD = <<<'GRAPHQL'
    query GetCurrentPeriod {
        getCurrentPeriod {
            periodId
            startDate
            endDate
            submissionDeadline
            periodString
            biweeklyPeriodId
            isLocked
            createdAt
            createdBy
        }
    }
    GRAPHQL;

    /**
     * Fetch the current period ID only (lightweight query for internal use).
     *
     * Used by: TimesheetController::getCurrentSubmission
     */
    public const GET_CURRENT_PERIOD_ID = <<<'GRAPHQL'
    query GetCurrentPeriodId {
        getCurrentPeriod {
            periodId
        }
    }
    GRAPHQL;

    /**
     * List the authenticated user's timesheet submissions with optional filter.
     *
     * Returns submissions with nested entries. Accepts an optional
     * SubmissionFilterInput to filter by periodId or status.
     *
     * Used by: DashboardController, TimesheetController, HistoryController
     */
    public const LIST_MY_SUBMISSIONS = <<<'GRAPHQL'
    query ListMySubmissions($filter: SubmissionFilterInput) {
        listMySubmissions(filter: $filter) {
            submissionId
            periodId
            employeeId
            status
            archived
            entries {
                entryId
                submissionId
                projectCode
                saturday
                sunday
                monday
                tuesday
                wednesday
                thursday
                friday
                totalHours
                createdAt
                updatedAt
            }
            totalHours
            chargeableHours
            createdAt
            updatedAt
            updatedBy
        }
    }
    GRAPHQL;

    /**
     * List projects with optional filter (e.g., approval_status: Approved).
     *
     * Returns a ProjectConnection with items array and nextToken for pagination.
     *
     * Used by: TimesheetController
     */
    public const LIST_PROJECTS = <<<'GRAPHQL'
    query ListProjects($filter: ProjectFilterInput) {
        listProjects(filter: $filter) {
            items {
                projectId
                projectCode
                projectName
                startDate
                plannedHours
                projectManagerId
                status
                approval_status
                rejectionReason
                createdAt
                createdBy
                updatedAt
                updatedBy
            }
            nextToken
        }
    }
    GRAPHQL;

    /**
     * Fetch a single user by ID.
     *
     * Used by: SettingsController
     */
    public const GET_USER = <<<'GRAPHQL'
    query GetUser($userId: ID!) {
        getUser(userId: $userId) {
            userId
            email
            fullName
            userType
            role
            status
            positionId
            departmentId
            supervisorId
            createdAt
            createdBy
            updatedAt
            updatedBy
        }
    }
    GRAPHQL;

    /**
     * List all departments.
     *
     * Used by: SettingsController
     */
    public const LIST_DEPARTMENTS = <<<'GRAPHQL'
    query ListDepartments {
        listDepartments {
            departmentId
            departmentName
            createdAt
            createdBy
            updatedAt
            updatedBy
            approval_status
            rejectionReason
        }
    }
    GRAPHQL;

    /**
     * List all timesheet periods with optional filter.
     *
     * Used by: HistoryController (to map periodId → startDate)
     */
    public const LIST_TIMESHEET_PERIODS = <<<'GRAPHQL'
    query ListTimesheetPeriods($filter: PeriodFilterInput) {
        listTimesheetPeriods(filter: $filter) {
            periodId
            startDate
            endDate
            submissionDeadline
            periodString
            biweeklyPeriodId
            isLocked
            createdAt
            createdBy
        }
    }
    GRAPHQL;

    // ---------------------------------------------------------------
    // Mutations
    // ---------------------------------------------------------------

    /**
     * Add a new timesheet entry to a submission.
     *
     * Used by: TimesheetController::storeEntry
     */
    public const ADD_TIMESHEET_ENTRY = <<<'GRAPHQL'
    mutation AddTimesheetEntry($submissionId: ID!, $input: TimesheetEntryInput!) {
        addTimesheetEntry(submissionId: $submissionId, input: $input) {
            entryId
            submissionId
            projectCode
            saturday
            sunday
            monday
            tuesday
            wednesday
            thursday
            friday
            totalHours
            createdAt
            updatedAt
        }
    }
    GRAPHQL;

    /**
     * Update an existing timesheet entry.
     *
     * Used by: TimesheetController::storeEntry, updateEntry, destroyEntry
     */
    public const UPDATE_TIMESHEET_ENTRY = <<<'GRAPHQL'
    mutation UpdateTimesheetEntry($entryId: ID!, $input: TimesheetEntryInput!) {
        updateTimesheetEntry(entryId: $entryId, input: $input) {
            entryId
            submissionId
            projectCode
            saturday
            sunday
            monday
            tuesday
            wednesday
            thursday
            friday
            totalHours
            createdAt
            updatedAt
        }
    }
    GRAPHQL;

    /**
     * Remove a timesheet entry entirely.
     *
     * Returns Boolean! indicating success.
     *
     * Used by: TimesheetController::destroyEntry
     */
    public const REMOVE_TIMESHEET_ENTRY = <<<'GRAPHQL'
    mutation RemoveTimesheetEntry($entryId: ID!) {
        removeTimesheetEntry(entryId: $entryId)
    }
    GRAPHQL;

    // ---------------------------------------------------------------
    // PM Reports Queries
    // ---------------------------------------------------------------

    /**
     * List all submissions with optional admin filter.
     *
     * Returns submissions with nested entries for cross-referencing
     * charged hours per project in the selected period.
     *
     * Used by: ReportsController
     */
    public const LIST_ALL_SUBMISSIONS = <<<'GRAPHQL'
    query ListAllSubmissions($filter: AdminSubmissionFilterInput) {
        listAllSubmissions(filter: $filter) {
            submissionId
            periodId
            employeeId
            status
            entries { entryId projectCode totalHours }
            totalHours
            chargeableHours
        }
    }
    GRAPHQL;

    /**
     * Get a pre-signed S3 URL for the project summary PDF report.
     *
     * Used by: ReportsController::exportProjectPdf
     */
    public const GET_PROJECT_SUMMARY_REPORT = <<<'GRAPHQL'
    query GetProjectSummaryReport($periodId: ID!) {
        getProjectSummaryReport(periodId: $periodId) {
            url
            expiresAt
        }
    }
    GRAPHQL;

    /**
     * Get a pre-signed S3 URL for the TC summary PDF report.
     *
     * Used by: ReportsController::exportSubmissionPdf
     */
    public const GET_TC_SUMMARY_REPORT = <<<'GRAPHQL'
    query GetTCSummaryReport($techLeadId: ID!, $periodId: ID!) {
        getTCSummaryReport(techLeadId: $techLeadId, periodId: $periodId) {
            url
            expiresAt
        }
    }
    GRAPHQL;

    /**
     * List users with full details for User Management page.
     *
     * Returns all user fields needed for the admin user management table.
     *
     * Used by: UserManagementController::index
     */
    public const LIST_USERS_FULL = <<<'GRAPHQL'
    query ListUsersFull($filter: UserFilterInput) {
        listUsers(filter: $filter) {
            items {
                userId
                email
                fullName
                userType
                role
                status
                positionId
                departmentId
                createdAt
                approval_status
                rejectionReason
            }
            nextToken
        }
    }
    GRAPHQL;

    /**
     * Fallback query without status field (handles bad data with null status).
     *
     * Used by: UserManagementController::index (fallback)
     */
    public const LIST_USERS_MINIMAL = <<<'GRAPHQL'
    query ListUsersMinimal($filter: UserFilterInput) {
        listUsers(filter: $filter) {
            items {
                userId
                email
                fullName
                userType
                role
                positionId
                departmentId
                createdAt
            }
            nextToken
        }
    }
    GRAPHQL;

    /**
     * List users with optional filter and pagination.
     *
     * Used to resolve employeeId → fullName in submission summary.
     *
     * Used by: ReportsController::submissionSummary
     */
    public const LIST_USERS = <<<'GRAPHQL'
    query ListUsers($filter: UserFilterInput) {
        listUsers(filter: $filter) {
            items {
                userId
                fullName
            }
            nextToken
        }
    }
    GRAPHQL;

    // ---------------------------------------------------------------
    // User Management Mutations
    // ---------------------------------------------------------------

    /**
     * List all positions.
     *
     * Used by: PositionController
     */
    public const LIST_POSITIONS = <<<'GRAPHQL'
    query ListPositions {
        listPositions {
            positionId
            positionName
            description
            createdAt
            createdBy
            updatedAt
            updatedBy
            approval_status
            rejectionReason
        }
    }
    GRAPHQL;

    /**
     * Create a new department.
     *
     * Used by: DepartmentController::store
     */
    public const CREATE_DEPARTMENT = <<<'GRAPHQL'
    mutation CreateDepartment($input: CreateDepartmentInput!) {
        createDepartment(input: $input) {
            departmentId
            departmentName
            createdAt
            createdBy
        }
    }
    GRAPHQL;

    /**
     * Create a new position.
     *
     * Used by: PositionController::store
     */
    public const CREATE_POSITION = <<<'GRAPHQL'
    mutation CreatePosition($input: CreatePositionInput!) {
        createPosition(input: $input) {
            positionId
            positionName
            description
            createdAt
            createdBy
        }
    }
    GRAPHQL;

    /**
     * Create a new user record.
     *
     * Used by: UserManagementController::store
     */
    public const CREATE_USER = <<<'GRAPHQL'
    mutation CreateUser($input: CreateUserInput!) {
        createUser(input: $input) {
            userId
            email
            fullName
            userType
            role
            positionId
            departmentId
        }
    }
    GRAPHQL;

    /**
     * Update an existing user record.
     *
     * Used by: UserManagementController::update
     */
    public const UPDATE_USER = <<<'GRAPHQL'
    mutation UpdateUser($userId: ID!, $input: UpdateUserInput!) {
        updateUser(userId: $userId, input: $input) {
            userId
            email
            fullName
            userType
            role
            status
            positionId
            departmentId
        }
    }
    GRAPHQL;

    /**
     * Delete a user record.
     *
     * Used by: UserManagementController::destroy
     */
    public const DELETE_USER = <<<'GRAPHQL'
    mutation DeleteUser($userId: ID!) {
        deleteUser(userId: $userId)
    }
    GRAPHQL;

    // ---------------------------------------------------------------
    // Project Mutations
    // ---------------------------------------------------------------

    /**
     * Delete a department.
     *
     * Used by: DepartmentController::destroy
     */
    public const DELETE_DEPARTMENT = <<<'GRAPHQL'
    mutation DeleteDepartment($departmentId: ID!) {
        deleteDepartment(departmentId: $departmentId)
    }
    GRAPHQL;

    /**
     * Update a department.
     *
     * Used by: DepartmentController::update
     */
    public const UPDATE_DEPARTMENT = <<<'GRAPHQL'
    mutation UpdateDepartment($departmentId: ID!, $input: UpdateDepartmentInput!) {
        updateDepartment(departmentId: $departmentId, input: $input) {
            departmentId
            departmentName
            approval_status
        }
    }
    GRAPHQL;

    /**
     * Delete a position.
     *
     * Used by: PositionController::destroy
     */
    public const DELETE_POSITION = <<<'GRAPHQL'
    mutation DeletePosition($positionId: ID!) {
        deletePosition(positionId: $positionId)
    }
    GRAPHQL;

    /**
     * Update a position.
     *
     * Used by: PositionController::update
     */
    public const UPDATE_POSITION = <<<'GRAPHQL'
    mutation UpdatePosition($positionId: ID!, $input: UpdatePositionInput!) {
        updatePosition(positionId: $positionId, input: $input) {
            positionId
            positionName
            description
            approval_status
        }
    }
    GRAPHQL;

    /**
     * Create a new project.
     *
     * Used by: ProjectController::store
     */
    public const CREATE_PROJECT = <<<'GRAPHQL'
    mutation CreateProject($input: CreateProjectInput!) {
        createProject(input: $input) {
            projectId
            projectCode
            projectName
            startDate
            plannedHours
            projectManagerId
            approval_status
            rejectionReason
            createdAt
            createdBy
        }
    }
    GRAPHQL;

    /**
     * Update a project.
     *
     * Used by: ProjectController::update
     */
    public const UPDATE_PROJECT = <<<'GRAPHQL'
    mutation UpdateProject($projectId: ID!, $input: UpdateProjectInput!) {
        updateProject(projectId: $projectId, input: $input) {
            projectId
            projectCode
            projectName
            startDate
            plannedHours
            projectManagerId
            approval_status
        }
    }
    GRAPHQL;

    /**
     * Delete a project.
     *
     * Used by: ProjectController::destroy
     */
    public const DELETE_PROJECT = <<<'GRAPHQL'
    mutation DeleteProject($projectId: ID!) {
        deleteProject(projectId: $projectId)
    }
    GRAPHQL;

    // ---------------------------------------------------------------
    // Approval / Rejection Mutations
    // ---------------------------------------------------------------

    /**
     * Approve a pending department (superadmin only).
     *
     * Used by: DepartmentController::approve
     */
    public const APPROVE_DEPARTMENT = <<<'GRAPHQL'
    mutation ApproveDepartment($departmentId: ID!) {
        approveDepartment(departmentId: $departmentId) {
            departmentId
            departmentName
            approval_status
            rejectionReason
            createdAt
            createdBy
            updatedAt
            updatedBy
        }
    }
    GRAPHQL;

    /**
     * Reject a pending department with a reason (superadmin only).
     *
     * Used by: DepartmentController::reject
     */
    public const REJECT_DEPARTMENT = <<<'GRAPHQL'
    mutation RejectDepartment($departmentId: ID!, $reason: String!) {
        rejectDepartment(departmentId: $departmentId, reason: $reason) {
            departmentId
            departmentName
            approval_status
            rejectionReason
            createdAt
            createdBy
            updatedAt
            updatedBy
        }
    }
    GRAPHQL;

    /**
     * Approve a pending position (superadmin only).
     *
     * Used by: PositionController::approve
     */
    public const APPROVE_POSITION = <<<'GRAPHQL'
    mutation ApprovePosition($positionId: ID!) {
        approvePosition(positionId: $positionId) {
            positionId
            positionName
            description
            approval_status
            rejectionReason
            createdAt
            createdBy
            updatedAt
            updatedBy
        }
    }
    GRAPHQL;

    /**
     * Reject a pending position with a reason (superadmin only).
     *
     * Used by: PositionController::reject
     */
    public const REJECT_POSITION = <<<'GRAPHQL'
    mutation RejectPosition($positionId: ID!, $reason: String!) {
        rejectPosition(positionId: $positionId, reason: $reason) {
            positionId
            positionName
            description
            approval_status
            rejectionReason
            createdAt
            createdBy
            updatedAt
            updatedBy
        }
    }
    GRAPHQL;

    /**
     * Approve a pending user (superadmin only).
     *
     * Used by: UserManagementController::approve
     */
    public const APPROVE_USER = <<<'GRAPHQL'
    mutation ApproveUser($userId: ID!) {
        approveUser(userId: $userId) {
            userId
            email
            fullName
            userType
            role
            status
            approval_status
            rejectionReason
            positionId
            departmentId
            createdAt
            createdBy
            updatedAt
            updatedBy
        }
    }
    GRAPHQL;

    /**
     * Reject a pending user with a reason (superadmin only).
     *
     * Used by: UserManagementController::reject
     */
    public const REJECT_USER = <<<'GRAPHQL'
    mutation RejectUser($userId: ID!, $reason: String!) {
        rejectUser(userId: $userId, reason: $reason) {
            userId
            email
            fullName
            userType
            role
            status
            approval_status
            rejectionReason
            positionId
            departmentId
            createdAt
            createdBy
            updatedAt
            updatedBy
        }
    }
    GRAPHQL;
}
