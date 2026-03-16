"""Biweekly Timesheet Archival Lambda.

Triggered by EventBridge after report distribution completes for a
Biweekly_Period. Finds the most recently ended biweekly period, queries
all submissions for periods in that cycle, and sets archived = true on
each submission. All entries and metadata are retained.

Environment variables:
    SUBMISSIONS_TABLE: DynamoDB Timesheet_Submissions table name
    PERIODS_TABLE: DynamoDB Timesheet_Periods table name
"""

import logging
import os
from datetime import date, datetime, timezone

import boto3
from boto3.dynamodb.conditions import Attr, Key

logger = logging.getLogger()
logger.setLevel(logging.INFO)

SUBMISSIONS_TABLE = os.environ.get("SUBMISSIONS_TABLE", "")
PERIODS_TABLE = os.environ.get("PERIODS_TABLE", "")

dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    """EventBridge scheduled event entry point.

    Finds the most recently ended biweekly period, queries all submissions
    for periods in that cycle, and archives them.

    Validates: Requirements 13.1, 13.2
    """
    logger.info("Archival Lambda invoked: %s", event)

    today = date.today()

    # Find the most recently ended biweekly period
    biweekly_period_id = _find_ended_biweekly_period(today)
    if not biweekly_period_id:
        logger.info("No ended biweekly period found for archival")
        return {"archivedSubmissions": 0}

    # Get all period IDs belonging to this biweekly cycle
    period_ids = _get_period_ids_for_biweekly(biweekly_period_id)
    if not period_ids:
        logger.info(
            "No periods found for biweeklyPeriodId '%s'", biweekly_period_id
        )
        return {"archivedSubmissions": 0}

    logger.info(
        "Archiving submissions for biweeklyPeriodId '%s' (%d period(s))",
        biweekly_period_id,
        len(period_ids),
    )

    # Archive all submissions for each period
    now_iso = datetime.now(timezone.utc).isoformat()
    total_archived = 0

    for period_id in period_ids:
        count = _archive_submissions_for_period(period_id, now_iso)
        total_archived += count

    logger.info(
        "Archival complete. Archived %d submission(s) for biweeklyPeriodId '%s'",
        total_archived,
        biweekly_period_id,
    )

    return {"archivedSubmissions": total_archived}


def _get_periods_table():
    """Return the DynamoDB Timesheet_Periods table resource."""
    return dynamodb.Table(PERIODS_TABLE)


def _get_submissions_table():
    """Return the DynamoDB Timesheet_Submissions table resource."""
    return dynamodb.Table(SUBMISSIONS_TABLE)


def _find_ended_biweekly_period(today):
    """Find the biweeklyPeriodId of the most recently ended biweekly cycle.

    Scans the Periods table for periods whose endDate has passed and that
    have a biweeklyPeriodId set. Returns the biweeklyPeriodId whose latest
    endDate is the most recent one that has already passed.

    Args:
        today: The current date (datetime.date).

    Returns:
        The biweeklyPeriodId string, or None if no ended period is found.

    Validates: Requirements 13.1
    """
    table = _get_periods_table()

    response = table.scan()
    items = response.get("Items", [])

    # Handle pagination
    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response.get("Items", []))

    # Filter to periods with a biweeklyPeriodId whose endDate has passed
    ended_periods = []
    for item in items:
        biweekly_id = item.get("biweeklyPeriodId", "")
        if not biweekly_id:
            continue

        try:
            end_date = date.fromisoformat(item["endDate"])
        except (KeyError, ValueError):
            continue

        if end_date < today:
            ended_periods.append((biweekly_id, end_date))

    if not ended_periods:
        return None

    # Group by biweeklyPeriodId and find the one with the latest endDate
    biweekly_max_end = {}
    for biweekly_id, end_date in ended_periods:
        if biweekly_id not in biweekly_max_end or end_date > biweekly_max_end[biweekly_id]:
            biweekly_max_end[biweekly_id] = end_date

    # Return the biweeklyPeriodId with the most recent max endDate
    most_recent = max(biweekly_max_end.items(), key=lambda x: x[1])
    return most_recent[0]


def _get_period_ids_for_biweekly(biweekly_period_id):
    """Get all periodIds belonging to a biweekly cycle.

    Args:
        biweekly_period_id: The biweekly period identifier.

    Returns:
        A list of periodId strings.
    """
    table = _get_periods_table()

    response = table.scan(
        FilterExpression=Attr("biweeklyPeriodId").eq(biweekly_period_id),
    )
    items = response.get("Items", [])

    # Handle pagination
    while "LastEvaluatedKey" in response:
        response = table.scan(
            FilterExpression=Attr("biweeklyPeriodId").eq(biweekly_period_id),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))

    return [item["periodId"] for item in items]


def _get_all_submissions_for_period(period_id):
    """Query all submissions for a given period using periodId-status-index.

    Queries across all statuses by using only the partition key.

    Args:
        period_id: The timesheet period ID.

    Returns:
        A list of submission items.
    """
    table = _get_submissions_table()

    response = table.query(
        IndexName="periodId-status-index",
        KeyConditionExpression=Key("periodId").eq(period_id),
    )
    items = response.get("Items", [])

    # Handle pagination
    while "LastEvaluatedKey" in response:
        response = table.query(
            IndexName="periodId-status-index",
            KeyConditionExpression=Key("periodId").eq(period_id),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))

    return items


def _archive_submissions_for_period(period_id, now_iso):
    """Archive all submissions for a given period.

    Sets archived = true on each submission. Retains all entries and metadata.

    Args:
        period_id: The timesheet period ID.
        now_iso: Current UTC time as ISO 8601 string.

    Returns:
        The number of submissions archived.

    Validates: Requirements 13.1, 13.2
    """
    submissions = _get_all_submissions_for_period(period_id)
    table = _get_submissions_table()
    archived_count = 0

    for submission in submissions:
        submission_id = submission["submissionId"]

        # Skip already archived submissions
        if submission.get("archived") is True:
            logger.info(
                "Submission %s already archived, skipping", submission_id
            )
            continue

        table.update_item(
            Key={"submissionId": submission_id},
            UpdateExpression=(
                "SET #archived = :archived, #updatedAt = :now, "
                "#updatedBy = :system"
            ),
            ExpressionAttributeNames={
                "#archived": "archived",
                "#updatedAt": "updatedAt",
                "#updatedBy": "updatedBy",
            },
            ExpressionAttributeValues={
                ":archived": True,
                ":now": now_iso,
                ":system": "SYSTEM_ARCHIVAL",
            },
        )

        logger.info(
            "Archived submission %s (employee: %s, status: %s) in period %s",
            submission_id,
            submission.get("employeeId", "unknown"),
            submission.get("status", "unknown"),
            period_id,
        )
        archived_count += 1

    return archived_count
