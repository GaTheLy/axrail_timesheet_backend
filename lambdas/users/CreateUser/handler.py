"""CreateUser Lambda resolver for AppSync.

Creates a new user account with role-based authorization.
Superadmins can create admin and user accounts; Admins can create user accounts only.

Environment variables:
    USERS_TABLE: DynamoDB Users table name
    USER_POOL_ID: Cognito User Pool ID
"""

import os
import uuid
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
cognito = boto3.client("cognito-idp")


def handler(event, context):
    """AppSync Lambda resolver entry point for createUser."""
    try:
        return create_user(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def _get_table():
    """Return the DynamoDB Users table resource."""
    return dynamodb.Table(USERS_TABLE)


def _now_iso():
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _validate_enum(value, valid_values, field_name):
    """Raise ValueError if value is not in the valid set."""
    if value not in valid_values:
        raise ValueError(
            f"Invalid {field_name}: '{value}'. Must be one of: {sorted(valid_values)}"
        )


def _check_email_unique(table, email):
    """Query the email-index GSI to ensure email uniqueness."""
    response = table.query(
        IndexName="email-index",
        KeyConditionExpression=Key("email").eq(email),
    )
    for item in response.get("Items", []):
        raise ValueError(f"Email '{email}' is already in use")


ALLOWED_EMAIL_DOMAIN = "@axrail.com"


def _validate_email_domain(email):
    """Raise ValueError if email is not from the allowed domain."""
    if not email.lower().endswith(ALLOWED_EMAIL_DOMAIN):
        raise ValueError("Only @axrail.com email addresses are allowed")


def _authorize_mutation(caller, target_user_type):
    """Validate that the caller can perform a mutation on the target user type."""
    caller_type = caller["userType"]
    if caller_type == "superadmin":
        if target_user_type not in ("admin", "user"):
            raise ForbiddenError(f"Superadmin cannot manage '{target_user_type}' accounts")
    elif caller_type == "admin":
        if target_user_type != "user":
            raise ForbiddenError("Admin can only manage user accounts")
    else:
        raise ForbiddenError("Insufficient permissions to manage users")


def create_user(event):
    """Create a new user account.

    Validates: Requirements 2.1, 2.4, 2.7, 2.8, 2.9, 2.10
    """
    caller = require_user_type(event, ["superadmin", "admin"])
    args = event["arguments"]["input"]

    target_user_type = args["userType"]
    role = args["role"]
    email = args["email"]
    full_name = args["fullName"]
    position_id = args.get("positionId", "")
    department_id = args.get("departmentId", "")
    supervisor_id = args.get("supervisorId") or None

    _validate_enum(target_user_type, VALID_USER_TYPES, "userType")
    _validate_enum(role, VALID_ROLES, "role")
    _authorize_mutation(caller, target_user_type)

    _validate_email_domain(email)

    table = _get_table()
    _check_email_unique(table, email)

    now = _now_iso()
    user_id = str(uuid.uuid4())

    item = {
        "userId": user_id,
        "email": email,
        "fullName": full_name,
        "userType": target_user_type,
        "role": role,
        "status": "active",
        "positionId": position_id,
        "departmentId": department_id,
        "createdAt": now,
        "createdBy": caller["userId"],
        "updatedAt": now,
        "updatedBy": caller["userId"],
    }
    if supervisor_id:
        item["supervisorId"] = supervisor_id

    table.put_item(Item=item)

    cognito.admin_create_user(
        UserPoolId=USER_POOL_ID,
        Username=email,
        UserAttributes=[
            {"Name": "email", "Value": email},
            {"Name": "email_verified", "Value": "true"},
            {"Name": "custom:userType", "Value": target_user_type},
            {"Name": "custom:role", "Value": role},
            {"Name": "custom:departmentId", "Value": department_id},
            {"Name": "custom:positionId", "Value": position_id},
        ],
        DesiredDeliveryMediums=["EMAIL"],
    )

    cognito.admin_add_user_to_group(
        UserPoolId=USER_POOL_ID,
        Username=email,
        GroupName=target_user_type,
    )

    return item
