"""UpdateProjectAssignment Lambda resolver for AppSync.

Environment variables:
    PROJECT_ASSIGNMENTS_TABLE: DynamoDB ProjectAssignments table name
    USERS_TABLE: DynamoDB Users table name
    PROJECTS_TABLE: DynamoDB Projects table name
"""

import os
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.auth import ForbiddenError, require_user_type

PROJECT_ASSIGNMENTS_TABLE = os.environ.get("PROJECT_ASSIGNMENTS_TABLE", "")
USERS_TABLE = os.environ.get("USERS_TABLE", "")
PROJECTS_TABLE = os.environ.get("PROJECTS_TABLE", "")

dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    """AppSync Lambda resolver entry point for updateProjectAssignment."""
    try:
        return update_project_assignment(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def _get_assignments_table():
    return dynamodb.Table(PROJECT_ASSIGNMENTS_TABLE)


def _get_users_table():
    return dynamodb.Table(USERS_TABLE)


def _get_projects_table():
    return dynamodb.Table(PROJECTS_TABLE)


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _get_existing_assignment(assignment_id):
    """Fetch an existing assignment by assignmentId."""
    table = _get_assignments_table()
    response = table.get_item(Key={"assignmentId": assignment_id})
    if "Item" not in response:
        raise ValueError(f"Assignment '{assignment_id}' not found")
    return response["Item"]


def _validate_project_exists(project_id):
    """Validate that the project exists in the Projects table."""
    table = _get_projects_table()
    response = table.get_item(Key={"projectId": project_id})
    if "Item" not in response:
        raise ValueError(f"Project '{project_id}' not found")


def _validate_supervisor_exists(supervisor_id):
    """Validate that the supervisor exists in the Users table."""
    table = _get_users_table()
    response = table.get_item(Key={"userId": supervisor_id})
    if "Item" not in response:
        raise ValueError(f"Supervisor '{supervisor_id}' not found")


def _check_duplicate_assignment(employee_id, project_id, exclude_assignment_id=None):
    """Check that no other assignment exists for this employee+project combination."""
    table = _get_assignments_table()
    response = table.query(
        IndexName="employeeId-index",
        KeyConditionExpression=Key("employeeId").eq(employee_id),
    )
    for item in response.get("Items", []):
        if item.get("projectId") == project_id and item.get("assignmentId") != exclude_assignment_id:
            raise ValueError(
                f"Assignment already exists for employee '{employee_id}' "
                f"on project '{project_id}'"
            )


def update_project_assignment(event):
    """Update an existing project assignment.

    Validates: Requirements 2.2, 2.5, 2.6, 2.7
    """
    caller = require_user_type(event, ["superadmin", "admin"])
    assignment_id = event["arguments"]["assignmentId"]
    args = event["arguments"]["input"]

    existing = _get_existing_assignment(assignment_id)

    # Validate referenced IDs if provided
    if "supervisorId" in args:
        _validate_supervisor_exists(args["supervisorId"])

    if "projectId" in args:
        _validate_project_exists(args["projectId"])

        # If projectId is changing, check for duplicate employeeId+projectId
        if args["projectId"] != existing.get("projectId"):
            _check_duplicate_assignment(
                existing["employeeId"],
                args["projectId"],
                exclude_assignment_id=assignment_id,
            )

    # Build updated item
    now = _now_iso()
    updated = {**existing}
    for key in ("supervisorId", "projectId"):
        if key in args:
            updated[key] = args[key]
    updated["updatedAt"] = now
    updated["updatedBy"] = caller["userId"]

    table = _get_assignments_table()
    table.put_item(Item=updated)
    return updated
