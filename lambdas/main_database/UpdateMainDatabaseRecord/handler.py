"""UpdateMainDatabaseRecord Lambda resolver for AppSync.

Environment variables:
    MAIN_DATABASE_TABLE: DynamoDB Main_Database table name
"""

import os
from datetime import datetime, timezone

import boto3

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.auth import ForbiddenError, require_user_type
from shared_utils import get_table, validate_budget_effort

MAIN_DATABASE_TABLE = os.environ.get("MAIN_DATABASE_TABLE", "")
dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    try:
        return update_main_database_record(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def update_main_database_record(event):
    """Update a record. Validates: Requirements 14.2"""
    caller = require_user_type(event, ["superadmin"])
    record_id = event["arguments"]["id"]
    args = event["arguments"]["input"]
    table = get_table()

    existing = table.get_item(Key={"recordId": record_id}).get("Item")
    if not existing:
        raise ValueError(f"Record '{record_id}' not found")

    now = datetime.now(timezone.utc).isoformat()
    update_parts = ["#updatedAt = :updatedAt", "#updatedBy = :updatedBy"]
    expr_names = {"#updatedAt": "updatedAt", "#updatedBy": "updatedBy"}
    expr_values = {":updatedAt": now, ":updatedBy": caller["userId"]}

    allowed_fields = {
        "type": "type", "chargeCode": "chargeCode",
        "projectName": "projectName", "budgetEffort": "budgetEffort",
        "projectStatus": "projectStatus",
    }

    for field, attr in allowed_fields.items():
        if field in args:
            value = args[field]
            if field == "budgetEffort":
                value = validate_budget_effort(value)
            placeholder = f":{attr}"
            name_placeholder = f"#{attr}"
            expr_values[placeholder] = value
            expr_names[name_placeholder] = attr
            update_parts.append(f"{name_placeholder} = {placeholder}")

    update_expr = "SET " + ", ".join(update_parts)
    result = table.update_item(
        Key={"recordId": record_id},
        UpdateExpression=update_expr,
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
        ReturnValues="ALL_NEW",
    )
    return result["Attributes"]
