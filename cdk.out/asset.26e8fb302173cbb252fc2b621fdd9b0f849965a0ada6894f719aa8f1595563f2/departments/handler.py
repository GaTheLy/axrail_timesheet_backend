"""Department Management Lambda resolver for AppSync.

Handles CRUD operations for departments with Superadmin-only authorization.
Enforces unique department names and prevents deletion of departments
with associated users.

Environment variables:
    DEPARTMENTS_TABLE: DynamoDB Departments table name
    USERS_TABLE: DynamoDB Users table name (for association checks)
"""

import os
import uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key

# Add parent directory to path for shared imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.auth import ForbiddenError, require_user_type

DEPARTMENTS_TABLE = os.environ.get("DEPARTMENTS_TABLE", "")
USERS_TABLE = os.environ.get("USERS_TABLE", "")

dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    """AppSync Lambda resolver entry point.

    Routes to the appropriate operation based on event['info']['fieldName'].
    """
    field = event["info"]["fieldName"]
    resolvers = {
        "createDepartment": create_department,
        "updateDepartment": update_department,
        "deleteDepartment": delete_department,
        "listDepartments": list_departments,
    }

    resolver = resolvers.get(field)
    if not resolver:
        raise ValueError(f"Unknown field: {field}")

    try:
        return resolver(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def _get_departments_table():
    """Return the DynamoDB Departments table resource."""
    return dynamodb.Table(DEPARTMENTS_TABLE)


def _get_users_table():
    """Return the DynamoDB Users table resource."""
    return dynamodb.Table(USERS_TABLE)


def _now_iso():
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _check_department_name_unique(table, department_name, exclude_department_id=None):
    """Query the departmentName-index GSI to ensure name uniqueness.

    Args:
        table: DynamoDB Departments Table resource.
        department_name: Department name to check.
        exclude_department_id: Optional departmentId to exclude (for updates).

    Raises:
        ValueError: If the department name is already in use.
    """
    response = table.query(
        IndexName="departmentName-index",
        KeyConditionExpression=Key("departmentName").eq(department_name),
    )
    for item in response.get("Items", []):
        if item["departmentId"] != exclude_department_id:
            raise ValueError(
                f"Department name '{department_name}' is already in use"
            )


def _has_associated_users(department_id):
    """Check if a department has associated users via departmentId-index GSI.

    Args:
        department_id: The departmentId to check.

    Returns:
        True if users are associated with this department, False otherwise.
    """
    users_table = _get_users_table()
    response = users_table.query(
        IndexName="departmentId-index",
        KeyConditionExpression=Key("departmentId").eq(department_id),
        Limit=1,
    )
    return len(response.get("Items", [])) > 0


def create_department(event):
    """Create a new department.

    Validates Superadmin access, enforces unique department name,
    writes to DynamoDB Departments table.

    Validates: Requirements 3.1, 3.3, 3.6
    """
    caller = require_user_type(event, ["superadmin"])
    args = event["arguments"]["input"]

    department_name = args["departmentName"]

    table = _get_departments_table()

    # Check department name uniqueness
    _check_department_name_unique(table, department_name)

    now = _now_iso()
    department_id = str(uuid.uuid4())

    item = {
        "departmentId": department_id,
        "departmentName": department_name,
        "createdAt": now,
        "createdBy": caller["userId"],
        "updatedAt": now,
        "updatedBy": caller["userId"],
    }

    table.put_item(Item=item)

    return item


def update_department(event):
    """Update an existing department.

    Validates Superadmin access, enforces unique department name if changed,
    persists changes with updatedBy/updatedAt.

    Validates: Requirements 3.1, 3.3, 3.6
    """
    caller = require_user_type(event, ["superadmin"])
    department_id = event["arguments"]["departmentId"]
    args = event["arguments"]["input"]

    table = _get_departments_table()

    # Fetch existing department
    existing = table.get_item(Key={"departmentId": department_id}).get("Item")
    if not existing:
        raise ValueError(f"Department '{department_id}' not found")

    # If department name is being changed, check uniqueness
    new_name = args.get("departmentName")
    if new_name and new_name != existing["departmentName"]:
        _check_department_name_unique(table, new_name, exclude_department_id=department_id)

    now = _now_iso()

    # Build update expression dynamically
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


def delete_department(event):
    """Delete a department.

    Validates Superadmin access, rejects deletion if department has
    associated users.

    Validates: Requirements 3.5, 3.6
    """
    caller = require_user_type(event, ["superadmin"])
    department_id = event["arguments"]["departmentId"]

    table = _get_departments_table()

    # Fetch existing department
    existing = table.get_item(Key={"departmentId": department_id}).get("Item")
    if not existing:
        raise ValueError(f"Department '{department_id}' not found")

    # Check for associated users
    if _has_associated_users(department_id):
        raise ValueError(
            f"Cannot delete department '{existing['departmentName']}': "
            "active user associations exist"
        )

    table.delete_item(Key={"departmentId": department_id})

    return True


def list_departments(event):
    """List all departments.

    All authenticated users can query departments.

    Validates: Requirements 3.1
    """
    table = _get_departments_table()
    response = table.scan()
    return response.get("Items", [])
