"""Timesheet Review Lambda resolver for AppSync.

Handles approval, rejection, and listing of pending timesheet submissions.
Only Project_Manager and Tech_Lead roles are authorized to perform reviews.
Reviewers can only see submissions for employees under their supervision
(via supervisorId-index GSI on the Users table).

Environment variables:
    SUBMISSIONS_TABLE: DynamoDB Timesheet_Submissions table name
    USERS_TABLE: DynamoDB Users table name (for supervisor lookup)
"""

import os
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key

# Add parent directory to path for shared imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.auth import ForbiddenError, require_role

SUBMISSIONS_TABLE = os.environ.get("SUBMISSIONS_TABLE", "")
USERS_TABLE = os.environ.get("USERS_TABLE", "")

REVIEWER_ROLES = ["Project_Manager", "Tech_Lead"]

dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    """AppSync Lambda resolver entry point.

    Routes to the appropriate operation based on event['info']['fieldName'].
    """
    field = event["info"]["fieldName"]
    resolvers = {
        "approveTimesheet": approve_timesheet,
        "rejectTimesheet": reject_timesheet,
        "listPendingTimesheets": list_pending_timesheets,
    }

    resolver = resolvers.get(field)
    if not resolver:
        raise ValueError(f"Unknown field: {field}")

    try:
        return resolver(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def _get_submissions_table():
    """Return the DynamoDB Timesheet_Submissions table resource."""
    return dynamodb.Table(SUBMISSIONS_TABLE)


def _get_users_table():
    """Return the DynamoDB Users table resource."""
    return dynamodb.Table(USERS_TABLE)


def _now_iso():
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _get_supervised_employee_ids(reviewer_id):
    """Get all employee IDs under the reviewer's supervision.

    Queries the supervisorId-index GSI on the Users table to find
    employees whose supervisorId matches the reviewer's userId.

    Args:
        reviewer_id: The reviewer's userId.

    Returns:
        A list of employee userId strings.
    """
    table = _get_users_table()
    response = table.query(
        IndexName="supervisorId-index",
        KeyConditionExpression=Key("supervisorId").eq(reviewer_id),
    )
    items = response.get("Items", [])

    # Handle pagination
    while "LastEvaluatedKey" in response:
        response = table.query(
            IndexName="supervisorId-index",
            KeyConditionExpression=Key("supervisorId").eq(reviewer_id),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))

    return [item["userId"] for item in items]


def approve_timesheet(event):
    """Approve a submitted timesheet, transitioning status to Approved.

    Only Project_Manager or Tech_Lead can approve. The submission must
    currently have status of Submitted. Records approvedBy and approvedAt.

    Validates: Requirements 7.1, 7.5
    """
    caller = require_role(event, REVIEWER_ROLES)
    submission_id = event["arguments"]["submissionId"]

    table = _get_submissions_table()

    existing = table.get_item(Key={"submissionId": submission_id}).get("Item")
    if not existing:
        raise ValueError(f"Submission '{submission_id}' not found")

    # Only Submitted -> Approved is valid
    if existing["status"] != "Submitted":
        raise ValueError(
            f"Cannot approve timesheet with status '{existing['status']}'. "
            f"Only timesheets with status 'Submitted' can be approved"
        )

    now = _now_iso()

    result = table.update_item(
        Key={"submissionId": submission_id},
        UpdateExpression=(
            "SET #status = :status, #approvedBy = :approvedBy, "
            "#approvedAt = :approvedAt, #updatedAt = :updatedAt, "
            "#updatedBy = :updatedBy"
        ),
        ExpressionAttributeNames={
            "#status": "status",
            "#approvedBy": "approvedBy",
            "#approvedAt": "approvedAt",
            "#updatedAt": "updatedAt",
            "#updatedBy": "updatedBy",
        },
        ExpressionAttributeValues={
            ":status": "Approved",
            ":approvedBy": caller["userId"],
            ":approvedAt": now,
            ":updatedAt": now,
            ":updatedBy": caller["userId"],
        },
        ReturnValues="ALL_NEW",
    )

    return result["Attributes"]


def reject_timesheet(event):
    """Reject a submitted timesheet, transitioning status to Rejected.

    Only Project_Manager or Tech_Lead can reject. The submission must
    currently have status of Submitted. Records updatedBy and updatedAt.

    Validates: Requirements 7.2, 7.5
    """
    caller = require_role(event, REVIEWER_ROLES)
    submission_id = event["arguments"]["submissionId"]

    table = _get_submissions_table()

    existing = table.get_item(Key={"submissionId": submission_id}).get("Item")
    if not existing:
        raise ValueError(f"Submission '{submission_id}' not found")

    # Only Submitted -> Rejected is valid
    if existing["status"] != "Submitted":
        raise ValueError(
            f"Cannot reject timesheet with status '{existing['status']}'. "
            f"Only timesheets with status 'Submitted' can be rejected"
        )

    now = _now_iso()

    result = table.update_item(
        Key={"submissionId": submission_id},
        UpdateExpression=(
            "SET #status = :status, #updatedAt = :updatedAt, "
            "#updatedBy = :updatedBy"
        ),
        ExpressionAttributeNames={
            "#status": "status",
            "#updatedAt": "updatedAt",
            "#updatedBy": "updatedBy",
        },
        ExpressionAttributeValues={
            ":status": "Rejected",
            ":updatedAt": now,
            ":updatedBy": caller["userId"],
        },
        ReturnValues="ALL_NEW",
    )

    return result["Attributes"]


def list_pending_timesheets(event):
    """List pending (Submitted) timesheets for employees under the reviewer.

    Only Project_Manager or Tech_Lead can list pending timesheets.
    Queries the supervisorId-index GSI on the Users table to find
    supervised employees, then queries submissions with status Submitted
    for those employees.

    Validates: Requirements 7.4
    """
    caller = require_role(event, REVIEWER_ROLES)
    reviewer_id = caller["userId"]

    # Get employee IDs under this reviewer's supervision
    employee_ids = _get_supervised_employee_ids(reviewer_id)

    if not employee_ids:
        return []

    # Query submissions with status Submitted using status-index GSI
    table = _get_submissions_table()
    response = table.query(
        IndexName="status-index",
        KeyConditionExpression=Key("status").eq("Submitted"),
    )
    items = response.get("Items", [])

    # Handle pagination
    while "LastEvaluatedKey" in response:
        response = table.query(
            IndexName="status-index",
            KeyConditionExpression=Key("status").eq("Submitted"),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))

    # Filter to only include submissions from supervised employees
    supervised_set = set(employee_ids)
    pending = [
        item for item in items
        if item.get("employeeId") in supervised_set
    ]

    return pending
