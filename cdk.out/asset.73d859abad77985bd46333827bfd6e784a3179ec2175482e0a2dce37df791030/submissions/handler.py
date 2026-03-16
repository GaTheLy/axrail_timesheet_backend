"""Timesheet Submission Management Lambda resolver for AppSync.

Handles creation, submission, and retrieval of timesheet submissions.
Employees can only access their own submissions. Enforces one submission
per employee per period via the employeeId-periodId-index GSI.

Environment variables:
    SUBMISSIONS_TABLE: DynamoDB Timesheet_Submissions table name
    ENTRIES_TABLE: DynamoDB Timesheet_Entries table name
"""

import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

# Add parent directory to path for shared imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.auth import ForbiddenError, get_caller_identity

SUBMISSIONS_TABLE = os.environ.get("SUBMISSIONS_TABLE", "")
ENTRIES_TABLE = os.environ.get("ENTRIES_TABLE", "")

VALID_STATUSES = {"Draft", "Submitted", "Approved", "Rejected", "Locked"}

dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    """AppSync Lambda resolver entry point.

    Routes to the appropriate operation based on event['info']['fieldName'].
    """
    field = event["info"]["fieldName"]
    resolvers = {
        "createTimesheetSubmission": create_timesheet_submission,
        "submitTimesheet": submit_timesheet,
        "getTimesheetSubmission": get_timesheet_submission,
        "listMySubmissions": list_my_submissions,
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


def _get_entries_table():
    """Return the DynamoDB Timesheet_Entries table resource."""
    return dynamodb.Table(ENTRIES_TABLE)


def _now_iso():
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _check_existing_submission(table, employee_id, period_id):
    """Check if a submission already exists for this employee and period.

    Queries the employeeId-periodId-index GSI to enforce one submission
    per employee per period.

    Args:
        table: DynamoDB Timesheet_Submissions Table resource.
        employee_id: The employee's userId.
        period_id: The timesheet period ID.

    Raises:
        ValueError: If a submission already exists for this employee/period.

    Validates: Requirements 6.9
    """
    response = table.query(
        IndexName="employeeId-periodId-index",
        KeyConditionExpression=(
            Key("employeeId").eq(employee_id) & Key("periodId").eq(period_id)
        ),
    )
    items = response.get("Items", [])
    if items:
        raise ValueError(
            f"A submission already exists for employee '{employee_id}' "
            f"and period '{period_id}'"
        )


def create_timesheet_submission(event):
    """Create a new timesheet submission with status Draft.

    Any authenticated employee can create a submission for themselves.
    The caller's userId is used as the employeeId. Enforces one submission
    per employee per period.

    Validates: Requirements 6.1, 6.9
    """
    caller = get_caller_identity(event)
    employee_id = caller["userId"]
    period_id = event["arguments"]["periodId"]

    if not period_id or not period_id.strip():
        raise ValueError("periodId is required")

    table = _get_submissions_table()

    # Enforce one submission per employee per period
    _check_existing_submission(table, employee_id, period_id)

    now = _now_iso()
    submission_id = str(uuid.uuid4())

    item = {
        "submissionId": submission_id,
        "periodId": period_id,
        "employeeId": employee_id,
        "status": "Draft",
        "archived": False,
        "totalHours": Decimal("0"),
        "chargeableHours": Decimal("0"),
        "approvedBy": "",
        "approvedAt": "",
        "createdAt": now,
        "updatedAt": now,
        "updatedBy": employee_id,
    }

    table.put_item(Item=item)

    return item


def submit_timesheet(event):
    """Submit a Draft or Rejected timesheet, transitioning status to Submitted.

    Only the submission owner can submit. The submission must currently
    have status of Draft or Rejected.

    Validates: Requirements 6.4, 6.6
    """
    caller = get_caller_identity(event)
    submission_id = event["arguments"]["submissionId"]

    table = _get_submissions_table()

    existing = table.get_item(Key={"submissionId": submission_id}).get("Item")
    if not existing:
        raise ValueError(f"Submission '{submission_id}' not found")

    # Only the submission owner can submit
    if existing["employeeId"] != caller["userId"]:
        raise ForbiddenError(
            "You can only submit your own timesheet submissions"
        )

    # Reject if submission is archived
    if existing.get("archived") is True:
        raise ValueError(
            "Cannot submit an archived timesheet. "
            "Archived submissions are read-only"
        )

    # Validate status transition: only Draft or Rejected -> Submitted
    allowed_source_statuses = {"Draft", "Rejected"}
    if existing["status"] not in allowed_source_statuses:
        raise ValueError(
            f"Cannot submit timesheet with status '{existing['status']}'. "
            f"Only timesheets with status {sorted(allowed_source_statuses)} "
            f"can be submitted"
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
            ":status": "Submitted",
            ":updatedAt": now,
            ":updatedBy": caller["userId"],
        },
        ReturnValues="ALL_NEW",
    )

    return result["Attributes"]


def get_timesheet_submission(event):
    """Get a single timesheet submission with its entries.

    Only the submission owner or an admin/superadmin can view a submission.
    Fetches associated entries from the Entries table via submissionId-index GSI.

    Validates: Requirements 6.10, 6.11
    """
    caller = get_caller_identity(event)
    submission_id = event["arguments"]["submissionId"]

    table = _get_submissions_table()

    existing = table.get_item(Key={"submissionId": submission_id}).get("Item")
    if not existing:
        raise ValueError(f"Submission '{submission_id}' not found")

    # Only the owner or admin/superadmin can view
    if (
        existing["employeeId"] != caller["userId"]
        and caller["userType"] not in ("admin", "superadmin")
    ):
        raise ForbiddenError(
            "You can only view your own timesheet submissions"
        )

    # Fetch entries from the Entries table via submissionId-index GSI
    entries_table = _get_entries_table()
    entries_response = entries_table.query(
        IndexName="submissionId-index",
        KeyConditionExpression=Key("submissionId").eq(submission_id),
    )
    entries = entries_response.get("Items", [])

    # Handle pagination for entries
    while "LastEvaluatedKey" in entries_response:
        entries_response = entries_table.query(
            IndexName="submissionId-index",
            KeyConditionExpression=Key("submissionId").eq(submission_id),
            ExclusiveStartKey=entries_response["LastEvaluatedKey"],
        )
        entries.extend(entries_response.get("Items", []))

    existing["entries"] = entries

    return existing


def list_my_submissions(event):
    """List the caller's own timesheet submissions.

    Returns only submissions belonging to the authenticated employee.
    Supports optional filtering by status and periodId.

    Validates: Requirements 6.10, 6.11
    """
    caller = get_caller_identity(event)
    employee_id = caller["userId"]

    table = _get_submissions_table()
    args = event.get("arguments") or {}
    filter_input = args.get("filter") or {}

    # Query by employeeId using the employeeId-periodId-index GSI
    # If periodId filter is provided, use it as the sort key condition
    if "periodId" in filter_input:
        key_condition = (
            Key("employeeId").eq(employee_id)
            & Key("periodId").eq(filter_input["periodId"])
        )
    else:
        key_condition = Key("employeeId").eq(employee_id)

    response = table.query(
        IndexName="employeeId-periodId-index",
        KeyConditionExpression=key_condition,
    )
    items = response.get("Items", [])

    # Handle pagination
    while "LastEvaluatedKey" in response:
        response = table.query(
            IndexName="employeeId-periodId-index",
            KeyConditionExpression=key_condition,
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))

    # Apply additional client-side filters
    if "status" in filter_input:
        items = [i for i in items if i.get("status") == filter_input["status"]]

    return items
