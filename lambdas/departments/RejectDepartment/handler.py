"""RejectDepartment Lambda resolver for AppSync.

Environment variables:
    DEPARTMENTS_TABLE: DynamoDB Departments table name
"""

import os
from datetime import datetime, timezone

import boto3

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.auth import ForbiddenError, require_user_type

DEPARTMENTS_TABLE = os.environ.get("DEPARTMENTS_TABLE", "")
dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    try:
        return reject_department(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def reject_department(event):
    """Reject a Pending_Approval department. Validates: Requirements 4.4, 4.7, 4.8, 4.9"""
    caller = require_user_type(event, ["superadmin"])
    department_id = event["arguments"]["departmentId"]
    reason = event["arguments"].get("reason", "")

    if not reason or not reason.strip():
        raise ValueError("Rejection reason is required")

    table = dynamodb.Table(DEPARTMENTS_TABLE)
    existing = table.get_item(Key={"departmentId": department_id}).get("Item")
    if not existing:
        raise ValueError(f"Department '{department_id}' not found")

    if existing["approval_status"] != "Pending_Approval":
        raise ValueError(
            f"Cannot reject department with approval_status "
            f"'{existing['approval_status']}'. "
            f"Only Pending_Approval departments can be rejected"
        )

    now = datetime.now(timezone.utc).isoformat()

    result = table.update_item(
        Key={"departmentId": department_id},
        UpdateExpression=(
            "SET #approval_status = :approval_status, "
            "#rejectionReason = :rejectionReason, "
            "#updatedAt = :updatedAt, #updatedBy = :updatedBy"
        ),
        ExpressionAttributeNames={
            "#approval_status": "approval_status",
            "#rejectionReason": "rejectionReason",
            "#updatedAt": "updatedAt",
            "#updatedBy": "updatedBy",
        },
        ExpressionAttributeValues={
            ":approval_status": "Rejected",
            ":rejectionReason": reason.strip(),
            ":updatedAt": now,
            ":updatedBy": caller["userId"],
        },
        ReturnValues="ALL_NEW",
    )
    return result["Attributes"]
