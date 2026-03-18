"""UpdateTimesheetPeriod Lambda resolver for AppSync.

Environment variables:
    PERIODS_TABLE: DynamoDB Timesheet_Periods table name
"""

import os
from datetime import datetime, timezone

import boto3

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.auth import ForbiddenError, require_user_type
from shared_utils import validate_period_dates, check_no_overlapping_periods

PERIODS_TABLE = os.environ.get("PERIODS_TABLE", "")
dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    try:
        return update_timesheet_period(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def update_timesheet_period(event):
    """Update an existing timesheet period. Validates: Requirements 5.1-5.5"""
    caller = require_user_type(event, ["superadmin"])
    period_id = event["arguments"]["periodId"]
    args = event["arguments"]["input"]
    table = dynamodb.Table(PERIODS_TABLE)

    existing = table.get_item(Key={"periodId": period_id}).get("Item")
    if not existing:
        raise ValueError(f"Period '{period_id}' not found")

    start_date = args.get("startDate", existing["startDate"])
    end_date = args.get("endDate", existing["endDate"])
    submission_deadline = args.get("submissionDeadline", existing["submissionDeadline"])

    dates_changed = (
        start_date != existing["startDate"]
        or end_date != existing["endDate"]
        or submission_deadline != existing["submissionDeadline"]
    )
    if dates_changed:
        validate_period_dates(start_date, end_date, submission_deadline)
        check_no_overlapping_periods(table, start_date, end_date, exclude_period_id=period_id)

    now = datetime.now(timezone.utc).isoformat()
    update_parts = []
    expr_names = {}
    expr_values = {}

    updatable_fields = {
        "startDate": start_date,
        "endDate": end_date,
        "submissionDeadline": submission_deadline,
        "periodString": args.get("periodString"),
        "biweeklyPeriodId": args.get("biweeklyPeriodId"),
        "isLocked": args.get("isLocked"),
    }

    for field_name, value in updatable_fields.items():
        if value is not None:
            placeholder = f":{field_name}"
            alias = f"#{field_name}"
            expr_names[alias] = field_name
            expr_values[placeholder] = value
            update_parts.append(f"{alias} = {placeholder}")

    expr_names["#updatedAt"] = "updatedAt"
    expr_values[":updatedAt"] = now
    update_parts.append("#updatedAt = :updatedAt")

    expr_names["#updatedBy"] = "updatedBy"
    expr_values[":updatedBy"] = caller["userId"]
    update_parts.append("#updatedBy = :updatedBy")

    update_expr = "SET " + ", ".join(update_parts)

    result = table.update_item(
        Key={"periodId": period_id},
        UpdateExpression=update_expr,
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
        ReturnValues="ALL_NEW",
    )
    return result["Attributes"]
