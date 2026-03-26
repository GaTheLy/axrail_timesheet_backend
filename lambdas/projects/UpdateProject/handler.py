"""UpdateProject Lambda resolver for AppSync.

Environment variables:
    PROJECTS_TABLE: DynamoDB Projects table name
"""

import os
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
        return update_project(event)
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


def _check_project_code_unique(table, project_code, exclude_project_id=None):
    response = table.query(
        IndexName="projectCode-index",
        KeyConditionExpression=Key("projectCode").eq(project_code),
    )
    for item in response.get("Items", []):
        if item["projectId"] != exclude_project_id:
            raise ValueError(f"Project code '{project_code}' is already in use")


def update_project(event):
    """Update an existing project. Validates: Requirements 4.7, 4.8"""
    caller = require_user_type(event, ["superadmin", "admin"])
    project_id = event["arguments"]["projectId"]
    args = event["arguments"]["input"]
    table = dynamodb.Table(PROJECTS_TABLE)

    existing = table.get_item(Key={"projectId": project_id}).get("Item")
    if not existing:
        raise ValueError(f"Project '{project_id}' not found")

    if existing.get("approval_status") == "Approved" and caller["userType"] != "superadmin":
        raise ValueError("Cannot update project: approved entities cannot be edited")

    new_code = args.get("projectCode")
    if new_code and new_code != existing.get("projectCode"):
        _check_project_code_unique(table, new_code, exclude_project_id=project_id)

    if "plannedHours" in args:
        args["plannedHours"] = _validate_planned_hours(args["plannedHours"])

    if "status" in args and args["status"] not in VALID_STATUSES:
        raise ValueError(f"Invalid status: '{args['status']}'. Must be one of: {sorted(VALID_STATUSES)}")

    now = datetime.now(timezone.utc).isoformat()
    update_parts = []
    expr_names = {}
    expr_values = {":updatedAt": now, ":updatedBy": caller["userId"]}
    update_parts.append("#updatedAt = :updatedAt")
    update_parts.append("#updatedBy = :updatedBy")
    expr_names["#updatedAt"] = "updatedAt"
    expr_names["#updatedBy"] = "updatedBy"

    allowed_fields = ["projectCode", "projectName", "startDate", "plannedHours", "projectManagerId", "status"]
    for field in allowed_fields:
        if field in args:
            placeholder = f":{field}"
            name_placeholder = f"#{field}"
            expr_values[placeholder] = args[field]
            expr_names[name_placeholder] = field
            update_parts.append(f"{name_placeholder} = {placeholder}")

    update_expr = "SET " + ", ".join(update_parts)
    result = table.update_item(
        Key={"projectId": project_id},
        UpdateExpression=update_expr,
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
        ReturnValues="ALL_NEW",
    )
    return result["Attributes"]
