"""GetTimesheetSubmission Lambda resolver for AppSync.

Environment variables:
    SUBMISSIONS_TABLE: DynamoDB Timesheet_Submissions table name
    ENTRIES_TABLE: DynamoDB Timesheet_Entries table name
"""

import os

import boto3
from boto3.dynamodb.conditions import Key

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.auth import ForbiddenError, get_caller_identity

SUBMISSIONS_TABLE = os.environ.get("SUBMISSIONS_TABLE", "")
ENTRIES_TABLE = os.environ.get("ENTRIES_TABLE", "")
dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    try:
        return get_timesheet_submission(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def get_timesheet_submission(event):
    """Get a submission with its entries. Validates: Requirements 6.10, 6.11"""
    caller = get_caller_identity(event)
    submission_id = event["arguments"]["submissionId"]
    table = dynamodb.Table(SUBMISSIONS_TABLE)

    existing = table.get_item(Key={"submissionId": submission_id}).get("Item")
    if not existing:
        raise ValueError(f"Submission '{submission_id}' not found")

    if (
        existing["employeeId"] != caller["userId"]
        and caller["userType"] not in ("admin", "superadmin")
    ):
        raise ForbiddenError("You can only view your own timesheet submissions")

    entries_table = dynamodb.Table(ENTRIES_TABLE)
    entries_response = entries_table.query(
        IndexName="submissionId-index",
        KeyConditionExpression=Key("submissionId").eq(submission_id),
    )
    entries = entries_response.get("Items", [])

    while "LastEvaluatedKey" in entries_response:
        entries_response = entries_table.query(
            IndexName="submissionId-index",
            KeyConditionExpression=Key("submissionId").eq(submission_id),
            ExclusiveStartKey=entries_response["LastEvaluatedKey"],
        )
        entries.extend(entries_response.get("Items", []))

    existing["entries"] = entries
    return existing
