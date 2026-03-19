"""Auto-Provisioning Lambda for weekly timesheet setup.

Triggered by EventBridge every Monday. Automatically:
  1. Creates a new timesheet period (Mon-Fri) for the current week
  2. Creates Draft submissions for all employees
  3. Deadline is auto-set to Friday 5PM MYT (09:00 UTC)

Environment variables:
    PERIODS_TABLE: DynamoDB Timesheet_Periods table name
    SUBMISSIONS_TABLE: DynamoDB Timesheet_Submissions table name
    USERS_TABLE: DynamoDB Users table name
"""

import logging
import os
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Attr, Key

logger = logging.getLogger()
logger.setLevel(logging.INFO)

PERIODS_TABLE = os.environ.get("PERIODS_TABLE", "")
SUBMISSIONS_TABLE = os.environ.get("SUBMISSIONS_TABLE", "")
USERS_TABLE = os.environ.get("USERS_TABLE", "")

dynamodb = boto3.resource("dynamodb")

# Deadline: Friday 5PM MYT = Friday 09:00 UTC
DEADLINE_HOUR_UTC = 9


def handler(event, context):
    """EventBridge scheduled event entry point (runs every Monday)."""
    logger.info("Auto-provisioning Lambda invoked: %s", event)

    today = date.today()
    # Ensure we're creating for the current week (Mon-Fri)
    # If triggered on a non-Monday, adjust to the current week's Monday
    days_since_monday = today.weekday()
    monday = today - timedelta(days=days_since_monday)
    friday = monday + timedelta(days=4)

    start_date = monday.isoformat()
    end_date = friday.isoformat()

    logger.info("Creating period for %s to %s", start_date, end_date)

    # Check if period already exists for this week
    periods_table = dynamodb.Table(PERIODS_TABLE)
    if _period_exists(periods_table, start_date, end_date):
        logger.info("Period already exists for %s to %s. Skipping.", start_date, end_date)
        return {"created": False, "reason": "period_already_exists"}

    # Create the period
    period_id = _create_period(periods_table, start_date, end_date, monday, friday)

    # Create Draft submissions for all employees
    employees = _get_all_employees()
    submission_count = _create_submissions_for_employees(period_id, employees)

    logger.info(
        "Auto-provisioning complete. Period: %s, Submissions created: %d",
        period_id, submission_count,
    )
    return {
        "created": True,
        "periodId": period_id,
        "submissionsCreated": submission_count,
    }


def _period_exists(table, start_date, end_date):
    """Check if a period already exists for the given date range."""
    response = table.scan(
        FilterExpression=(
            Attr("startDate").eq(start_date) & Attr("endDate").eq(end_date)
        ),
    )
    return len(response.get("Items", [])) > 0


def _create_period(table, start_date, end_date, monday, friday):
    """Create a new timesheet period."""
    now = datetime.now(timezone.utc).isoformat()
    period_id = str(uuid.uuid4())

    # Compute deadline: Friday 5PM MYT = Friday 09:00 UTC
    deadline = datetime(
        friday.year, friday.month, friday.day,
        DEADLINE_HOUR_UTC, 0, 0,
        tzinfo=timezone.utc,
    )

    period_string = f"{monday.strftime('%b %d')} - {friday.strftime('%b %d, %Y')}"

    # Compute biweekly period ID based on ISO week
    iso_year, iso_week, _ = monday.isocalendar()
    biweekly_period_id = f"{iso_year}-W{iso_week:02d}"

    item = {
        "periodId": period_id,
        "startDate": start_date,
        "endDate": end_date,
        "submissionDeadline": deadline.isoformat(),
        "periodString": period_string,
        "biweeklyPeriodId": biweekly_period_id,
        "isLocked": False,
        "createdAt": now,
        "createdBy": "SYSTEM_AUTO_PROVISIONING",
    }
    table.put_item(Item=item)
    logger.info("Created period %s: %s", period_id, period_string)
    return period_id


def _get_all_employees():
    """Get all active users (Employee, Project_Manager, Tech_Lead)."""
    table = dynamodb.Table(USERS_TABLE)
    filter_expr = Attr("status").eq("active")
    response = table.scan(FilterExpression=filter_expr)
    items = response.get("Items", [])
    while "LastEvaluatedKey" in response:
        response = table.scan(
            FilterExpression=filter_expr,
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))
    return items


def _create_submissions_for_employees(period_id, employees):
    """Create Draft submissions for all employees."""
    table = dynamodb.Table(SUBMISSIONS_TABLE)
    now = datetime.now(timezone.utc).isoformat()
    count = 0

    for employee in employees:
        employee_id = employee["userId"]
        submission_id = str(uuid.uuid4())

        item = {
            "submissionId": submission_id,
            "periodId": period_id,
            "employeeId": employee_id,
            "status": "Draft",
            "archived": False,
            "totalHours": Decimal("0"),
            "chargeableHours": Decimal("0"),
            "createdAt": now,
            "updatedAt": now,
            "updatedBy": "SYSTEM_AUTO_PROVISIONING",
        }
        table.put_item(Item=item)
        count += 1
        logger.info(
            "Created Draft submission %s for employee %s",
            submission_id, employee_id,
        )

    return count
