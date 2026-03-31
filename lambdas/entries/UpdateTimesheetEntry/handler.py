"""UpdateTimesheetEntry Lambda resolver for AppSync.

Environment variables:
    ENTRIES_TABLE: DynamoDB Timesheet_Entries table name
    SUBMISSIONS_TABLE: DynamoDB Timesheet_Submissions table name
    PROJECTS_TABLE: DynamoDB Projects table name
"""

import os
from datetime import datetime, timezone

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.auth import ForbiddenError, get_caller_identity
from shared_utils import (
    get_entries_table, get_submission, validate_submission_editable,
    validate_project_approved, parse_and_validate_daily_hours,
    get_existing_entries, validate_daily_totals, validate_weekly_total,
    recalculate_submission_total_hours,
)


def handler(event, context):
    try:
        return update_timesheet_entry(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def update_timesheet_entry(event):
    """Update an existing timesheet entry. Validates: Requirements 6.2-6.8, 15.1-15.5"""
    get_caller_identity(event)
    args = event["arguments"]
    entry_id = args["entryId"]
    input_data = args["input"]

    entries_table = get_entries_table()
    existing_entry = entries_table.get_item(Key={"entryId": entry_id}).get("Item")
    if not existing_entry:
        raise ValueError(f"Entry '{entry_id}' not found")

    submission_id = existing_entry["submissionId"]
    submission = get_submission(submission_id)
    validate_submission_editable(submission)

    project_code = input_data.get("projectCode", existing_entry["projectCode"])
    if not project_code or not project_code.strip():
        raise ValueError("projectCode is required")
    validate_project_approved(project_code)

    description = input_data.get("description", existing_entry.get("description", ""))

    hours = parse_and_validate_daily_hours(input_data)
    existing_entries = get_existing_entries(submission_id)
    validate_daily_totals(existing_entries, hours, exclude_entry_id=entry_id)
    validate_weekly_total(existing_entries, hours, exclude_entry_id=entry_id)

    now = datetime.now(timezone.utc).isoformat()

    result = entries_table.update_item(
        Key={"entryId": entry_id},
        UpdateExpression=(
            "SET projectCode = :projectCode, "
            "description = :description, "
            "saturday = :saturday, sunday = :sunday, "
            "monday = :monday, tuesday = :tuesday, "
            "wednesday = :wednesday, thursday = :thursday, "
            "friday = :friday, totalHours = :totalHours, "
            "updatedAt = :updatedAt"
        ),
        ExpressionAttributeValues={
            ":projectCode": project_code,
            ":description": description,
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
    # Recalculate submission totalHours
    recalculate_submission_total_hours(submission_id)

    return result["Attributes"]
