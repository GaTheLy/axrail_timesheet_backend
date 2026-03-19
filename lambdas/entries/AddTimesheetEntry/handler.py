"""AddTimesheetEntry Lambda resolver for AppSync.

Environment variables:
    ENTRIES_TABLE: DynamoDB Timesheet_Entries table name
    SUBMISSIONS_TABLE: DynamoDB Timesheet_Submissions table name
    PROJECTS_TABLE: DynamoDB Projects table name
"""

import os
import uuid
from datetime import datetime, timezone

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.auth import ForbiddenError, get_caller_identity
from shared_utils import (
    get_entries_table, get_submission, validate_submission_editable,
    validate_project_approved, validate_max_entries,
    parse_and_validate_daily_hours, get_existing_entries, validate_daily_totals,
    validate_weekly_total,
)


def handler(event, context):
    try:
        return add_timesheet_entry(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def add_timesheet_entry(event):
    """Add a new timesheet entry. Validates: Requirements 6.2-6.8, 15.1-15.5"""
    get_caller_identity(event)
    args = event["arguments"]
    submission_id = args["submissionId"]
    input_data = args["input"]

    submission = get_submission(submission_id)
    validate_submission_editable(submission)

    project_code = input_data.get("projectCode", "")
    if not project_code or not project_code.strip():
        raise ValueError("projectCode is required")
    validate_project_approved(project_code)
    validate_max_entries(submission_id)

    hours = parse_and_validate_daily_hours(input_data)
    existing_entries = get_existing_entries(submission_id)
    validate_daily_totals(existing_entries, hours)
    validate_weekly_total(existing_entries, hours)

    now = datetime.now(timezone.utc).isoformat()
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

    entries_table = get_entries_table()
    entries_table.put_item(Item=item)
    return item
