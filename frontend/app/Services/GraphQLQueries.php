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
}
