"""GetCurrentPeriod Lambda resolver for AppSync.

Environment variables:
    PERIODS_TABLE: DynamoDB Timesheet_Periods table name
"""

import os
from datetime import date, datetime, timedelta, timezone

import boto3

PERIODS_TABLE = os.environ.get("PERIODS_TABLE", "")
dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    return get_current_period(event)


def get_current_period(event):
    """Return the period containing today's date. Validates: Requirements 5.1"""
    table = dynamodb.Table(PERIODS_TABLE)
    MYT = timezone(timedelta(hours=8))
    today = datetime.now(MYT).date()

    response = table.scan()
    items = response.get("Items", [])
    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response.get("Items", []))

    for item in items:
        start = date.fromisoformat(item["startDate"])
        end = date.fromisoformat(item["endDate"])
        if start <= today <= end:
            return item

    return None
