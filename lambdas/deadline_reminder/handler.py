"""Deadline Reminder Lambda for timesheet submission reminders.

Triggered by EventBridge 4 hours before the deadline (Friday 1PM MYT = 05:00 UTC).
Sends email reminders to employees who still have Draft submissions.

Environment variables:
    PERIODS_TABLE: DynamoDB Timesheet_Periods table name
    SUBMISSIONS_TABLE: DynamoDB Timesheet_Submissions table name
    USERS_TABLE: DynamoDB Users table name
    SES_FROM_EMAIL: Sender email address for SES
"""

import logging
import os
from datetime import date, datetime, timezone

import boto3
from boto3.dynamodb.conditions import Attr, Key

logger = logging.getLogger()
logger.setLevel(logging.INFO)

PERIODS_TABLE = os.environ.get("PERIODS_TABLE", "")
SUBMISSIONS_TABLE = os.environ.get("SUBMISSIONS_TABLE", "")
USERS_TABLE = os.environ.get("USERS_TABLE", "")
SES_FROM_EMAIL = os.environ.get("SES_FROM_EMAIL", "")

dynamodb = boto3.resource("dynamodb")
ses_client = boto3.client("ses")


def handler(event, context):
    """EventBridge scheduled event entry point (runs Friday 1PM MYT)."""
    logger.info("Deadline reminder Lambda invoked: %s", event)

    # Find the current active period
    period = _get_current_active_period()
    if not period:
        logger.info("No active unlocked period found. Skipping.")
        return {"reminders_sent": 0}

    period_id = period["periodId"]
    period_string = period.get("periodString", "")
    deadline = period.get("submissionDeadline", "")

    logger.info("Sending reminders for period: %s (%s)", period_id, period_string)

    # Find all Draft submissions for this period
    draft_submissions = _get_draft_submissions(period_id)
    if not draft_submissions:
        logger.info("No Draft submissions found. All employees have been active.")
        return {"reminders_sent": 0}

    sent_count = 0
    for submission in draft_submissions:
        employee_id = submission.get("employeeId", "")
        user = _get_user(employee_id)
        if not user:
            continue

        # Skip inactive users
        if user.get("status") == "inactive":
            logger.info("Skipping reminder for inactive user %s", employee_id)
            continue

        email = user.get("email", "")
        full_name = user.get("fullName", "Employee")
        if not email:
            logger.warning("User %s has no email. Skipping.", employee_id)
            continue

        success = _send_reminder_email(email, full_name, period_string)
        if success:
            sent_count += 1

    logger.info("Deadline reminder complete. Sent %d reminder(s).", sent_count)
    return {"reminders_sent": sent_count}


def _get_current_active_period():
    """Find the current active (unlocked) period."""
    table = dynamodb.Table(PERIODS_TABLE)
    today = date.today()

    response = table.scan(FilterExpression=Attr("isLocked").eq(False))
    items = response.get("Items", [])
    while "LastEvaluatedKey" in response:
        response = table.scan(
            FilterExpression=Attr("isLocked").eq(False),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))

    for item in items:
        start = date.fromisoformat(item["startDate"])
        end = date.fromisoformat(item["endDate"])
        if start <= today <= end:
            return item

    return None


def _get_draft_submissions(period_id):
    """Get all Draft submissions for a period."""
    table = dynamodb.Table(SUBMISSIONS_TABLE)
    response = table.query(
        IndexName="periodId-status-index",
        KeyConditionExpression=(
            Key("periodId").eq(period_id) & Key("status").eq("Draft")
        ),
    )
    items = response.get("Items", [])
    while "LastEvaluatedKey" in response:
        response = table.query(
            IndexName="periodId-status-index",
            KeyConditionExpression=(
                Key("periodId").eq(period_id) & Key("status").eq("Draft")
            ),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))
    return items


def _get_user(user_id):
    """Look up a user by userId."""
    table = dynamodb.Table(USERS_TABLE)
    response = table.get_item(Key={"userId": user_id})
    return response.get("Item")


def _send_reminder_email(recipient, full_name, period_string):
    """Send a deadline reminder email."""
    subject = f"Reminder: Timesheet Due Today - {period_string}"
    body = (
        f"Hi {full_name},\n\n"
        f"This is a reminder that your timesheet for the period "
        f"{period_string} is due today at 5:00 PM (MYT).\n\n"
        f"Please fill out your timesheet before the deadline. "
        f"Any unfilled timesheets will be automatically submitted "
        f"with the current hours at the deadline.\n\n"
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
        logger.info("Sent reminder to %s", recipient)
        return True
    except Exception:
        logger.error("Failed to send reminder to %s", recipient, exc_info=True)
        return False
