"""Report Distribution Config Lambda resolver for AppSync.

Handles reading and updating the singleton Report_Distribution_Config record.
Superadmin-only access for updates; any authenticated user can read.

Environment variables:
    REPORT_DISTRIBUTION_CONFIG_TABLE: DynamoDB Report_Distribution_Config table name
"""

import os
from datetime import datetime, timezone

import boto3

# Add parent directory to path for shared imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.auth import ForbiddenError, get_caller_identity, require_user_type

REPORT_DISTRIBUTION_CONFIG_TABLE = os.environ.get(
    "REPORT_DISTRIBUTION_CONFIG_TABLE", ""
)

dynamodb = boto3.resource("dynamodb")

CONFIG_ID = "default"


def handler(event, context):
    """AppSync Lambda resolver entry point.

    Routes to the appropriate operation based on event['info']['fieldName'].
    """
    field = event["info"]["fieldName"]
    resolvers = {
        "updateReportDistributionConfig": update_report_distribution_config,
        "getReportDistributionConfig": get_report_distribution_config,
    }

    resolver = resolvers.get(field)
    if not resolver:
        raise ValueError(f"Unknown field: {field}")

    try:
        return resolver(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def _get_table():
    """Return the DynamoDB Report_Distribution_Config table resource."""
    return dynamodb.Table(REPORT_DISTRIBUTION_CONFIG_TABLE)


def _now_iso():
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def update_report_distribution_config(event):
    """Update the report distribution configuration.

    Superadmin only. Persists schedule_cron_expression, recipient_emails,
    and enabled flag to the singleton config record.

    Validates: Requirements 12.4, 12.5, 12.7
    """
    caller = require_user_type(event, ["superadmin"])
    args = event["arguments"]["input"]

    table = _get_table()
    now = _now_iso()

    # Build update expression dynamically
    update_parts = []
    expr_names = {}
    expr_values = {":updatedAt": now, ":updatedBy": caller["userId"]}
    update_parts.append("#updatedAt = :updatedAt")
    update_parts.append("#updatedBy = :updatedBy")
    expr_names["#updatedAt"] = "updatedAt"
    expr_names["#updatedBy"] = "updatedBy"

    if "schedule_cron_expression" in args:
        cron = args["schedule_cron_expression"]
        if not isinstance(cron, str) or not cron.strip():
            raise ValueError("schedule_cron_expression must be a non-empty string")
        expr_values[":schedule_cron_expression"] = cron.strip()
        expr_names["#schedule_cron_expression"] = "schedule_cron_expression"
        update_parts.append("#schedule_cron_expression = :schedule_cron_expression")

    if "recipient_emails" in args:
        emails = args["recipient_emails"]
        if not isinstance(emails, list):
            raise ValueError("recipient_emails must be a list of strings")
        for email in emails:
            if not isinstance(email, str) or not email.strip():
                raise ValueError("Each recipient email must be a non-empty string")
        expr_values[":recipient_emails"] = [e.strip() for e in emails]
        expr_names["#recipient_emails"] = "recipient_emails"
        update_parts.append("#recipient_emails = :recipient_emails")

    if "enabled" in args:
        enabled = args["enabled"]
        if not isinstance(enabled, bool):
            raise ValueError("enabled must be a boolean")
        expr_values[":enabled"] = enabled
        expr_names["#enabled"] = "enabled"
        update_parts.append("#enabled = :enabled")

    update_expr = "SET " + ", ".join(update_parts)

    result = table.update_item(
        Key={"configId": CONFIG_ID},
        UpdateExpression=update_expr,
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
        ReturnValues="ALL_NEW",
    )

    return result["Attributes"]


def get_report_distribution_config(event):
    """Get the current report distribution configuration.

    Any authenticated user can read the config.

    Validates: Requirements 12.5
    """
    # Verify the caller is authenticated
    get_caller_identity(event)

    table = _get_table()
    response = table.get_item(Key={"configId": CONFIG_ID})
    item = response.get("Item")

    if not item:
        # Return a default config if none exists yet
        return {
            "configId": CONFIG_ID,
            "schedule_cron_expression": "",
            "recipient_emails": [],
            "enabled": False,
        }

    return item
