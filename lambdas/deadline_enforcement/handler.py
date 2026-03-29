"""Deadline Enforcement Lambda for automatic timesheet submission.

Triggered by EventBridge on a scheduled basis. Scans all timesheet periods
where the submissionDeadline has passed and isLocked is false, then:
  1. Auto-submits all Draft submissions (Draft -> Submitted)
  2. Creates Submitted submissions with zero hours for employees without one
  3. Sends under-40-hours email notification to employees
  4. Marks the period as isLocked = true

Environment variables:
    PERIODS_TABLE: DynamoDB Timesheet_Periods table name
    SUBMISSIONS_TABLE: DynamoDB Timesheet_Submissions table name
    ENTRIES_TABLE: DynamoDB Timesheet_Entries table name
    USERS_TABLE: DynamoDB Users table name
    SES_FROM_EMAIL: Sender email address for SES
"""

import logging
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Attr, Key

logger = logging.getLogger()
logger.setLevel(logging.INFO)

PERIODS_TABLE = os.environ.get("PERIODS_TABLE", "")
SUBMISSIONS_TABLE = os.environ.get("SUBMISSIONS_TABLE", "")
ENTRIES_TABLE = os.environ.get("ENTRIES_TABLE", "")
USERS_TABLE = os.environ.get("USERS_TABLE", "")
SES_FROM_EMAIL = os.environ.get("SES_FROM_EMAIL", "")

REQUIRED_WEEKLY_HOURS = Decimal("40")

dynamodb = boto3.resource("dynamodb")
ses_client = boto3.client("ses")


def handler(event, context):
    """EventBridge scheduled event entry point."""
    logger.info("Deadline enforcement Lambda invoked: %s", event)

    now = datetime.now(timezone.utc).isoformat()
    expired_periods = _get_expired_unlocked_periods(now)

    if not expired_periods:
        logger.info("No expired unlocked periods found")
        return {"submittedPeriods": 0}

    submitted_count = 0
    for period in expired_periods:
        period_id = period["periodId"]
        period_string = period.get("periodString", "")
        logger.info("Processing expired period: %s (%s)", period_id, period_string)

        _submit_draft_submissions(period_id, now)
        _create_missing_submitted_submissions(period_id, now)
        _send_under_40_hours_notifications(period_id, period_string)
        _mark_period_locked(period_id, now)
        submitted_count += 1

    logger.info("Deadline enforcement complete. Processed %d period(s)", submitted_count)
    return {"submittedPeriods": submitted_count}


def _get_periods_table():
    return dynamodb.Table(PERIODS_TABLE)


def _get_submissions_table():
    return dynamodb.Table(SUBMISSIONS_TABLE)


def _get_entries_table():
    return dynamodb.Table(ENTRIES_TABLE)


def _get_users_table():
    return dynamodb.Table(USERS_TABLE)


def _get_expired_unlocked_periods(now_iso):
    """Scan for periods where submissionDeadline has passed and isLocked is false."""
    table = _get_periods_table()
    response = table.scan(
        FilterExpression=(
            Attr("submissionDeadline").lt(now_iso)
            & Attr("isLocked").eq(False)
        ),
    )
    items = response.get("Items", [])
    while "LastEvaluatedKey" in response:
        response = table.scan(
            FilterExpression=(
                Attr("submissionDeadline").lt(now_iso)
                & Attr("isLocked").eq(False)
            ),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))
    return items


def _submit_draft_submissions(period_id, now_iso):
    """Auto-submit all Draft submissions for a period (Draft -> Submitted)."""
    table = _get_submissions_table()
    drafts = _query_submissions_by_status(period_id, "Draft")

    for submission in drafts:
        submission_id = submission["submissionId"]
        employee_id = submission.get("employeeId", "unknown")

        table.update_item(
            Key={"submissionId": submission_id},
            UpdateExpression=(
                "SET #status = :submitted, #updatedAt = :now, "
                "#updatedBy = :system"
            ),
            ExpressionAttributeNames={
                "#status": "status",
                "#updatedAt": "updatedAt",
                "#updatedBy": "updatedBy",
            },
            ExpressionAttributeValues={
                ":submitted": "Submitted",
                ":now": now_iso,
                ":system": "SYSTEM_DEADLINE_ENFORCEMENT",
            },
        )
        logger.info(
            "Auto-submitted Draft submission %s for employee %s in period %s",
            submission_id, employee_id, period_id,
        )


def _query_submissions_by_status(period_id, status):
    """Query submissions for a period with a given status."""
    table = _get_submissions_table()
    response = table.query(
        IndexName="periodId-status-index",
        KeyConditionExpression=(
            Key("periodId").eq(period_id) & Key("status").eq(status)
        ),
    )
    items = response.get("Items", [])
    while "LastEvaluatedKey" in response:
        response = table.query(
            IndexName="periodId-status-index",
            KeyConditionExpression=(
                Key("periodId").eq(period_id) & Key("status").eq(status)
            ),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))
    return items


def _get_all_employees():
    """Scan the Users table for all active users with role Employee and userType 'user'."""
    table = _get_users_table()
    filter_expr = Attr("role").eq("Employee") & Attr("status").eq("active") & Attr("userType").eq("user")
    response = table.scan(FilterExpression=filter_expr)
    items = response.get("Items", [])
    while "LastEvaluatedKey" in response:
        response = table.scan(
            FilterExpression=filter_expr,
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))
    return items


def _get_employee_ids_with_submission(period_id):
    """Get employee IDs that already have a submission for a period."""
    table = _get_submissions_table()
    response = table.query(
        IndexName="periodId-status-index",
        KeyConditionExpression=Key("periodId").eq(period_id),
    )
    items = response.get("Items", [])
    while "LastEvaluatedKey" in response:
        response = table.query(
            IndexName="periodId-status-index",
            KeyConditionExpression=Key("periodId").eq(period_id),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))
    return {item["employeeId"] for item in items if "employeeId" in item}


def _create_missing_submitted_submissions(period_id, now_iso):
    """Create Submitted submissions with zero hours for employees without one."""
    all_employees = _get_all_employees()
    employees_with_submission = _get_employee_ids_with_submission(period_id)
    table = _get_submissions_table()

    for employee in all_employees:
        employee_id = employee["userId"]
        if employee_id in employees_with_submission:
            continue

        submission_id = str(uuid.uuid4())
        item = {
            "submissionId": submission_id,
            "periodId": period_id,
            "employeeId": employee_id,
            "status": "Submitted",
            "archived": False,
            "totalHours": Decimal("0"),
            "chargeableHours": Decimal("0"),
            "createdAt": now_iso,
            "updatedAt": now_iso,
            "updatedBy": "SYSTEM_DEADLINE_ENFORCEMENT",
        }
        table.put_item(Item=item)
        logger.info(
            "Created Submitted submission %s with zero hours for employee %s in period %s",
            submission_id, employee_id, period_id,
        )


def _get_submission_total_hours(submission_id):
    """Calculate total hours for a submission from its entries."""
    table = _get_entries_table()
    response = table.query(
        IndexName="submissionId-index",
        KeyConditionExpression=Key("submissionId").eq(submission_id),
    )
    entries = response.get("Items", [])
    while "LastEvaluatedKey" in response:
        response = table.query(
            IndexName="submissionId-index",
            KeyConditionExpression=Key("submissionId").eq(submission_id),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        entries.extend(response.get("Items", []))

    total = Decimal("0")
    for entry in entries:
        total += Decimal(str(entry.get("totalHours", 0)))
    return total


def _get_user_by_id(user_id):
    """Look up a user by userId."""
    table = _get_users_table()
    response = table.get_item(Key={"userId": user_id})
    return response.get("Item")


def _send_under_40_hours_notifications(period_id, period_string):
    """Send email to employees whose total hours < 40 for the period."""
    table = _get_submissions_table()
    # Get all Submitted submissions for this period
    submissions = _query_submissions_by_status(period_id, "Submitted")

    for submission in submissions:
        employee_id = submission["employeeId"]
        submission_id = submission["submissionId"]
        total_hours = _get_submission_total_hours(submission_id)

        if total_hours >= REQUIRED_WEEKLY_HOURS:
            continue

        user = _get_user_by_id(employee_id)
        if not user:
            logger.warning("User %s not found, skipping notification", employee_id)
            continue

        user_type = user.get("userType", "user")
        if user_type in ("admin", "superadmin"):
            logger.info("Skipping under-40-hours notification for %s user %s", user_type, employee_id)
            continue

        email = user.get("email", "")
        full_name = user.get("fullName", "Employee")
        if not email:
            logger.warning("User %s has no email, skipping notification", employee_id)
            continue

        _send_under_hours_email(email, full_name, total_hours, period_string)


def _send_under_hours_email(recipient, full_name, total_hours, period_string):
    """Send under-40-hours notification email to an employee."""
    subject = f"Timesheet Notice: Under 40 Hours - {period_string}"
    body = (
        f"Hi {full_name},\n\n"
        f"Your timesheet for the period {period_string} has been automatically "
        f"submitted with a total of {total_hours} hours.\n\n"
        f"The required weekly hours is 40. You are short by "
        f"{REQUIRED_WEEKLY_HOURS - total_hours} hours.\n\n"
        f"Please contact your supervisor if you have any questions.\n\n"
        f"Regards,\nTimesheet System"
    )
    try:
        ses_client.send_email(
            Source=SES_FROM_EMAIL,
            Destination={"ToAddresses": [recipient]},
            Message={
                "Subject": {"Data": subject},
                "Body": {"Text": {"Data": body}},
            },
        )
        logger.info("Sent under-40h notification to %s (%s hours)", recipient, total_hours)
    except Exception:
        logger.error(
            "Failed to send under-40h email to %s", recipient, exc_info=True,
        )


def _mark_period_locked(period_id, now_iso):
    """Mark a timesheet period as locked after deadline enforcement."""
    table = _get_periods_table()
    table.update_item(
        Key={"periodId": period_id},
        UpdateExpression="SET #isLocked = :locked, #updatedAt = :now",
        ExpressionAttributeNames={
            "#isLocked": "isLocked",
            "#updatedAt": "updatedAt",
        },
        ExpressionAttributeValues={
            ":locked": True,
            ":now": now_iso,
        },
    )
    logger.info("Marked period %s as locked", period_id)
