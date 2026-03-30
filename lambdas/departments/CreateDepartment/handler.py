"""CreateDepartment Lambda resolver for AppSync.

Environment variables:
    DEPARTMENTS_TABLE: DynamoDB Departments table name
    USERS_TABLE: DynamoDB Users table name (for association checks)
"""

import os
import uuid
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
        return create_department(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def _get_departments_table():
    return dynamodb.Table(DEPARTMENTS_TABLE)


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _check_department_name_unique(table, department_name):
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
            raise ValueError(f"Department name '{department_name}' is already in use")


def create_department(event):
    """Create a new department. Validates: Requirements 2.1, 2.5, 2.9, 3.1"""
    caller = require_user_type(event, ["superadmin", "admin"])
    args = event["arguments"]["input"]
    department_name = args["departmentName"]
    table = _get_departments_table()
    _check_department_name_unique(table, department_name)

    now = _now_iso()
    department_id = str(uuid.uuid4())

    approval_status = "Approved" if caller["userType"] == "superadmin" else "Pending_Approval"

    item = {
        "departmentId": department_id,
        "departmentName": department_name,
        "approval_status": approval_status,
        "rejectionReason": "",
        "createdAt": now,
        "createdBy": caller["userId"],
        "updatedAt": now,
        "updatedBy": caller["userId"],
    }
    table.put_item(Item=item)
    return item
