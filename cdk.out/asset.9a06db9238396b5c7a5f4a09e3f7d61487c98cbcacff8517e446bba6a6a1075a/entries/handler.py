"""Timesheet Entry Management Lambda resolver for AppSync.

Handles adding, updating, and removing timesheet entries.
Validates submission status, project approval, daily hours constraints,
max entries per submission, and computes row totals.

Environment variables:
    ENTRIES_TABLE: DynamoDB Timesheet_Entries table name
    SUBMISSIONS_TABLE: DynamoDB Timesheet_Submissions table name
    PROJECTS_TABLE: DynamoDB Projects table name
"""

import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import boto3
from boto3.dynamodb.conditions import Key

# Add parent directory to path for shared imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.auth import ForbiddenError, get_caller_identity

ENTRIES_TABLE = os.environ.get("ENTRIES_TABLE", "")
SUBMISSIONS_TABLE = os.environ.get("SUBMISSIONS_TABLE", "")
PROJECTS_TABLE = os.environ.get("PROJECTS_TABLE", "")

DAY_FIELDS = ("saturday", "sunday", "monday", "tuesday", "wednesday", "thursday", "friday")
MAX_ENTRIES_PER_SUBMISSION = 27
MAX_DAILY_HOURS = Decimal("24.0")
EDITABLE_STATUSES = {"Draft", "Rejected"}

dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    """AppSync Lambda resolver entry point.

    Routes to the appropriate operation based on event['info']['fieldName'].
    """
    field = event["info"]["fieldName"]
    resolvers = {
        "addTimesheetEntry": add_timesheet_entry,
        "updateTimesheetEntry": update_timesheet_entry,
        "removeTimesheetEntry": remove_timesheet_entry,
    }

    resolver = resolvers.get(field)
    if not resolver:
        raise ValueError(f"Unknown field: {field}")

    try:
        return resolver(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def _get_entries_table():
    """Return the DynamoDB Timesheet_Entries table resource."""
    return dynamodb.Table(ENTRIES_TABLE)


def _get_submissions_table():
    """Return the DynamoDB Timesheet_Submissions table resource."""
    return dynamodb.Table(SUBMISSIONS_TABLE)


def _get_projects_table():
    """Return the DynamoDB Projects table resource."""
    return dynamodb.Table(PROJECTS_TABLE)


def _now_iso():
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _get_submission(submission_id):
    """Fetch a submission by ID.

    Args:
        submission_id: The submission's unique identifier.

    Returns:
        The submission item dict.

    Raises:
        ValueError: If the submission is not found.
    """
    table = _get_submissions_table()
    item = table.get_item(Key={"submissionId": submission_id}).get("Item")
    if not item:
        raise ValueError(f"Submission '{submission_id}' not found")
    return item


def _validate_submission_editable(submission):
    """Validate that the submission status allows edits and is not archived.

    Validates: Requirements 6.5, 13.3 — entries only editable when Draft or
    Rejected, and never when archived.

    Args:
        submission: The submission item dict.

    Raises:
        ValueError: If the submission is archived or status does not allow edits.
    """
    # Reject edits on archived submissions
    if submission.get("archived") is True:
        raise ValueError(
            "Cannot modify entries for an archived submission. "
            "Archived submissions are read-only"
        )

    status = submission.get("status", "")
    if status not in EDITABLE_STATUSES:
        raise ValueError(
            f"Cannot modify entries for submission with status '{status}'. "
            f"Entries can only be modified when status is {sorted(EDITABLE_STATUSES)}"
        )


def _validate_project_approved(project_code):
    """Validate that the projectCode references an Approved project.

    Queries the projectCode-index GSI on the Projects table.

    Validates: Requirements 6.2, 15.4

    Args:
        project_code: The project charge code to validate.

    Raises:
        ValueError: If no project with the given code exists or it is not Approved.
    """
    table = _get_projects_table()
    response = table.query(
        IndexName="projectCode-index",
        KeyConditionExpression=Key("projectCode").eq(project_code),
    )
    items = response.get("Items", [])
    if not items:
        raise ValueError(
            f"Project with code '{project_code}' not found"
        )

    project = items[0]
    if project.get("approval_status") != "Approved":
        raise ValueError(
            f"Project '{project_code}' does not have approval_status of "
            f"'Approved'. Current status: '{project.get('approval_status')}'"
        )


def _validate_max_entries(submission_id, exclude_entry_id=None):
    """Validate that the submission does not exceed the max entry count.

    Queries the submissionId-index GSI on the Entries table.

    Validates: Requirements 6.7

    Args:
        submission_id: The submission to check.
        exclude_entry_id: Optional entryId to exclude from count (for updates).

    Raises:
        ValueError: If adding another entry would exceed the limit.
    """
    table = _get_entries_table()
    response = table.query(
        IndexName="submissionId-index",
        KeyConditionExpression=Key("submissionId").eq(submission_id),
        Select="COUNT",
    )
    count = response.get("Count", 0)

    # Handle pagination for count
    while "LastEvaluatedKey" in response:
        response = table.query(
            IndexName="submissionId-index",
            KeyConditionExpression=Key("submissionId").eq(submission_id),
            Select="COUNT",
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        count += response.get("Count", 0)

    # For updates, the entry already exists so we don't need to add 1
    effective_count = count if exclude_entry_id else count
    if not exclude_entry_id and effective_count >= MAX_ENTRIES_PER_SUBMISSION:
        raise ValueError(
            f"Cannot add entry: submission already has {count} entries. "
            f"Maximum allowed is {MAX_ENTRIES_PER_SUBMISSION}"
        )


def _validate_daily_hours(value, field_name):
    """Validate a single daily hours value.

    Validates: Requirements 15.1 — non-negative float, max 2 decimal places.

    Args:
        value: The hours value to validate (from input).
        field_name: The day field name (for error messages).

    Returns:
        A Decimal representation of the validated value.

    Raises:
        ValueError: If the value is negative or has more than 2 decimal places.
    """
    try:
        dec_value = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(
            f"Invalid value for '{field_name}': '{value}'. "
            f"Must be a valid number"
        )

    if dec_value < 0:
        raise ValueError(
            f"Invalid value for '{field_name}': {dec_value}. "
            f"Daily hours must be non-negative"
        )

    # Check max 2 decimal places: quantize to 2 places and compare
    two_places = Decimal("0.01")
    if dec_value != dec_value.quantize(two_places):
        raise ValueError(
            f"Invalid value for '{field_name}': {dec_value}. "
            f"Daily hours must have a maximum of 2 decimal places"
        )

    return dec_value


def _parse_and_validate_daily_hours(input_data):
    """Parse and validate all 7 daily hour values from input.

    Validates: Requirements 15.1, 15.5

    Args:
        input_data: The input dict containing day field values.

    Returns:
        A dict mapping day field names to validated Decimal values,
        plus a 'totalHours' key with the computed row total.

    Raises:
        ValueError: If any daily value fails validation.
    """
    hours = {}
    total = Decimal("0")

    for day in DAY_FIELDS:
        value = input_data.get(day, 0)
        validated = _validate_daily_hours(value, day)
        hours[day] = validated
        total += validated

    hours["totalHours"] = total
    return hours


def _get_existing_entries(submission_id):
    """Fetch all existing entries for a submission.

    Args:
        submission_id: The submission ID to query.

    Returns:
        A list of entry item dicts.
    """
    table = _get_entries_table()
    response = table.query(
        IndexName="submissionId-index",
        KeyConditionExpression=Key("submissionId").eq(submission_id),
    )
    items = response.get("Items", [])

    while "LastEvaluatedKey" in response:
        response = table.query(
            IndexName="submissionId-index",
            KeyConditionExpression=Key("submissionId").eq(submission_id),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))

    return items


def _validate_daily_totals(existing_entries, new_hours, exclude_entry_id=None):
    """Validate that total daily hours across all entries do not exceed 24.0.

    Validates: Requirements 15.2

    Args:
        existing_entries: List of existing entry items for the submission.
        new_hours: Dict of day field -> Decimal values for the new/updated entry.
        exclude_entry_id: Optional entryId to exclude from totals (for updates).

    Raises:
        ValueError: If any day's total would exceed 24.0 hours.
    """
    for day in DAY_FIELDS:
        day_total = new_hours.get(day, Decimal("0"))

        for entry in existing_entries:
            if exclude_entry_id and entry.get("entryId") == exclude_entry_id:
                continue
            entry_value = entry.get(day, Decimal("0"))
            if not isinstance(entry_value, Decimal):
                entry_value = Decimal(str(entry_value))
            day_total += entry_value

        if day_total > MAX_DAILY_HOURS:
            raise ValueError(
                f"Total hours for {day} across all entries would be "
                f"{day_total}, which exceeds the maximum of {MAX_DAILY_HOURS}"
            )


def add_timesheet_entry(event):
    """Add a new timesheet entry to a submission.

    Validates:
    - Submission exists and status is Draft or Rejected (Req 6.5)
    - projectCode references an Approved project (Req 6.2, 15.4)
    - Max 27 entries per submission (Req 6.7)
    - Daily hours are non-negative with max 2 decimal places (Req 15.1)
    - Total daily hours across all entries <= 24.0 (Req 15.2)
    - Computes and stores row total (Req 6.8, 15.5)

    Validates: Requirements 6.2, 6.3, 6.5, 6.7, 6.8, 15.1, 15.2, 15.3, 15.4, 15.5
    """
    get_caller_identity(event)
    args = event["arguments"]
    submission_id = args["submissionId"]
    input_data = args["input"]

    # Validate submission exists and is editable
    submission = _get_submission(submission_id)
    _validate_submission_editable(submission)

    # Validate projectCode references an Approved project
    project_code = input_data.get("projectCode", "")
    if not project_code or not project_code.strip():
        raise ValueError("projectCode is required")
    _validate_project_approved(project_code)

    # Validate max entries per submission
    _validate_max_entries(submission_id)

    # Parse and validate daily hours, compute row total
    hours = _parse_and_validate_daily_hours(input_data)

    # Validate total daily hours across all entries
    existing_entries = _get_existing_entries(submission_id)
    _validate_daily_totals(existing_entries, hours)

    now = _now_iso()
    entry_id = str(uuid.uuid4())

    item = {
        "entryId": entry_id,
        "submissionId": submission_id,
        "projectCode": project_code,
        "saturday": hours["saturday"],
        "sunday": hours["sunday"],
        "monday": hours["monday"],
        "tuesday": hours["tuesday"],
        "wednesday": hours["wednesday"],
        "thursday": hours["thursday"],
        "friday": hours["friday"],
        "totalHours": hours["totalHours"],
        "createdAt": now,
        "updatedAt": now,
    }

    entries_table = _get_entries_table()
    entries_table.put_item(Item=item)

    return item


def update_timesheet_entry(event):
    """Update an existing timesheet entry.

    Same validations as add_timesheet_entry, plus validates the entry exists.

    Validates: Requirements 6.2, 6.3, 6.5, 6.8, 15.1, 15.2, 15.3, 15.4, 15.5
    """
    get_caller_identity(event)
    args = event["arguments"]
    entry_id = args["entryId"]
    input_data = args["input"]

    # Fetch existing entry
    entries_table = _get_entries_table()
    existing_entry = entries_table.get_item(Key={"entryId": entry_id}).get("Item")
    if not existing_entry:
        raise ValueError(f"Entry '{entry_id}' not found")

    submission_id = existing_entry["submissionId"]

    # Validate submission exists and is editable
    submission = _get_submission(submission_id)
    _validate_submission_editable(submission)

    # Validate projectCode if provided, otherwise keep existing
    project_code = input_data.get("projectCode", existing_entry["projectCode"])
    if not project_code or not project_code.strip():
        raise ValueError("projectCode is required")
    _validate_project_approved(project_code)

    # Parse and validate daily hours, compute row total
    hours = _parse_and_validate_daily_hours(input_data)

    # Validate total daily hours across all entries (excluding this entry)
    existing_entries = _get_existing_entries(submission_id)
    _validate_daily_totals(existing_entries, hours, exclude_entry_id=entry_id)

    now = _now_iso()

    result = entries_table.update_item(
        Key={"entryId": entry_id},
        UpdateExpression=(
            "SET projectCode = :projectCode, "
            "saturday = :saturday, sunday = :sunday, "
            "monday = :monday, tuesday = :tuesday, "
            "wednesday = :wednesday, thursday = :thursday, "
            "friday = :friday, totalHours = :totalHours, "
            "updatedAt = :updatedAt"
        ),
        ExpressionAttributeValues={
            ":projectCode": project_code,
            ":saturday": hours["saturday"],
            ":sunday": hours["sunday"],
            ":monday": hours["monday"],
            ":tuesday": hours["tuesday"],
            ":wednesday": hours["wednesday"],
            ":thursday": hours["thursday"],
            ":friday": hours["friday"],
            ":totalHours": hours["totalHours"],
            ":updatedAt": now,
        },
        ReturnValues="ALL_NEW",
    )

    return result["Attributes"]


def remove_timesheet_entry(event):
    """Remove a timesheet entry from a submission.

    Validates that the submission status allows edits before deleting.

    Validates: Requirements 6.5
    """
    get_caller_identity(event)
    args = event["arguments"]
    entry_id = args["entryId"]

    # Fetch existing entry
    entries_table = _get_entries_table()
    existing_entry = entries_table.get_item(Key={"entryId": entry_id}).get("Item")
    if not existing_entry:
        raise ValueError(f"Entry '{entry_id}' not found")

    submission_id = existing_entry["submissionId"]

    # Validate submission exists and is editable
    submission = _get_submission(submission_id)
    _validate_submission_editable(submission)

    # Delete the entry
    entries_table.delete_item(Key={"entryId": entry_id})

    return True
