"""Timesheet Period Management Lambda resolver for AppSync.

Handles CRUD operations for timesheet periods with Superadmin-only
authorization for mutations. Enforces date validation rules:
- startDate must be a Saturday
- endDate must be a Friday
- endDate must be exactly startDate + 6 days
- submissionDeadline must be >= endDate
- No overlapping periods

Environment variables:
    PERIODS_TABLE: DynamoDB Timesheet_Periods table name
"""

import os
import uuid
from datetime import datetime, date, timedelta, timezone

import boto3
from boto3.dynamodb.conditions import Key

# Add parent directory to path for shared imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.auth import ForbiddenError, require_user_type

PERIODS_TABLE = os.environ.get("PERIODS_TABLE", "")

dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    """AppSync Lambda resolver entry point.

    Routes to the appropriate operation based on event['info']['fieldName'].
    """
    field = event["info"]["fieldName"]
    resolvers = {
        "createTimesheetPeriod": create_timesheet_period,
        "updateTimesheetPeriod": update_timesheet_period,
        "listTimesheetPeriods": list_timesheet_periods,
        "getCurrentPeriod": get_current_period,
    }

    resolver = resolvers.get(field)
    if not resolver:
        raise ValueError(f"Unknown field: {field}")

    try:
        return resolver(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def _get_table():
    """Return the DynamoDB Timesheet_Periods table resource."""
    return dynamodb.Table(PERIODS_TABLE)


def _now_iso():
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _parse_date(date_str):
    """Parse an ISO 8601 date string into a date object.

    Args:
        date_str: Date string in YYYY-MM-DD format.

    Returns:
        A datetime.date object.

    Raises:
        ValueError: If the date string is not valid.
    """
    return date.fromisoformat(date_str)


def _validate_period_dates(start_date_str, end_date_str, submission_deadline_str):
    """Validate all date constraints for a timesheet period.

    Args:
        start_date_str: Start date in YYYY-MM-DD format.
        end_date_str: End date in YYYY-MM-DD format.
        submission_deadline_str: Submission deadline in YYYY-MM-DD or ISO 8601 format.

    Raises:
        ValueError: If any date constraint is violated.

    Validates: Requirements 5.2, 5.3, 5.4
    """
    start_date = _parse_date(start_date_str)
    end_date = _parse_date(end_date_str)

    # Parse submission deadline — may include time component
    deadline_date = _parse_date(submission_deadline_str[:10])

    # startDate must be a Saturday (weekday() == 5 in Python)
    if start_date.weekday() != 5:
        raise ValueError(
            f"startDate '{start_date_str}' is not a Saturday. "
            f"Got weekday {start_date.strftime('%A')}"
        )

    # endDate must be a Friday (weekday() == 4 in Python)
    if end_date.weekday() != 4:
        raise ValueError(
            f"endDate '{end_date_str}' is not a Friday. "
            f"Got weekday {end_date.strftime('%A')}"
        )

    # endDate must be exactly startDate + 6 days
    expected_end = start_date + timedelta(days=6)
    if end_date != expected_end:
        raise ValueError(
            f"endDate '{end_date_str}' must be exactly 6 days after "
            f"startDate '{start_date_str}'. Expected '{expected_end.isoformat()}'"
        )

    # submissionDeadline must be >= endDate
    if deadline_date < end_date:
        raise ValueError(
            f"submissionDeadline '{submission_deadline_str}' must be on or after "
            f"endDate '{end_date_str}'"
        )


def _check_no_overlapping_periods(table, start_date_str, end_date_str, exclude_period_id=None):
    """Check that no existing period overlaps with the given date range.

    Scans all periods and checks for date range overlap. Two periods overlap
    if one starts before the other ends and ends after the other starts.

    Args:
        table: DynamoDB Timesheet_Periods Table resource.
        start_date_str: Start date of the new/updated period (YYYY-MM-DD).
        end_date_str: End date of the new/updated period (YYYY-MM-DD).
        exclude_period_id: Optional periodId to exclude (for updates).

    Raises:
        ValueError: If an overlapping period is found.

    Validates: Requirements 5.5
    """
    new_start = _parse_date(start_date_str)
    new_end = _parse_date(end_date_str)

    # Scan all periods to check for overlaps
    response = table.scan()
    items = response.get("Items", [])

    # Handle pagination
    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response.get("Items", []))

    for item in items:
        if exclude_period_id and item["periodId"] == exclude_period_id:
            continue

        existing_start = _parse_date(item["startDate"])
        existing_end = _parse_date(item["endDate"])

        # Two ranges overlap if: new_start <= existing_end AND new_end >= existing_start
        if new_start <= existing_end and new_end >= existing_start:
            raise ValueError(
                f"Period overlaps with existing period "
                f"'{item.get('periodString', item['periodId'])}' "
                f"({item['startDate']} to {item['endDate']})"
            )


def create_timesheet_period(event):
    """Create a new timesheet period.

    Validates Superadmin access, enforces date constraints (Saturday start,
    Friday end, 6-day span, deadline >= endDate), and checks for overlapping
    periods.

    Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5
    """
    caller = require_user_type(event, ["superadmin"])
    args = event["arguments"]["input"]

    start_date = args["startDate"]
    end_date = args["endDate"]
    submission_deadline = args["submissionDeadline"]
    period_string = args["periodString"]
    biweekly_period_id = args.get("biweeklyPeriodId", "")

    # Validate date constraints
    _validate_period_dates(start_date, end_date, submission_deadline)

    table = _get_table()

    # Check for overlapping periods
    _check_no_overlapping_periods(table, start_date, end_date)

    now = _now_iso()
    period_id = str(uuid.uuid4())

    item = {
        "periodId": period_id,
        "startDate": start_date,
        "endDate": end_date,
        "submissionDeadline": submission_deadline,
        "periodString": period_string,
        "biweeklyPeriodId": biweekly_period_id,
        "isLocked": False,
        "createdAt": now,
        "createdBy": caller["userId"],
    }

    table.put_item(Item=item)

    return item


def update_timesheet_period(event):
    """Update an existing timesheet period.

    Validates Superadmin access. If date fields are changed, re-validates
    all date constraints and checks for overlapping periods.

    Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5
    """
    caller = require_user_type(event, ["superadmin"])
    period_id = event["arguments"]["periodId"]
    args = event["arguments"]["input"]

    table = _get_table()

    # Fetch existing period
    existing = table.get_item(Key={"periodId": period_id}).get("Item")
    if not existing:
        raise ValueError(f"Period '{period_id}' not found")

    # Determine effective dates (use new values if provided, else existing)
    start_date = args.get("startDate", existing["startDate"])
    end_date = args.get("endDate", existing["endDate"])
    submission_deadline = args.get("submissionDeadline", existing["submissionDeadline"])

    # Re-validate dates if any date field changed
    dates_changed = (
        start_date != existing["startDate"]
        or end_date != existing["endDate"]
        or submission_deadline != existing["submissionDeadline"]
    )
    if dates_changed:
        _validate_period_dates(start_date, end_date, submission_deadline)
        _check_no_overlapping_periods(table, start_date, end_date, exclude_period_id=period_id)

    now = _now_iso()

    # Build update expression dynamically
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

    # Always set updatedAt and updatedBy
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


def list_timesheet_periods(event):
    """List timesheet periods with optional filtering.

    All authenticated users can query periods. Supports filtering by
    isLocked and biweeklyPeriodId.

    Validates: Requirements 5.1
    """
    table = _get_table()

    args = event.get("arguments") or {}
    filter_input = args.get("filter") or {}

    # If no filters, scan all
    if not filter_input:
        response = table.scan()
        items = response.get("Items", [])
        while "LastEvaluatedKey" in response:
            response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
            items.extend(response.get("Items", []))
        return items

    # Build filter expression for scan
    filter_parts = []
    expr_names = {}
    expr_values = {}

    if "isLocked" in filter_input:
        expr_names["#isLocked"] = "isLocked"
        expr_values[":isLocked"] = filter_input["isLocked"]
        filter_parts.append("#isLocked = :isLocked")

    if "biweeklyPeriodId" in filter_input:
        expr_names["#biweeklyPeriodId"] = "biweeklyPeriodId"
        expr_values[":biweeklyPeriodId"] = filter_input["biweeklyPeriodId"]
        filter_parts.append("#biweeklyPeriodId = :biweeklyPeriodId")

    scan_kwargs = {}
    if filter_parts:
        scan_kwargs["FilterExpression"] = " AND ".join(filter_parts)
        scan_kwargs["ExpressionAttributeNames"] = expr_names
        scan_kwargs["ExpressionAttributeValues"] = expr_values

    response = table.scan(**scan_kwargs)
    items = response.get("Items", [])
    while "LastEvaluatedKey" in response:
        scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
        response = table.scan(**scan_kwargs)
        items.extend(response.get("Items", []))

    return items


def get_current_period(event):
    """Return the period where the current date falls between startDate and endDate.

    Scans all periods and finds the one containing today's date.
    Returns None if no current period exists.

    Validates: Requirements 5.1
    """
    table = _get_table()
    today = date.today()

    response = table.scan()
    items = response.get("Items", [])
    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response.get("Items", []))

    for item in items:
        start = _parse_date(item["startDate"])
        end = _parse_date(item["endDate"])
        if start <= today <= end:
            return item

    return None
