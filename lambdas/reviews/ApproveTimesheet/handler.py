"""ApproveTimesheet Lambda resolver for AppSync.

Environment variables:
    SUBMISSIONS_TABLE: DynamoDB Timesheet_Submissions table name
    USERS_TABLE: DynamoDB Users table name
"""

import os
from datetime import datetime, timezone

import boto3

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.auth import ForbiddenError, require_role
from shared_utils import validate_review_transition

SUBMISSIONS_TABLE = os.environ.get("SUBMISSIONS_TABLE", "")
REVIEWER_ROLES = ["Project_Manager", "Tech_Lead"]
dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    try:
        return approve_timesheet(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def approve_timesheet(event):
    """Approve a submitted timesheet. Validates: Requirements 7.1, 7.5"""
    caller = require_role(event, REVIEWER_ROLES)
    submission_id = event["arguments"]["submissionId"]
    table = dynamodb.Table(SUBMISSIONS_TABLE)

    existing = table.get_item(Key={"submissionId": submission_id}).get("Item")
    if not existing:
        raise ValueError(f"Submission '{submission_id}' not found")

    validate_review_transition(existing["status"], "Approved")
    now = datetime.now(timezone.utc).isoformat()

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
