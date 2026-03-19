"""ListAllSubmissions Lambda resolver for AppSync.

Admin/superadmin query to list all timesheet submissions with optional filters.

Environment variables:
    SUBMISSIONS_TABLE: DynamoDB Timesheet_Submissions table name
"""

import os

import boto3
from boto3.dynamodb.conditions import Key

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.auth import ForbiddenError, require_user_type

SUBMISSIONS_TABLE = os.environ.get("SUBMISSIONS_TABLE", "")
dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    try:
        return list_all_submissions(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def list_all_submissions(event):
    """List all submissions for admin/superadmin users with optional filters.

    Validates: Requirements 2.6, 2.7, 2.8, 2.9
    """
    require_user_type(event, ["superadmin", "admin"])
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

    return items
