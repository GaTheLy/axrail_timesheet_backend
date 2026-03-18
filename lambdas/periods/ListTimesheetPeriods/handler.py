"""ListTimesheetPeriods Lambda resolver for AppSync.

Environment variables:
    PERIODS_TABLE: DynamoDB Timesheet_Periods table name
"""

import os

import boto3

PERIODS_TABLE = os.environ.get("PERIODS_TABLE", "")
dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    return list_timesheet_periods(event)


def list_timesheet_periods(event):
    """List timesheet periods with optional filtering. Validates: Requirements 5.1"""
    table = dynamodb.Table(PERIODS_TABLE)
    args = event.get("arguments") or {}
    filter_input = args.get("filter") or {}

    if not filter_input:
        response = table.scan()
        items = response.get("Items", [])
        while "LastEvaluatedKey" in response:
            response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
            items.extend(response.get("Items", []))
        return items

    filter_parts = []
    expr_names = {}
    expr_values = {}

    if "isLocked" in filter_input:
        expr_names["#isLocked"] = "isLocked"
        expr_values[":isLocked"] = filter_input["isLocked"]
        filter_parts.append("#isLocked = :isLocked")

    if "biweeklyPeriodId" in filter_input:
        expr_names["#biweeklyPeriodId"] = "biweeklyPeriodId"
        expr_values[":biweeklyPeriodId"] = filter_input["biweeklyPeriodId"]
        filter_parts.append("#biweeklyPeriodId = :biweeklyPeriodId")

    scan_kwargs = {}
    if filter_parts:
        scan_kwargs["FilterExpression"] = " AND ".join(filter_parts)
        scan_kwargs["ExpressionAttributeNames"] = expr_names
        scan_kwargs["ExpressionAttributeValues"] = expr_values

    response = table.scan(**scan_kwargs)
    items = response.get("Items", [])
    while "LastEvaluatedKey" in response:
        scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
        response = table.scan(**scan_kwargs)
        items.extend(response.get("Items", []))

    return items
