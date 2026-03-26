"""ListPendingTimesheets Lambda resolver for AppSync.

Environment variables:
    SUBMISSIONS_TABLE: DynamoDB Timesheet_Submissions table name
    PROJECT_ASSIGNMENTS_TABLE: DynamoDB Timesheet_ProjectAssignments table name
"""

import os

import boto3
from boto3.dynamodb.conditions import Key

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.auth import ForbiddenError, require_role
from shared.project_assignments import get_supervised_employee_ids

SUBMISSIONS_TABLE = os.environ.get("SUBMISSIONS_TABLE", "")
PROJECT_ASSIGNMENTS_TABLE = os.environ.get("PROJECT_ASSIGNMENTS_TABLE", "")
REVIEWER_ROLES = ["Project_Manager", "Tech_Lead"]
dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    try:
        return list_pending_timesheets(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def _get_supervised_employee_ids(reviewer_id):
    return get_supervised_employee_ids(PROJECT_ASSIGNMENTS_TABLE, reviewer_id)


def list_pending_timesheets(event):
    """List pending timesheets for supervised employees. Validates: Requirements 7.4"""
    caller = require_role(event, REVIEWER_ROLES)
    reviewer_id = caller["userId"]
    employee_ids = _get_supervised_employee_ids(reviewer_id)
    if not employee_ids:
        return []

    table = dynamodb.Table(SUBMISSIONS_TABLE)
    response = table.query(
        IndexName="status-index",
        KeyConditionExpression=Key("status").eq("Submitted"),
    )
    items = response.get("Items", [])
    while "LastEvaluatedKey" in response:
        response = table.query(
            IndexName="status-index",
            KeyConditionExpression=Key("status").eq("Submitted"),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))

    supervised_set = set(employee_ids)
    pending = [item for item in items if item.get("employeeId") in supervised_set]
    return pending
