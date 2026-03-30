"""AddTimesheetEntry Lambda resolver for AppSync.

Environment variables:
    ENTRIES_TABLE: DynamoDB Timesheet_Entries table name
    SUBMISSIONS_TABLE: DynamoDB Timesheet_Submissions table name
    PROJECTS_TABLE: DynamoDB Projects table name
    PROJECT_ASSIGNMENTS_TABLE: DynamoDB ProjectAssignments table name
"""

import os
import uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.auth import ForbiddenError, get_caller_identity
from shared_utils import (
    get_entries_table, get_submission, validate_submission_editable,
    validate_project_approved, validate_max_entries,
    parse_and_validate_daily_hours, get_existing_entries, validate_daily_totals,
    validate_weekly_total, get_projects_table, recalculate_submission_total_hours,
)

PROJECT_ASSIGNMENTS_TABLE = os.environ.get("PROJECT_ASSIGNMENTS_TABLE", "")
dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    try:
        return add_timesheet_entry(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def add_timesheet_entry(event):
    """Add a new timesheet entry. Validates: Requirements 6.2-6.8, 15.1-15.5"""
    caller = get_caller_identity(event)
    employee_id = caller["userId"]
    args = event["arguments"]
    submission_id = args["submissionId"]
    input_data = args["input"]

    submission = get_submission(submission_id)
    validate_submission_editable(submission)

    project_code = input_data.get("projectCode", "")
    if not project_code or not project_code.strip():
        raise ValueError("projectCode is required")
    validate_project_approved(project_code)
    validate_max_entries(submission_id)

    hours = parse_and_validate_daily_hours(input_data)
    existing_entries = get_existing_entries(submission_id)
    validate_daily_totals(existing_entries, hours)
    validate_weekly_total(existing_entries, hours)

    now = datetime.now(timezone.utc).isoformat()
    entry_id = str(uuid.uuid4())

    item = {
        "entryId": entry_id,
        "submissionId": submission_id,
        "projectCode": project_code,
        "saturday": hours["saturday"],
        "sunday": hours["sunday"],
        "monday": hours["monday"],
        "tuesday": hours["tuesday"],
        "wednesday": hours["wednesday"],
        "thursday": hours["thursday"],
        "friday": hours["friday"],
        "totalHours": hours["totalHours"],
        "createdAt": now,
        "updatedAt": now,
    }

    entries_table = get_entries_table()
    entries_table.put_item(Item=item)

    # Recalculate submission totalHours
    recalculate_submission_total_hours(submission_id)

    # Auto-create project assignment (employee → project manager as supervisor)
    _ensure_project_assignment(employee_id, project_code, now)

    return item


def _ensure_project_assignment(employee_id, project_code, now):
    """Auto-create a ProjectAssignment linking the employee to the project's manager.

    Looks up the project by projectCode to get projectManagerId and projectId,
    then checks if an assignment already exists. If not, creates one.
    Each project has one supervisor (the projectManagerId).
    """
    if not PROJECT_ASSIGNMENTS_TABLE:
        return

    try:
        # Look up the project to get projectManagerId and projectId
        projects_table = get_projects_table()
        response = projects_table.query(
            IndexName="projectCode-index",
            KeyConditionExpression=Key("projectCode").eq(project_code),
        )
        items = response.get("Items", [])
        if not items:
            return

        project = items[0]
        project_id = project.get("projectId", "")
        supervisor_id = project.get("projectManagerId", "")

        if not supervisor_id or not project_id:
            return

        # Don't create assignment if employee is the supervisor themselves
        if employee_id == supervisor_id:
            return

        # Check if assignment already exists for this employee + project
        assignments_table = dynamodb.Table(PROJECT_ASSIGNMENTS_TABLE)
        existing = assignments_table.query(
            IndexName="employeeId-index",
            KeyConditionExpression=Key("employeeId").eq(employee_id),
        )
        for assignment in existing.get("Items", []):
            if assignment.get("projectId") == project_id:
                return  # Assignment already exists

        # Create the assignment
        assignment_id = str(uuid.uuid4())
        assignments_table.put_item(Item={
            "assignmentId": assignment_id,
            "employeeId": employee_id,
            "projectId": project_id,
            "supervisorId": supervisor_id,
            "createdAt": now,
            "createdBy": employee_id,
            "updatedAt": now,
            "updatedBy": employee_id,
        })
    except Exception:
        # Don't fail the entry creation if assignment fails
        pass
