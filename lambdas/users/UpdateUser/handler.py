"""UpdateUser Lambda resolver for AppSync.

Updates an existing user account with role-based authorization.

Environment variables:
    USERS_TABLE: DynamoDB Users table name
    USER_POOL_ID: Cognito User Pool ID
"""

import os
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.auth import ForbiddenError, require_user_type

USERS_TABLE = os.environ.get("USERS_TABLE", "")
USER_POOL_ID = os.environ.get("USER_POOL_ID", "")

VALID_ROLES = {"Project_Manager", "Tech_Lead", "Employee"}
VALID_USER_TYPES = {"superadmin", "admin", "user"}

dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    """AppSync Lambda resolver entry point for updateUser."""
    try:
        return update_user(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def _get_table():
    return dynamodb.Table(USERS_TABLE)


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _validate_enum(value, valid_values, field_name):
    if value not in valid_values:
        raise ValueError(
            f"Invalid {field_name}: '{value}'. Must be one of: {sorted(valid_values)}"
        )


def _check_email_unique(table, email, exclude_user_id=None):
    response = table.query(
        IndexName="email-index",
        KeyConditionExpression=Key("email").eq(email),
    )
    for item in response.get("Items", []):
        if item["userId"] != exclude_user_id:
            raise ValueError(f"Email '{email}' is already in use")


def _authorize_mutation(caller, target_user_type):
    caller_type = caller["userType"]
    if caller_type == "superadmin":
        if target_user_type not in ("admin", "user"):
            raise ForbiddenError(f"Superadmin cannot manage '{target_user_type}' accounts")
    elif caller_type == "admin":
        if target_user_type != "user":
            raise ForbiddenError("Admin can only manage user accounts")
    else:
        raise ForbiddenError("Insufficient permissions to manage users")


def update_user(event):
    """Update an existing user account.

    Validates: Requirements 2.2, 2.5, 2.7
    """
    caller = require_user_type(event, ["superadmin", "admin"])
    user_id = event["arguments"]["userId"]
    args = event["arguments"]["input"]

    table = _get_table()

    existing = table.get_item(Key={"userId": user_id}).get("Item")
    if not existing:
        raise ValueError(f"User '{user_id}' not found")

    if existing.get("approval_status") == "Approved":
        raise ValueError("Cannot update user: approved entities cannot be edited")

    _authorize_mutation(caller, existing["userType"])

    if "userType" in args:
        _validate_enum(args["userType"], VALID_USER_TYPES, "userType")
        _authorize_mutation(caller, args["userType"])

    if "role" in args:
        _validate_enum(args["role"], VALID_ROLES, "role")

    if "status" in args:
        _validate_enum(args["status"], {"active", "inactive"}, "status")

    if "email" in args and args["email"] != existing["email"]:
        _check_email_unique(table, args["email"], exclude_user_id=user_id)

    now = _now_iso()

    update_parts = []
    expr_names = {}
    expr_values = {":updatedAt": now, ":updatedBy": caller["userId"]}
    update_parts.append("#updatedAt = :updatedAt")
    update_parts.append("#updatedBy = :updatedBy")
    expr_names["#updatedAt"] = "updatedAt"
    expr_names["#updatedBy"] = "updatedBy"

    allowed_fields = [
        "fullName", "email", "userType", "role", "status",
        "positionId", "departmentId", "supervisorId",
    ]
    remove_fields = []
    for field in allowed_fields:
        if field in args:
            value = args[field]
            # DynamoDB GSI keys cannot be empty strings; remove the attribute instead
            if field == "supervisorId" and (not value or value == ""):
                remove_fields.append(f"#{field}")
                expr_names[f"#{field}"] = field
                continue
            placeholder = f":{field}"
            name_placeholder = f"#{field}"
            expr_values[placeholder] = value
            expr_names[name_placeholder] = field
            update_parts.append(f"{name_placeholder} = {placeholder}")

    update_expr = "SET " + ", ".join(update_parts)
    if remove_fields:
        update_expr += " REMOVE " + ", ".join(remove_fields)

    result = table.update_item(
        Key={"userId": user_id},
        UpdateExpression=update_expr,
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
        ReturnValues="ALL_NEW",
    )

    return result["Attributes"]
