"""Main Database Management Lambda resolver for AppSync.

Handles listing, updating, bulk CSV import, and database refresh operations
for the Main_Database table. Superadmin-only for mutations.

Environment variables:
    MAIN_DATABASE_TABLE: DynamoDB Main_Database table name
    REPORT_BUCKET: S3 bucket for reading CSV files
"""

import csv
import io
import logging
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import boto3

# Add parent directory to path for shared imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.auth import ForbiddenError, get_caller_identity, require_user_type

MAIN_DATABASE_TABLE = os.environ.get("MAIN_DATABASE_TABLE", "")
REPORT_BUCKET = os.environ.get("REPORT_BUCKET", "")

dynamodb = boto3.resource("dynamodb")
s3_client = boto3.client("s3")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

REQUIRED_CSV_COLUMNS = {"type", "value", "project_name", "budget_effort", "project_status"}


def handler(event, context):
    """AppSync Lambda resolver entry point.

    Routes to the appropriate operation based on event['info']['fieldName'].
    """
    field = event["info"]["fieldName"]
    resolvers = {
        "listMainDatabase": list_main_database,
        "updateMainDatabaseRecord": update_main_database_record,
        "bulkImportCSV": bulk_import_csv,
        "refreshDatabase": refresh_database,
    }

    resolver = resolvers.get(field)
    if not resolver:
        raise ValueError(f"Unknown field: {field}")

    try:
        return resolver(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def _get_table():
    """Return the DynamoDB Main_Database table resource."""
    return dynamodb.Table(MAIN_DATABASE_TABLE)


def _now_iso():
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _validate_budget_effort(value):
    """Validate that budget_effort is a positive number.

    Args:
        value: The budget_effort value to validate.

    Returns:
        Decimal representation for DynamoDB storage.

    Raises:
        ValueError: If the value is not a positive number.
    """
    try:
        effort = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"Invalid budget_effort: '{value}'. Must be a positive number")

    if effort <= 0:
        raise ValueError(f"Invalid budget_effort: '{value}'. Must be a positive number")

    return effort


def _read_csv_from_s3(bucket, key):
    """Read and parse a CSV file from S3.

    Args:
        bucket: S3 bucket name.
        key: S3 object key.

    Returns:
        A list of dicts, one per CSV row.

    Raises:
        ValueError: If the CSV cannot be read or is missing required columns.
    """
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


def _validate_csv_row(row, row_number):
    """Validate a single CSV row against the expected schema.

    Args:
        row: Dict representing one CSV row.
        row_number: 1-based row number for error reporting.

    Returns:
        Tuple of (mapped_item, errors) where mapped_item is the DynamoDB item
        dict if valid, or None if invalid. errors is a list of error strings.
    """
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
            budget_effort = _validate_budget_effort(budget_effort_raw)
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
        "createdAt": _now_iso(),
    }, []


def _batch_write_items(table, items):
    """Write items to DynamoDB in batches of 25.

    Args:
        table: DynamoDB Table resource.
        items: List of item dicts to write.
    """
    with table.batch_writer() as batch:
        for item in items:
            batch.put_item(Item=item)


def _delete_all_records(table):
    """Delete all records from the table via scan + batch delete.

    Args:
        table: DynamoDB Table resource.
    """
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


def list_main_database(event):
    """List all records in the Main_Database table.

    Any authenticated user with Project_Manager or Superadmin role can access.

    Validates: Requirements 14.1
    """
    caller = get_caller_identity(event)
    allowed = caller["userType"] == "superadmin" or caller["role"] == "Project_Manager"
    if not allowed:
        raise ForbiddenError(
            "Only Superadmin or Project_Manager can access the main database"
        )

    table = _get_table()
    items = []
    scan_kwargs = {}
    while True:
        response = table.scan(**scan_kwargs)
        items.extend(response.get("Items", []))
        if "LastEvaluatedKey" not in response:
            break
        scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

    return items


def update_main_database_record(event):
    """Update a record in the Main_Database table.

    Superadmin only. Persists changes with updatedBy/updatedAt.

    Validates: Requirements 14.2
    """
    caller = require_user_type(event, ["superadmin"])
    record_id = event["arguments"]["id"]
    args = event["arguments"]["input"]

    table = _get_table()

    existing = table.get_item(Key={"recordId": record_id}).get("Item")
    if not existing:
        raise ValueError(f"Record '{record_id}' not found")

    now = _now_iso()

    update_parts = ["#updatedAt = :updatedAt", "#updatedBy = :updatedBy"]
    expr_names = {"#updatedAt": "updatedAt", "#updatedBy": "updatedBy"}
    expr_values = {":updatedAt": now, ":updatedBy": caller["userId"]}

    allowed_fields = {
        "type": "type",
        "chargeCode": "chargeCode",
        "projectName": "projectName",
        "budgetEffort": "budgetEffort",
        "projectStatus": "projectStatus",
    }

    for field, attr in allowed_fields.items():
        if field in args:
            value = args[field]
            if field == "budgetEffort":
                value = _validate_budget_effort(value)
            placeholder = f":{attr}"
            name_placeholder = f"#{attr}"
            expr_values[placeholder] = value
            expr_names[name_placeholder] = attr
            update_parts.append(f"{name_placeholder} = {placeholder}")

    update_expr = "SET " + ", ".join(update_parts)

    result = table.update_item(
        Key={"recordId": record_id},
        UpdateExpression=update_expr,
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
        ReturnValues="ALL_NEW",
    )

    return result["Attributes"]


def bulk_import_csv(event):
    """Bulk import records from a CSV file in S3.

    Superadmin only. Validates each row against the expected schema.
    Rejects invalid rows with row number and error detail.
    Persists valid rows.

    Validates: Requirements 14.3, 14.4
    """
    caller = require_user_type(event, ["superadmin"])
    file_input = event["arguments"]["file"]
    bucket = file_input.get("bucket", REPORT_BUCKET)
    key = file_input["key"]

    rows = _read_csv_from_s3(bucket, key)

    table = _get_table()
    now = _now_iso()
    valid_items = []
    rejected_rows = []

    for idx, row in enumerate(rows, start=1):
        item, errors = _validate_csv_row(row, idx)
        if errors:
            rejected_rows.append({
                "row": idx,
                "errors": errors,
            })
        else:
            item["updatedAt"] = now
            item["updatedBy"] = caller["userId"]
            valid_items.append(item)

    if valid_items:
        _batch_write_items(table, valid_items)

    return {
        "importedCount": len(valid_items),
        "rejectedCount": len(rejected_rows),
        "rejectedRows": rejected_rows,
    }


def refresh_database(event):
    """Replace all existing records with imported CSV data.

    Superadmin only. Deletes all existing records, then imports from CSV.
    Logs the operation.

    Validates: Requirements 14.5
    """
    caller = require_user_type(event, ["superadmin"])
    file_input = event["arguments"]["file"]
    bucket = file_input.get("bucket", REPORT_BUCKET)
    key = file_input["key"]

    rows = _read_csv_from_s3(bucket, key)

    table = _get_table()
    now = _now_iso()
    valid_items = []
    rejected_rows = []

    for idx, row in enumerate(rows, start=1):
        item, errors = _validate_csv_row(row, idx)
        if errors:
            rejected_rows.append({"row": idx, "errors": errors})
        else:
            item["updatedAt"] = now
            item["updatedBy"] = caller["userId"]
            valid_items.append(item)

    # Delete all existing records before importing
    _delete_all_records(table)

    if valid_items:
        _batch_write_items(table, valid_items)

    logger.info(
        "Database refresh by %s at %s: imported=%d, rejected=%d, s3=%s/%s",
        caller["userId"],
        now,
        len(valid_items),
        len(rejected_rows),
        bucket,
        key,
    )

    return {
        "importedCount": len(valid_items),
        "rejectedCount": len(rejected_rows),
        "rejectedRows": rejected_rows,
        "refreshedAt": now,
        "refreshedBy": caller["userId"],
    }
