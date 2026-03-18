"""CreatePosition Lambda resolver for AppSync.

Environment variables:
    POSITIONS_TABLE: DynamoDB Positions table name
"""

import os
import uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.auth import ForbiddenError, require_user_type

POSITIONS_TABLE = os.environ.get("POSITIONS_TABLE", "")
dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    try:
        return create_position(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def _check_position_name_unique(table, position_name):
    response = table.query(
        IndexName="positionName-index",
        KeyConditionExpression=Key("positionName").eq(position_name),
    )
    for item in response.get("Items", []):
        raise ValueError(f"Position name '{position_name}' is already in use")


def create_position(event):
    """Create a new position. Validates: Requirements 3.2, 3.4, 3.6"""
    caller = require_user_type(event, ["superadmin"])
    args = event["arguments"]["input"]
    position_name = args["positionName"]
    description = args.get("description", "")
    table = dynamodb.Table(POSITIONS_TABLE)
    _check_position_name_unique(table, position_name)

    now = datetime.now(timezone.utc).isoformat()
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
