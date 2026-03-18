"""Shared utilities for main_database handlers."""

import csv
import io
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import boto3

MAIN_DATABASE_TABLE = os.environ.get("MAIN_DATABASE_TABLE", "")
REPORT_BUCKET = os.environ.get("REPORT_BUCKET", "")

dynamodb = boto3.resource("dynamodb")
s3_client = boto3.client("s3")

REQUIRED_CSV_COLUMNS = {"type", "value", "project_name", "budget_effort", "project_status"}


def get_table():
    return dynamodb.Table(MAIN_DATABASE_TABLE)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def validate_budget_effort(value):
    try:
        effort = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"Invalid budget_effort: '{value}'. Must be a positive number")
    if effort <= 0:
        raise ValueError(f"Invalid budget_effort: '{value}'. Must be a positive number")
    return effort


def read_csv_from_s3(bucket, key):
    response = s3_client.get_object(Bucket=bucket, Key=key)
    body = response["Body"].read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(body))
    if reader.fieldnames is None:
        raise ValueError("CSV file is empty or has no header row")
    actual_columns = {col.strip() for col in reader.fieldnames}
    missing = REQUIRED_CSV_COLUMNS - actual_columns
    if missing:
        raise ValueError(f"CSV is missing required columns: {sorted(missing)}")
    return list(reader)


def validate_csv_row(row, row_number):
    errors = []
    record_type = (row.get("type") or "").strip()
    if not record_type:
        errors.append("'type' is required")
    charge_code = (row.get("value") or "").strip()
    if not charge_code:
        errors.append("'value' is required")
    project_name = (row.get("project_name") or "").strip()
    if not project_name:
        errors.append("'project_name' is required")
    project_status = (row.get("project_status") or "").strip()
    if not project_status:
        errors.append("'project_status' is required")
    budget_effort_raw = (row.get("budget_effort") or "").strip()
    budget_effort = None
    if not budget_effort_raw:
        errors.append("'budget_effort' is required")
    else:
        try:
            budget_effort = validate_budget_effort(budget_effort_raw)
        except ValueError:
            errors.append(f"'budget_effort' must be a positive number, got '{budget_effort_raw}'")
    if errors:
        return None, errors
    return {
        "recordId": str(uuid.uuid4()),
        "type": record_type,
        "chargeCode": charge_code,
        "projectName": project_name,
        "budgetEffort": budget_effort,
        "projectStatus": project_status,
        "createdAt": now_iso(),
    }, []


def batch_write_items(table, items):
    with table.batch_writer() as batch:
        for item in items:
            batch.put_item(Item=item)


def delete_all_records(table):
    scan_kwargs = {"ProjectionExpression": "recordId"}
    while True:
        response = table.scan(**scan_kwargs)
        items = response.get("Items", [])
        if not items:
            break
        with table.batch_writer() as batch:
            for item in items:
                batch.delete_item(Key={"recordId": item["recordId"]})
        if "LastEvaluatedKey" not in response:
            break
        scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
