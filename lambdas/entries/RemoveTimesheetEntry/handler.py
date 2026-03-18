"""RemoveTimesheetEntry Lambda resolver for AppSync.

Environment variables:
    ENTRIES_TABLE: DynamoDB Timesheet_Entries table name
    SUBMISSIONS_TABLE: DynamoDB Timesheet_Submissions table name
"""

import os

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.auth import ForbiddenError, get_caller_identity
from shared_utils import get_entries_table, get_submission, validate_submission_editable


def handler(event, context):
    try:
        return remove_timesheet_entry(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def remove_timesheet_entry(event):
    """Remove a timesheet entry. Validates: Requirements 6.5"""
    get_caller_identity(event)
    args = event["arguments"]
    entry_id = args["entryId"]

    entries_table = get_entries_table()
    existing_entry = entries_table.get_item(Key={"entryId": entry_id}).get("Item")
    if not existing_entry:
        raise ValueError(f"Entry '{entry_id}' not found")

    submission_id = existing_entry["submissionId"]
    submission = get_submission(submission_id)
    validate_submission_editable(submission)

    entries_table.delete_item(Key={"entryId": entry_id})
    return True
