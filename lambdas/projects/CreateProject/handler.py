"""CreateProject Lambda resolver for AppSync.

Environment variables:
    PROJECTS_TABLE: DynamoDB Projects table name
"""

import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import boto3
from boto3.dynamodb.conditions import Key

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.auth import ForbiddenError, require_user_type

PROJECTS_TABLE = os.environ.get("PROJECTS_TABLE", "")
VALID_STATUSES = {"Active", "Inactive", "Completed"}
dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    try:
        return create_project(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def _validate_planned_hours(value):
    try:
        hours = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"Invalid plannedHours: '{value}'. Must be a positive number")
    if hours <= 0:
        raise ValueError(f"Invalid plannedHours: '{value}'. Must be a positive number")
    return hours


def _check_project_code_unique(table, project_code):
    response = table.query(
        IndexName="projectCode-index",
        KeyConditionExpression=Key("projectCode").eq(project_code),
    )
    for item in response.get("Items", []):
        raise ValueError(f"Project code '{project_code}' is already in use")


def create_project(event):
    """Create a new project. Validates: Requirements 4.1, 4.2, 4.6, 4.8"""
    caller = require_user_type(event, ["superadmin", "admin"])
    args = event["arguments"]["input"]

    project_code = args["projectCode"]
    project_name = args["projectName"]
    start_date = args["startDate"]
    planned_hours = _validate_planned_hours(args["plannedHours"])
    project_manager_id = args["projectManagerId"]
    status = args.get("status", "Active")

    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: '{status}'. Must be one of: {sorted(VALID_STATUSES)}")

    table = dynamodb.Table(PROJECTS_TABLE)
    _check_project_code_unique(table, project_code)

    if caller["userType"] == "superadmin":
        approval_status = "Approved"
    else:
        approval_status = "Pending_Approval"

    now = datetime.now(timezone.utc).isoformat()
    project_id = str(uuid.uuid4())

    item = {
        "projectId": project_id,
        "projectCode": project_code,
        "projectName": project_name,
        "startDate": start_date,
        "plannedHours": planned_hours,
        "projectManagerId": project_manager_id,
        "status": status,
        "approval_status": approval_status,
        "rejectionReason": "",
        "createdAt": now,
        "createdBy": caller["userId"],
        "updatedAt": now,
        "updatedBy": caller["userId"],
    }
    table.put_item(Item=item)
    return item
