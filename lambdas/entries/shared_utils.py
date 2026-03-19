"""Shared utilities for entry handlers."""

import os
from decimal import Decimal, InvalidOperation

import boto3
from boto3.dynamodb.conditions import Key

ENTRIES_TABLE = os.environ.get("ENTRIES_TABLE", "")
SUBMISSIONS_TABLE = os.environ.get("SUBMISSIONS_TABLE", "")
PROJECTS_TABLE = os.environ.get("PROJECTS_TABLE", "")

DAY_FIELDS = ("saturday", "sunday", "monday", "tuesday", "wednesday", "thursday", "friday")
MAX_ENTRIES_PER_SUBMISSION = 27
MAX_DAILY_HOURS = Decimal("8.0")
MAX_WEEKLY_HOURS = Decimal("40.0")
EDITABLE_STATUSES = {"Draft"}

dynamodb = boto3.resource("dynamodb")


def get_entries_table():
    return dynamodb.Table(ENTRIES_TABLE)


def get_submissions_table():
    return dynamodb.Table(SUBMISSIONS_TABLE)


def get_projects_table():
    return dynamodb.Table(PROJECTS_TABLE)


def get_submission(submission_id):
    table = get_submissions_table()
    item = table.get_item(Key={"submissionId": submission_id}).get("Item")
    if not item:
        raise ValueError(f"Submission '{submission_id}' not found")
    return item


def validate_submission_editable(submission):
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


def validate_project_approved(project_code):
    table = get_projects_table()
    response = table.query(
        IndexName="projectCode-index",
        KeyConditionExpression=Key("projectCode").eq(project_code),
    )
    items = response.get("Items", [])
    if not items:
        raise ValueError(f"Project with code '{project_code}' not found")
    project = items[0]
    if project.get("approval_status") != "Approved":
        raise ValueError(
            f"Project '{project_code}' does not have approval_status of "
            f"'Approved'. Current status: '{project.get('approval_status')}'"
        )


def validate_max_entries(submission_id, exclude_entry_id=None):
    table = get_entries_table()
    response = table.query(
        IndexName="submissionId-index",
        KeyConditionExpression=Key("submissionId").eq(submission_id),
        Select="COUNT",
    )
    count = response.get("Count", 0)
    while "LastEvaluatedKey" in response:
        response = table.query(
            IndexName="submissionId-index",
            KeyConditionExpression=Key("submissionId").eq(submission_id),
            Select="COUNT",
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        count += response.get("Count", 0)
    if not exclude_entry_id and count >= MAX_ENTRIES_PER_SUBMISSION:
        raise ValueError(
            f"Cannot add entry: submission already has {count} entries. "
            f"Maximum allowed is {MAX_ENTRIES_PER_SUBMISSION}"
        )


def validate_daily_hours(value, field_name):
    try:
        dec_value = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"Invalid value for '{field_name}': '{value}'. Must be a valid number")
    if dec_value < 0:
        raise ValueError(f"Invalid value for '{field_name}': {dec_value}. Daily hours must be non-negative")
    two_places = Decimal("0.01")
    if dec_value != dec_value.quantize(two_places):
        raise ValueError(f"Invalid value for '{field_name}': {dec_value}. Daily hours must have a maximum of 2 decimal places")
    return dec_value


def parse_and_validate_daily_hours(input_data):
    hours = {}
    total = Decimal("0")
    for day in DAY_FIELDS:
        value = input_data.get(day, 0)
        validated = validate_daily_hours(value, day)
        hours[day] = validated
        total += validated
    hours["totalHours"] = total
    return hours


def get_existing_entries(submission_id):
    table = get_entries_table()
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


def validate_daily_totals(existing_entries, new_hours, exclude_entry_id=None):
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


def validate_weekly_total(existing_entries, new_hours, exclude_entry_id=None):
    total = Decimal("0")
    for day in DAY_FIELDS:
        total += new_hours.get(day, Decimal("0"))
    for entry in existing_entries:
        if exclude_entry_id and entry.get("entryId") == exclude_entry_id:
            continue
        entry_total = entry.get("totalHours", Decimal("0"))
        if not isinstance(entry_total, Decimal):
            entry_total = Decimal(str(entry_total))
        total += entry_total
    if total > MAX_WEEKLY_HOURS:
        raise ValueError(
            f"Total weekly hours across all entries would be {total}, "
            f"which exceeds the maximum of {MAX_WEEKLY_HOURS}"
        )
