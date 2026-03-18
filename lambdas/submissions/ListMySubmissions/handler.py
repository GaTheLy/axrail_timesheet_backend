"""ListMySubmissions Lambda resolver for AppSync.

Environment variables:
    SUBMISSIONS_TABLE: DynamoDB Timesheet_Submissions table name
"""

import os

import boto3
from boto3.dynamodb.conditions import Key

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.auth import ForbiddenError, get_caller_identity

SUBMISSIONS_TABLE = os.environ.get("SUBMISSIONS_TABLE", "")
dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    try:
        return list_my_submissions(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def list_my_submissions(event):
    """List the caller's own submissions. Validates: Requirements 6.10, 6.11"""
    caller = get_caller_identity(event)
    employee_id = caller["userId"]
    table = dynamodb.Table(SUBMISSIONS_TABLE)
    args = event.get("arguments") or {}
    filter_input = args.get("filter") or {}

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

    while "LastEvaluatedKey" in response:
        response = table.query(
            IndexName="employeeId-periodId-index",
            KeyConditionExpression=key_condition,
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))

    if "status" in filter_input:
        items = [i for i in items if i.get("status") == filter_input["status"]]

    return items
