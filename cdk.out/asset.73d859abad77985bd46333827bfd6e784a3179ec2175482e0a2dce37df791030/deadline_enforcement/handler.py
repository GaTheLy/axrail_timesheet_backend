"""Deadline Enforcement Lambda for automatic timesheet locking.

Triggered by EventBridge on a scheduled basis. Scans all timesheet periods
where the submissionDeadline has passed and isLocked is false, then:
  1. Locks all Draft submissions for that period
  2. Locks all Submitted submissions for that period
  3. Creates Locked submissions with zero hours for employees without one
  4. Marks the period as isLocked = true

Environment variables:
    PERIODS_TABLE: DynamoDB Timesheet_Periods table name
    SUBMISSIONS_TABLE: DynamoDB Timesheet_Submissions table name
    USERS_TABLE: DynamoDB Users table name
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
USERS_TABLE = os.environ.get("USERS_TABLE", "")

dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    """EventBridge scheduled event entry point.

    Scans for unlocked periods past their submission deadline and
    enforces locking on all associated submissions.
    """
    logger.info("Deadline enforcement Lambda invoked: %s", event)

    now = datetime.now(timezone.utc).isoformat()
    expired_periods = _get_expired_unlocked_periods(now)

    if not expired_periods:
        logger.info("No expired unlocked periods found")
        return {"lockedPeriods": 0}

    locked_count = 0
    for period in expired_periods:
        period_id = period["periodId"]
        logger.info(
            "Processing expired period: %s (%s)",
            period_id,
            period.get("periodString", ""),
        )

        _lock_submissions_for_period(period_id, now)
        _create_missing_locked_submissions(period_id, now)
        _mark_period_locked(period_id, now)
        locked_count += 1

    logger.info("Deadline enforcement complete. Locked %d period(s)", locked_count)
    return {"lockedPeriods": locked_count}


def _get_periods_table():
    """Return the DynamoDB Timesheet_Periods table resource."""
    return dynamodb.Table(PERIODS_TABLE)


def _get_submissions_table():
    """Return the DynamoDB Timesheet_Submissions table resource."""
    return dynamodb.Table(SUBMISSIONS_TABLE)


def _get_users_table():
    """Return the DynamoDB Users table resource."""
    return dynamodb.Table(USERS_TABLE)


def _get_expired_unlocked_periods(now_iso):
    """Scan for periods where submissionDeadline has passed and isLocked is false.

    Args:
        now_iso: Current UTC time as ISO 8601 string.

    Returns:
        List of period items that need locking.

    Validates: Requirements 8.1
    """
    table = _get_periods_table()
    response = table.scan(
        FilterExpression=(
            Attr("submissionDeadline").lt(now_iso)
            & Attr("isLocked").eq(False)
        ),
    )
    items = response.get("Items", [])

    # Handle pagination
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


def _query_submissions_by_status(period_id, status):
    """Query submissions for a period with a given status using periodId-status-index.

    Args:
        period_id: The timesheet period ID.
        status: The submission status to filter by (e.g. 'Draft', 'Submitted').

    Returns:
        List of submission items matching the criteria.
    """
    table = _get_submissions_table()
    response = table.query(
        IndexName="periodId-status-index",
        KeyConditionExpression=(
            Key("periodId").eq(period_id) & Key("status").eq(status)
        ),
    )
    items = response.get("Items", [])

    # Handle pagination
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


def _lock_submissions_for_period(period_id, now_iso):
    """Lock all Draft and Submitted submissions for a given period.

    Queries the periodId-status-index GSI for Draft and Submitted statuses,
    then updates each submission's status to Locked.

    Args:
        period_id: The timesheet period ID.
        now_iso: Current UTC time as ISO 8601 string.

    Validates: Requirements 8.1
    """
    table = _get_submissions_table()

    for status in ("Draft", "Submitted"):
        submissions = _query_submissions_by_status(period_id, status)
        for submission in submissions:
            submission_id = submission["submissionId"]
            employee_id = submission.get("employeeId", "unknown")

            table.update_item(
                Key={"submissionId": submission_id},
                UpdateExpression=(
                    "SET #status = :locked, #updatedAt = :now, "
                    "#updatedBy = :system"
                ),
                ExpressionAttributeNames={
                    "#status": "status",
                    "#updatedAt": "updatedAt",
                    "#updatedBy": "updatedBy",
                },
                ExpressionAttributeValues={
                    ":locked": "Locked",
                    ":now": now_iso,
                    ":system": "SYSTEM_DEADLINE_ENFORCEMENT",
                },
            )

            logger.info(
                "Locked %s submission %s for employee %s in period %s",
                status,
                submission_id,
                employee_id,
                period_id,
            )


def _get_all_employees():
    """Scan the Users table for all users with role Employee.

    Returns:
        List of employee user items.
    """
    table = _get_users_table()
    response = table.scan(
        FilterExpression=Attr("role").eq("Employee"),
    )
    items = response.get("Items", [])

    # Handle pagination
    while "LastEvaluatedKey" in response:
        response = table.scan(
            FilterExpression=Attr("role").eq("Employee"),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))

    return items


def _get_employee_ids_with_submission(period_id):
    """Get the set of employee IDs that already have a submission for a period.

    Queries all statuses via periodId-status-index to collect every employee
    who has any submission for this period.

    Args:
        period_id: The timesheet period ID.

    Returns:
        A set of employeeId strings.
    """
    table = _get_submissions_table()
    # Scan submissions filtered by periodId to get all statuses
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


def _create_missing_locked_submissions(period_id, now_iso):
    """Create Locked submissions with zero hours for employees without one.

    Finds all employees, determines which ones already have a submission
    for the period, and creates a Locked submission for those who don't.

    Args:
        period_id: The timesheet period ID.
        now_iso: Current UTC time as ISO 8601 string.

    Validates: Requirements 8.4
    """
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
            "status": "Locked",
            "archived": False,
            "totalHours": Decimal("0"),
            "chargeableHours": Decimal("0"),
            "approvedBy": "",
            "approvedAt": "",
            "createdAt": now_iso,
            "updatedAt": now_iso,
            "updatedBy": "SYSTEM_DEADLINE_ENFORCEMENT",
        }

        table.put_item(Item=item)

        logger.info(
            "Created Locked submission %s with zero hours for employee %s "
            "in period %s",
            submission_id,
            employee_id,
            period_id,
        )


def _mark_period_locked(period_id, now_iso):
    """Mark a timesheet period as locked after deadline enforcement.

    Args:
        period_id: The timesheet period ID.
        now_iso: Current UTC time as ISO 8601 string.

    Validates: Requirements 8.1
    """
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
