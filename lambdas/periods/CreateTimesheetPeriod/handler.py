"""CreateTimesheetPeriod Lambda resolver for AppSync.

Environment variables:
    PERIODS_TABLE: DynamoDB Timesheet_Periods table name
"""

import os
import uuid
from datetime import datetime, timezone

import boto3

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.auth import ForbiddenError, require_user_type
from shared_utils import validate_period_dates, check_no_overlapping_periods

PERIODS_TABLE = os.environ.get("PERIODS_TABLE", "")
dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    try:
        return create_timesheet_period(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def create_timesheet_period(event):
    """Create a new timesheet period. Validates: Requirements 5.1-5.5"""
    caller = require_user_type(event, ["superadmin"])
    args = event["arguments"]["input"]

    start_date = args["startDate"]
    end_date = args["endDate"]
    submission_deadline = args["submissionDeadline"]
    period_string = args["periodString"]
    biweekly_period_id = args.get("biweeklyPeriodId", "")

    validate_period_dates(start_date, end_date, submission_deadline)
    table = dynamodb.Table(PERIODS_TABLE)
    check_no_overlapping_periods(table, start_date, end_date)

    now = datetime.now(timezone.utc).isoformat()
    period_id = str(uuid.uuid4())

    item = {
        "periodId": period_id,
        "startDate": start_date,
        "endDate": end_date,
        "submissionDeadline": submission_deadline,
        "periodString": period_string,
        "biweeklyPeriodId": biweekly_period_id,
        "isLocked": False,
        "createdAt": now,
        "createdBy": caller["userId"],
    }
    table.put_item(Item=item)
    return item
