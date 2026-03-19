"""DeactivateUser Lambda resolver for AppSync.

Sets a user's status to inactive and disables their Cognito account.

Environment variables:
    USERS_TABLE: DynamoDB Users table name
    USER_POOL_ID: Cognito User Pool ID
"""

import os
from datetime import datetime, timezone

import boto3

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.auth import ForbiddenError, require_user_type

USERS_TABLE = os.environ.get("USERS_TABLE", "")
USER_POOL_ID = os.environ.get("USER_POOL_ID", "")

dynamodb = boto3.resource("dynamodb")
cognito = boto3.client("cognito-idp")


def handler(event, context):
    """AppSync Lambda resolver entry point for deactivateUser."""
    try:
        return deactivate_user(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def _get_table():
    return dynamodb.Table(USERS_TABLE)


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


def deactivate_user(event):
    """Deactivate a user account (soft delete).

    Sets status to inactive and disables the Cognito account.
    The user's data remains visible for historical queries.
    """
    caller = require_user_type(event, ["superadmin", "admin"])
    user_id = event["arguments"]["userId"]

    table = _get_table()
    existing = table.get_item(Key={"userId": user_id}).get("Item")
    if not existing:
        raise ValueError(f"User '{user_id}' not found")

    _authorize_mutation(caller, existing["userType"])

    if existing.get("status") == "inactive":
        raise ValueError(f"User '{user_id}' is already inactive")

    now = datetime.now(timezone.utc).isoformat()

    result = table.update_item(
        Key={"userId": user_id},
        UpdateExpression="SET #status = :status, #updatedAt = :now, #updatedBy = :by",
        ExpressionAttributeNames={
            "#status": "status",
            "#updatedAt": "updatedAt",
            "#updatedBy": "updatedBy",
        },
        ExpressionAttributeValues={
            ":status": "inactive",
            ":now": now,
            ":by": caller["userId"],
        },
        ReturnValues="ALL_NEW",
    )

    # Disable the Cognito account
    try:
        cognito.admin_disable_user(
            UserPoolId=USER_POOL_ID,
            Username=existing["email"],
        )
    except cognito.exceptions.UserNotFoundException:
        pass

    return result["Attributes"]
