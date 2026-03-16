"""Position Management Lambda resolver for AppSync.

Handles CRUD operations for positions with Superadmin-only authorization.
Enforces unique position names via positionName-index GSI.

Environment variables:
    POSITIONS_TABLE: DynamoDB Positions table name
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

POSITIONS_TABLE = os.environ.get("POSITIONS_TABLE", "")

dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    """AppSync Lambda resolver entry point.

    Routes to the appropriate operation based on event['info']['fieldName'].
    """
    field = event["info"]["fieldName"]
    resolvers = {
        "createPosition": create_position,
        "updatePosition": update_position,
        "deletePosition": delete_position,
        "listPositions": list_positions,
    }

    resolver = resolvers.get(field)
    if not resolver:
        raise ValueError(f"Unknown field: {field}")

    try:
        return resolver(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def _get_positions_table():
    """Return the DynamoDB Positions table resource."""
    return dynamodb.Table(POSITIONS_TABLE)


def _now_iso():
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _check_position_name_unique(table, position_name, exclude_position_id=None):
    """Query the positionName-index GSI to ensure name uniqueness.

    Args:
        table: DynamoDB Positions Table resource.
        position_name: Position name to check.
        exclude_position_id: Optional positionId to exclude (for updates).

    Raises:
        ValueError: If the position name is already in use.
    """
    response = table.query(
        IndexName="positionName-index",
        KeyConditionExpression=Key("positionName").eq(position_name),
    )
    for item in response.get("Items", []):
        if item["positionId"] != exclude_position_id:
            raise ValueError(
                f"Position name '{position_name}' is already in use"
            )


def create_position(event):
    """Create a new position.

    Validates Superadmin access, enforces unique position name,
    writes to DynamoDB Positions table.

    Validates: Requirements 3.2, 3.4, 3.6
    """
    caller = require_user_type(event, ["superadmin"])
    args = event["arguments"]["input"]

    position_name = args["positionName"]
    description = args.get("description", "")

    table = _get_positions_table()

    # Check position name uniqueness
    _check_position_name_unique(table, position_name)

    now = _now_iso()
    position_id = str(uuid.uuid4())

    item = {
        "positionId": position_id,
        "positionName": position_name,
        "description": description,
        "createdAt": now,
        "createdBy": caller["userId"],
        "updatedAt": now,
        "updatedBy": caller["userId"],
    }

    table.put_item(Item=item)

    return item


def update_position(event):
    """Update an existing position.

    Validates Superadmin access, enforces unique position name if changed,
    persists changes with updatedBy/updatedAt.

    Validates: Requirements 3.2, 3.4, 3.6
    """
    caller = require_user_type(event, ["superadmin"])
    position_id = event["arguments"]["positionId"]
    args = event["arguments"]["input"]

    table = _get_positions_table()

    # Fetch existing position
    existing = table.get_item(Key={"positionId": position_id}).get("Item")
    if not existing:
        raise ValueError(f"Position '{position_id}' not found")

    # If position name is being changed, check uniqueness
    new_name = args.get("positionName")
    if new_name and new_name != existing["positionName"]:
        _check_position_name_unique(table, new_name, exclude_position_id=position_id)

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
        expr_values[":positionName"] = new_name
        expr_names["#positionName"] = "positionName"
        update_parts.append("#positionName = :positionName")

    new_description = args.get("description")
    if new_description is not None:
        expr_values[":description"] = new_description
        expr_names["#description"] = "description"
        update_parts.append("#description = :description")

    update_expr = "SET " + ", ".join(update_parts)

    result = table.update_item(
        Key={"positionId": position_id},
        UpdateExpression=update_expr,
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
        ReturnValues="ALL_NEW",
    )

    return result["Attributes"]


def delete_position(event):
    """Delete a position.

    Validates Superadmin access, removes position from DynamoDB.

    Validates: Requirements 3.2, 3.6
    """
    caller = require_user_type(event, ["superadmin"])
    position_id = event["arguments"]["positionId"]

    table = _get_positions_table()

    # Fetch existing position
    existing = table.get_item(Key={"positionId": position_id}).get("Item")
    if not existing:
        raise ValueError(f"Position '{position_id}' not found")

    table.delete_item(Key={"positionId": position_id})

    return True


def list_positions(event):
    """List all positions.

    All authenticated users can query positions.

    Validates: Requirements 3.2
    """
    table = _get_positions_table()
    response = table.scan()
    return response.get("Items", [])
