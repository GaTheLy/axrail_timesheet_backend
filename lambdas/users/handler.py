"""User Management Lambda resolver for AppSync.

Handles CRUD operations for user accounts with role-based authorization.
Superadmins can manage admin and user accounts; Admins can manage user accounts only.

Environment variables:
    USERS_TABLE: DynamoDB Users table name
    USER_POOL_ID: Cognito User Pool ID
"""

import os
import uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key

# Add parent directory to path for shared imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.auth import ForbiddenError, get_caller_identity, require_user_type

USERS_TABLE = os.environ.get("USERS_TABLE", "")
USER_POOL_ID = os.environ.get("USER_POOL_ID", "")

VALID_ROLES = {"Project_Manager", "Tech_Lead", "Employee"}
VALID_USER_TYPES = {"superadmin", "admin", "user"}

dynamodb = boto3.resource("dynamodb")
cognito = boto3.client("cognito-idp")


def handler(event, context):
    """AppSync Lambda resolver entry point.

    Routes to the appropriate operation based on event['info']['fieldName'].
    """
    field = event["info"]["fieldName"]
    resolvers = {
        "createUser": create_user,
        "updateUser": update_user,
        "deleteUser": delete_user,
        "getUser": get_user,
        "listUsers": list_users,
    }

    resolver = resolvers.get(field)
    if not resolver:
        raise ValueError(f"Unknown field: {field}")

    try:
        return resolver(event)
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


def _check_email_unique(table, email, exclude_user_id=None):
    """Query the email-index GSI to ensure email uniqueness.

    Args:
        table: DynamoDB Table resource.
        email: Email address to check.
        exclude_user_id: Optional userId to exclude (for updates).

    Raises:
        ValueError: If the email is already in use by another user.
    """
    response = table.query(
        IndexName="email-index",
        KeyConditionExpression=Key("email").eq(email),
    )
    for item in response.get("Items", []):
        if item["userId"] != exclude_user_id:
            raise ValueError(f"Email '{email}' is already in use")


def _authorize_mutation(caller, target_user_type):
    """Validate that the caller can perform a mutation on the target user type.

    Authorization rules:
        - Superadmin can manage admin and user accounts
        - Admin can manage user accounts only
        - User cannot manage any accounts

    Args:
        caller: Caller identity dict from get_caller_identity.
        target_user_type: The userType of the target account.

    Raises:
        ForbiddenError: If the caller lacks permission.
    """
    caller_type = caller["userType"]

    if caller_type == "superadmin":
        if target_user_type not in ("admin", "user"):
            raise ForbiddenError(
                f"Superadmin cannot manage '{target_user_type}' accounts"
            )
    elif caller_type == "admin":
        if target_user_type != "user":
            raise ForbiddenError(
                "Admin can only manage user accounts"
            )
    else:
        raise ForbiddenError("Insufficient permissions to manage users")


def create_user(event):
    """Create a new user account.

    Validates caller permissions, email uniqueness, role/userType enums,
    writes to DynamoDB Users table, and creates a Cognito user.

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
    supervisor_id = args.get("supervisorId", "")

    # Validate enums
    _validate_enum(target_user_type, VALID_USER_TYPES, "userType")
    _validate_enum(role, VALID_ROLES, "role")

    # Authorize caller for the target user type
    _authorize_mutation(caller, target_user_type)

    table = _get_table()

    # Check email uniqueness
    _check_email_unique(table, email)

    now = _now_iso()
    user_id = str(uuid.uuid4())

    item = {
        "userId": user_id,
        "email": email,
        "fullName": full_name,
        "userType": target_user_type,
        "role": role,
        "positionId": position_id,
        "departmentId": department_id,
        "supervisorId": supervisor_id,
        "createdAt": now,
        "createdBy": caller["userId"],
        "updatedAt": now,
        "updatedBy": caller["userId"],
    }

    # Write to DynamoDB
    table.put_item(Item=item)

    # Create Cognito user
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
            {"Name": "sub", "Value": user_id},
        ],
        DesiredDeliveryMediums=["EMAIL"],
    )

    # Add user to the appropriate Cognito group
    cognito.admin_add_user_to_group(
        UserPoolId=USER_POOL_ID,
        Username=email,
        GroupName=target_user_type,
    )

    return item


def update_user(event):
    """Update an existing user account.

    Validates caller permissions, persists changes with updatedBy/updatedAt.

    Validates: Requirements 2.2, 2.5, 2.7
    """
    caller = require_user_type(event, ["superadmin", "admin"])
    user_id = event["arguments"]["userId"]
    args = event["arguments"]["input"]

    table = _get_table()

    # Fetch existing user to check target userType
    existing = table.get_item(Key={"userId": user_id}).get("Item")
    if not existing:
        raise ValueError(f"User '{user_id}' not found")

    # Authorize caller against the existing user's type
    _authorize_mutation(caller, existing["userType"])

    # If userType is being changed, also authorize for the new type
    if "userType" in args:
        _validate_enum(args["userType"], VALID_USER_TYPES, "userType")
        _authorize_mutation(caller, args["userType"])

    if "role" in args:
        _validate_enum(args["role"], VALID_ROLES, "role")

    # If email is being changed, check uniqueness
    if "email" in args and args["email"] != existing["email"]:
        _check_email_unique(table, args["email"], exclude_user_id=user_id)

    now = _now_iso()

    # Build update expression dynamically
    update_parts = []
    expr_names = {}
    expr_values = {":updatedAt": now, ":updatedBy": caller["userId"]}
    update_parts.append("#updatedAt = :updatedAt")
    update_parts.append("#updatedBy = :updatedBy")
    expr_names["#updatedAt"] = "updatedAt"
    expr_names["#updatedBy"] = "updatedBy"

    allowed_fields = [
        "fullName", "email", "userType", "role",
        "positionId", "departmentId", "supervisorId",
    ]
    for field in allowed_fields:
        if field in args:
            placeholder = f":{field}"
            name_placeholder = f"#{field}"
            expr_values[placeholder] = args[field]
            expr_names[name_placeholder] = field
            update_parts.append(f"{name_placeholder} = {placeholder}")

    update_expr = "SET " + ", ".join(update_parts)

    result = table.update_item(
        Key={"userId": user_id},
        UpdateExpression=update_expr,
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
        ReturnValues="ALL_NEW",
    )

    return result["Attributes"]


def delete_user(event):
    """Delete a user account.

    Validates caller permissions, removes from DynamoDB Users table and Cognito.

    Validates: Requirements 2.3, 2.6, 2.7
    """
    caller = require_user_type(event, ["superadmin", "admin"])
    user_id = event["arguments"]["userId"]

    table = _get_table()

    # Fetch existing user to check target userType
    existing = table.get_item(Key={"userId": user_id}).get("Item")
    if not existing:
        raise ValueError(f"User '{user_id}' not found")

    # Authorize caller against the target user's type
    _authorize_mutation(caller, existing["userType"])

    # Remove from DynamoDB
    table.delete_item(Key={"userId": user_id})

    # Remove from Cognito
    try:
        cognito.admin_delete_user(
            UserPoolId=USER_POOL_ID,
            Username=existing["email"],
        )
    except cognito.exceptions.UserNotFoundException:
        # User may have already been removed from Cognito
        pass

    return True


def get_user(event):
    """Retrieve a single user by userId.

    Validates: Requirements 2.1
    """
    user_id = event["arguments"]["userId"]
    table = _get_table()

    result = table.get_item(Key={"userId": user_id})
    item = result.get("Item")
    if not item:
        return None
    return item


def list_users(event):
    """List users with optional filtering.

    Supports filtering by departmentId, userType, role, and supervisorId.

    Validates: Requirements 2.1, 2.4
    """
    table = _get_table()
    args = event.get("arguments") or {}
    filter_input = args.get("filter") or {}

    # Use GSI for departmentId or supervisorId filters for efficiency
    if "departmentId" in filter_input:
        response = table.query(
            IndexName="departmentId-index",
            KeyConditionExpression=Key("departmentId").eq(
                filter_input["departmentId"]
            ),
        )
        items = response.get("Items", [])
    elif "supervisorId" in filter_input:
        response = table.query(
            IndexName="supervisorId-index",
            KeyConditionExpression=Key("supervisorId").eq(
                filter_input["supervisorId"]
            ),
        )
        items = response.get("Items", [])
    else:
        response = table.scan()
        items = response.get("Items", [])

    # Apply additional client-side filters
    if "userType" in filter_input:
        items = [i for i in items if i.get("userType") == filter_input["userType"]]
    if "role" in filter_input:
        items = [i for i in items if i.get("role") == filter_input["role"]]

    return {"items": items}
