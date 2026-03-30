"""UpdateDepartment Lambda resolver for AppSync.

Environment variables:
    DEPARTMENTS_TABLE: DynamoDB Departments table name
"""

import os
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.auth import ForbiddenError, require_user_type

DEPARTMENTS_TABLE = os.environ.get("DEPARTMENTS_TABLE", "")

dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    try:
        return update_department(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def _get_departments_table():
    return dynamodb.Table(DEPARTMENTS_TABLE)


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _check_department_name_unique(table, department_name, exclude_department_id=None):
    """Check for case-insensitive duplicate department names."""
    response = table.scan(ProjectionExpression="departmentId, departmentName")
    items = response.get("Items", [])
    while "LastEvaluatedKey" in response:
        response = table.scan(
            ProjectionExpression="departmentId, departmentName",
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))
    for item in items:
        if item.get("departmentName", "").lower() == department_name.lower():
            if item["departmentId"] != exclude_department_id:
                raise ValueError(f"Department name '{department_name}' is already in use")


def update_department(event):
    """Update an existing department. Validates: Requirements 3.1, 3.3, 3.6"""
    caller = require_user_type(event, ["superadmin", "admin"])
    department_id = event["arguments"]["departmentId"]
    args = event["arguments"]["input"]
    table = _get_departments_table()

    existing = table.get_item(Key={"departmentId": department_id}).get("Item")
    if not existing:
        raise ValueError(f"Department '{department_id}' not found")

    if existing.get("approval_status") == "Approved" and caller["userType"] != "superadmin":
        raise ValueError("Cannot update department: approved entities cannot be edited")

    new_name = args.get("departmentName")
    if new_name and new_name != existing["departmentName"]:
        _check_department_name_unique(table, new_name, exclude_department_id=department_id)

    now = _now_iso()
    update_parts = []
    expr_names = {}
    expr_values = {":updatedAt": now, ":updatedBy": caller["userId"]}
    update_parts.append("#updatedAt = :updatedAt")
    update_parts.append("#updatedBy = :updatedBy")
    expr_names["#updatedAt"] = "updatedAt"
    expr_names["#updatedBy"] = "updatedBy"

    if new_name:
        expr_values[":departmentName"] = new_name
        expr_names["#departmentName"] = "departmentName"
        update_parts.append("#departmentName = :departmentName")

    update_expr = "SET " + ", ".join(update_parts)

    result = table.update_item(
        Key={"departmentId": department_id},
        UpdateExpression=update_expr,
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
        ReturnValues="ALL_NEW",
    )
    return result["Attributes"]
