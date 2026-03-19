"""Employee Performance Tracking Lambda.

Triggered by DynamoDB Streams on the Timesheet_Submissions table.
When a submission transitions to Submitted status, this handler updates
the Employee_Performance record for the corresponding employee and year
by atomically adding the chargeable and total hours, then
recalculating the YTD chargeability percentage.

Environment variables:
    EMPLOYEE_PERFORMANCE_TABLE: DynamoDB Employee_Performance table name
"""

import logging
import os
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

EMPLOYEE_PERFORMANCE_TABLE = os.environ.get("EMPLOYEE_PERFORMANCE_TABLE", "")

dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    """DynamoDB Streams event entry point.

    Processes stream records from the Timesheet_Submissions table.
    For each record where the NEW status is 'Submitted', updates the
    Employee_Performance table with the submission's hours.
    """
    logger.info("Performance tracking Lambda invoked with %d record(s)",
                len(event.get("Records", [])))

    processed = 0
    for record in event.get("Records", []):
        if _should_process(record):
            _process_approved_submission(record)
            processed += 1

    logger.info("Performance tracking complete. Processed %d record(s)",
                processed)
    return {"processedRecords": processed}


def _get_performance_table():
    """Return the DynamoDB Employee_Performance table resource."""
    return dynamodb.Table(EMPLOYEE_PERFORMANCE_TABLE)


def _should_process(record):
    """Determine if a DynamoDB Stream record should be processed.

    Only processes INSERT or MODIFY events where the new status is
    'Submitted'. Also checks that the old status was not already 'Submitted'
    to avoid duplicate processing on unrelated attribute updates.

    Args:
        record: A single DynamoDB Stream record.

    Returns:
        True if the record represents a transition to Submitted status.
    """
    event_name = record.get("eventName")
    if event_name not in ("INSERT", "MODIFY"):
        return False

    new_image = record.get("dynamodb", {}).get("NewImage")
    if not new_image:
        return False

    new_status = new_image.get("status", {}).get("S", "")
    if new_status != "Submitted":
        return False

    # For MODIFY events, skip if old status was already Submitted
    if event_name == "MODIFY":
        old_image = record.get("dynamodb", {}).get("OldImage", {})
        old_status = old_image.get("status", {}).get("S", "")
        if old_status == "Submitted":
            return False

    return True


def _process_approved_submission(record):
    """Process a single submitted submission and update performance record."""
    new_image = record["dynamodb"]["NewImage"]

    employee_id = new_image.get("employeeId", {}).get("S", "")
    submission_id = new_image.get("submissionId", {}).get("S", "")
    chargeable_hours = _extract_decimal(new_image.get("chargeableHours", {}))
    total_hours = _extract_decimal(new_image.get("totalHours", {}))

    # Determine year from updatedAt timestamp, fall back to current year
    updated_at = new_image.get("updatedAt", {}).get("S", "")
    year = _extract_year(updated_at)

    logger.info(
        "Processing approved submission %s for employee %s: "
        "chargeableHours=%s, totalHours=%s, year=%d",
        submission_id, employee_id, chargeable_hours, total_hours, year,
    )

    _update_performance_record(employee_id, year, chargeable_hours, total_hours)


def _extract_decimal(dynamo_value):
    """Extract a Decimal from a DynamoDB Stream attribute value.

    DynamoDB Streams represent numbers as {"N": "string_value"}.

    Args:
        dynamo_value: A DynamoDB attribute value dict (e.g. {"N": "8.5"}).

    Returns:
        Decimal value, defaulting to Decimal("0") if missing or invalid.
    """
    try:
        return Decimal(dynamo_value.get("N", "0"))
    except Exception:
        return Decimal("0")


def _extract_year(approved_at_iso):
    """Extract the calendar year from an ISO 8601 timestamp string.

    Args:
        approved_at_iso: ISO 8601 timestamp (e.g. "2025-06-15T10:30:00+00:00").

    Returns:
        Integer year. Falls back to current UTC year if parsing fails.
    """
    if approved_at_iso:
        try:
            dt = datetime.fromisoformat(approved_at_iso)
            return dt.year
        except (ValueError, TypeError):
            pass
    return datetime.now(timezone.utc).year


def calculate_chargeability_percentage(ytd_chargeable_hours, ytd_total_hours):
    """Calculate the YTD chargeability percentage.

    Pure function that computes (ytdChargable_hours / ytdTotalHours) * 100,
    rounded to 2 decimal places using ROUND_HALF_UP.

    Args:
        ytd_chargeable_hours: Decimal year-to-date chargeable hours.
        ytd_total_hours: Decimal year-to-date total hours.

    Returns:
        Decimal chargeability percentage, or Decimal("0") if total hours is 0.

    Validates: Requirements 11.2
    """
    if ytd_total_hours > 0:
        return (ytd_chargeable_hours / ytd_total_hours * Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    return Decimal("0")


def _update_performance_record(employee_id, year, chargeable_hours, total_hours):
    """Update or create an Employee_Performance record with atomic increments.

    Uses DynamoDB ADD expressions to atomically increment ytdChargable_hours
    and ytdTotalHours. Then recalculates ytdChargabilityPercentage based on
    the new totals.

    If no record exists for (userId, year), DynamoDB ADD creates it with
    the provided values as initial values (ADD treats missing attributes
    as zero).

    Args:
        employee_id: The employee's userId (partition key).
        year: The calendar year (sort key).
        chargeable_hours: Decimal chargeable hours to add.
        total_hours: Decimal total hours to add.

    Validates: Requirements 11.1, 11.2, 11.3, 11.4
    """
    table = _get_performance_table()
    now = datetime.now(timezone.utc).isoformat()

    # Step 1: Atomically add hours using ADD expression
    # ADD creates the item if it doesn't exist, treating missing numeric
    # attributes as zero.
    result = table.update_item(
        Key={"userId": employee_id, "year": year},
        UpdateExpression=(
            "ADD #chargeable :chargeable, #total :total "
            "SET #updatedAt = :now"
        ),
        ExpressionAttributeNames={
            "#chargeable": "ytdChargable_hours",
            "#total": "ytdTotalHours",
            "#updatedAt": "updatedAt",
        },
        ExpressionAttributeValues={
            ":chargeable": chargeable_hours,
            ":total": total_hours,
            ":now": now,
        },
        ReturnValues="ALL_NEW",
    )

    updated = result["Attributes"]
    new_chargeable = Decimal(str(updated.get("ytdChargable_hours", 0)))
    new_total = Decimal(str(updated.get("ytdTotalHours", 0)))

    # Step 2: Recalculate chargeability percentage
    percentage = calculate_chargeability_percentage(new_chargeable, new_total)

    # Step 3: Update the percentage
    table.update_item(
        Key={"userId": employee_id, "year": year},
        UpdateExpression="SET #pct = :pct",
        ExpressionAttributeNames={
            "#pct": "ytdChargabilityPercentage",
        },
        ExpressionAttributeValues={
            ":pct": percentage,
        },
    )

    logger.info(
        "Updated performance for employee %s, year %d: "
        "ytdChargable_hours=%s, ytdTotalHours=%s, "
        "ytdChargabilityPercentage=%s",
        employee_id, year, new_chargeable, new_total, percentage,
    )
