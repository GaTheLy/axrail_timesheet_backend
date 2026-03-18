"""CreateTimesheetSubmission Lambda resolver for AppSync.

Environment variables:
    SUBMISSIONS_TABLE: DynamoDB Timesheet_Submissions table name
"""

import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.auth import ForbiddenError, get_caller_identity

SUBMISSIONS_TABLE = os.environ.get("SUBMISSIONS_TABLE", "")
dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    try:
        return create_timesheet_submission(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def _check_existing_submission(table, employee_id, period_id):
    response = table.query(
        IndexName="employeeId-periodId-index",
        KeyConditionExpression=(
            Key("employeeId").eq(employee_id) & Key("periodId").eq(period_id)
        ),
    )
    if response.get("Items", []):
        raise ValueError(
            f"A submission already exists for employee '{employee_id}' "
            f"and period '{period_id}'"
        )


def create_timesheet_submission(event):
    """Create a new timesheet submission. Validates: Requirements 6.1, 6.9"""
    caller = get_caller_identity(event)
    employee_id = caller["userId"]
    period_id = event["arguments"]["periodId"]

    if not period_id or not period_id.strip():
        raise ValueError("periodId is required")

    table = dynamodb.Table(SUBMISSIONS_TABLE)
    _check_existing_submission(table, employee_id, period_id)

    now = datetime.now(timezone.utc).isoformat()
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
