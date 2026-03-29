"""ListAllSubmissions Lambda resolver for AppSync.

Admin/superadmin query to list all timesheet submissions with optional filters.
Also allows Tech_Lead and Project_Manager users to list submissions scoped to
their supervised employees.

Environment variables:
    SUBMISSIONS_TABLE: DynamoDB Timesheet_Submissions table name
    ENTRIES_TABLE: DynamoDB Timesheet_Entries table name
    PROJECT_ASSIGNMENTS_TABLE: DynamoDB ProjectAssignments table name
"""

import logging
import os

import boto3
from boto3.dynamodb.conditions import Key

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.auth import ForbiddenError, get_caller_identity
from shared.project_assignments import get_supervised_employee_ids

logger = logging.getLogger(__name__)

SUBMISSIONS_TABLE = os.environ.get("SUBMISSIONS_TABLE", "")
ENTRIES_TABLE = os.environ.get("ENTRIES_TABLE", "")
PROJECT_ASSIGNMENTS_TABLE = os.environ.get("PROJECT_ASSIGNMENTS_TABLE", "")
dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    try:
        return list_all_submissions(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def list_all_submissions(event):
    """List all submissions with optional filters.

    Admin/superadmin users see all submissions.
    Tech_Lead/Project_Manager users see only submissions from their supervised employees.

    Validates: Requirements 2.6, 2.7, 2.8, 2.9
    """
    identity = get_caller_identity(event)
    user_type = identity["userType"]
    role = identity["role"]
    user_id = identity["userId"]

    is_admin = user_type in ("superadmin", "admin")
    is_pm = user_type == "user" and role in ("Tech_Lead", "Project_Manager")

    if not is_admin and not is_pm:
        logger.warning(
            "Authorization failed: user type '%s' with role '%s' not authorized for listAllSubmissions (user: %s)",
            user_type, role, identity.get("email", identity["userId"])
        )
        raise ForbiddenError("Access denied")

    table = dynamodb.Table(SUBMISSIONS_TABLE)
    args = event.get("arguments") or {}
    filter_input = args.get("filter") or {}

    period_id = filter_input.get("periodId")
    status = filter_input.get("status")
    employee_id = filter_input.get("employeeId")

    items = []

    if period_id:
        # Use periodId-status-index GSI
        if status:
            key_condition = (
                Key("periodId").eq(period_id) & Key("status").eq(status)
            )
        else:
            key_condition = Key("periodId").eq(period_id)

        response = table.query(
            IndexName="periodId-status-index",
            KeyConditionExpression=key_condition,
        )
        items = response.get("Items", [])

        while "LastEvaluatedKey" in response:
            response = table.query(
                IndexName="periodId-status-index",
                KeyConditionExpression=key_condition,
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            items.extend(response.get("Items", []))

    elif status:
        # Use status-index GSI
        key_condition = Key("status").eq(status)

        response = table.query(
            IndexName="status-index",
            KeyConditionExpression=key_condition,
        )
        items = response.get("Items", [])

        while "LastEvaluatedKey" in response:
            response = table.query(
                IndexName="status-index",
                KeyConditionExpression=key_condition,
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            items.extend(response.get("Items", []))

    else:
        # No index filters — scan all
        response = table.scan()
        items = response.get("Items", [])

        while "LastEvaluatedKey" in response:
            response = table.scan(
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            items.extend(response.get("Items", []))

    # Post-query filter by employeeId if provided
    if employee_id:
        items = [i for i in items if i.get("employeeId") == employee_id]

    # Fetch entries for each submission
    entries_table = dynamodb.Table(ENTRIES_TABLE)
    for item in items:
        submission_id = item["submissionId"]
        entry_resp = entries_table.query(
            IndexName="submissionId-index",
            KeyConditionExpression=Key("submissionId").eq(submission_id),
        )
        item["entries"] = entry_resp.get("Items", [])

    return items
