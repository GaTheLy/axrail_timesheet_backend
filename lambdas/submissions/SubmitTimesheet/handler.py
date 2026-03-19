"""SubmitTimesheet Lambda resolver for AppSync.

Environment variables:
    SUBMISSIONS_TABLE: DynamoDB Timesheet_Submissions table name
"""

import os
from datetime import datetime, timezone

import boto3

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.auth import ForbiddenError, get_caller_identity

SUBMISSIONS_TABLE = os.environ.get("SUBMISSIONS_TABLE", "")
dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    try:
        return submit_timesheet(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def submit_timesheet(event):
    """Submit a Draft or Rejected timesheet. Validates: Requirements 6.4, 6.6"""
    caller = get_caller_identity(event)
    submission_id = event["arguments"]["submissionId"]
    table = dynamodb.Table(SUBMISSIONS_TABLE)

    existing = table.get_item(Key={"submissionId": submission_id}).get("Item")
    if not existing:
        raise ValueError(f"Submission '{submission_id}' not found")

    if existing["employeeId"] != caller["userId"]:
        raise ForbiddenError("You can only submit your own timesheet submissions")

    if existing.get("archived") is True:
        raise ValueError(
            "Cannot submit an archived timesheet. Archived submissions are read-only"
        )

    allowed_source_statuses = {"Draft"}
    if existing["status"] not in allowed_source_statuses:
        raise ValueError(
            f"Cannot submit timesheet with status '{existing['status']}'. "
            f"Only timesheets with status {sorted(allowed_source_statuses)} can be submitted"
        )

    now = datetime.now(timezone.utc).isoformat()

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
