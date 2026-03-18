"""DeleteDepartment Lambda resolver for AppSync.

Environment variables:
    DEPARTMENTS_TABLE: DynamoDB Departments table name
    USERS_TABLE: DynamoDB Users table name (for association checks)
"""

import os

import boto3
from boto3.dynamodb.conditions import Key

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.auth import ForbiddenError, require_user_type

DEPARTMENTS_TABLE = os.environ.get("DEPARTMENTS_TABLE", "")
USERS_TABLE = os.environ.get("USERS_TABLE", "")

dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    try:
        return delete_department(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def _has_associated_users(department_id):
    users_table = dynamodb.Table(USERS_TABLE)
    response = users_table.query(
        IndexName="departmentId-index",
        KeyConditionExpression=Key("departmentId").eq(department_id),
        Limit=1,
    )
    return len(response.get("Items", [])) > 0


def delete_department(event):
    """Delete a department. Validates: Requirements 3.5, 3.6"""
    caller = require_user_type(event, ["superadmin"])
    department_id = event["arguments"]["departmentId"]
    table = dynamodb.Table(DEPARTMENTS_TABLE)

    existing = table.get_item(Key={"departmentId": department_id}).get("Item")
    if not existing:
        raise ValueError(f"Department '{department_id}' not found")

    if _has_associated_users(department_id):
        raise ValueError(
            f"Cannot delete department '{existing['departmentName']}': "
            "active user associations exist"
        )

    table.delete_item(Key={"departmentId": department_id})
    return True
