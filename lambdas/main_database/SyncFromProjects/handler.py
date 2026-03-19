"""SyncFromProjects Lambda — DynamoDB Streams trigger.

Listens to INSERT/MODIFY events on the Projects table and upserts
corresponding records into the Main_Database table.

Field mapping:
    projectId    -> recordId
    projectCode  -> chargeCode
    projectName  -> projectName
    plannedHours -> budgetEffort
    status       -> projectStatus
    (constant)   -> type = "Project"

Environment variables:
    MAIN_DATABASE_TABLE: DynamoDB Main_Database table name
"""

import logging
import os
from datetime import datetime, timezone

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

MAIN_DATABASE_TABLE = os.environ.get("MAIN_DATABASE_TABLE", "")
dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    table = dynamodb.Table(MAIN_DATABASE_TABLE)
    synced = 0

    for record in event.get("Records", []):
        event_name = record.get("eventName")
        if event_name not in ("INSERT", "MODIFY"):
            continue

        new_image = record.get("dynamodb", {}).get("NewImage")
        if not new_image:
            continue

        item = _map_project_to_main_db(new_image)
        table.put_item(Item=item)
        synced += 1

    logger.info("Synced %d project(s) to main_database", synced)
    return {"synced": synced}


def _map_project_to_main_db(new_image):
    """Convert a DynamoDB Streams NewImage (with type descriptors) to a
    flat Main_Database item."""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "recordId": _ddb_val(new_image, "projectId"),
        "type": "Project",
        "chargeCode": _ddb_val(new_image, "projectCode"),
        "projectName": _ddb_val(new_image, "projectName"),
        "budgetEffort": _ddb_num(new_image, "plannedHours"),
        "projectStatus": _ddb_val(new_image, "status"),
        "createdAt": _ddb_val(new_image, "createdAt") or now,
        "updatedAt": now,
        "updatedBy": _ddb_val(new_image, "updatedBy") or "system-sync",
    }


def _ddb_val(image, key):
    """Extract a string value from a DynamoDB Streams typed attribute."""
    attr = image.get(key, {})
    return attr.get("S", "")


def _ddb_num(image, key):
    """Extract a numeric value from a DynamoDB Streams typed attribute."""
    from decimal import Decimal
    attr = image.get(key, {})
    raw = attr.get("N", "0")
    return Decimal(raw)
