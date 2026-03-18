"""BulkImportCSV Lambda resolver for AppSync.

Environment variables:
    MAIN_DATABASE_TABLE: DynamoDB Main_Database table name
    REPORT_BUCKET: S3 bucket for reading CSV files
"""

import os

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.auth import ForbiddenError, require_user_type
from shared_utils import (
    get_table, now_iso, read_csv_from_s3, validate_csv_row, batch_write_items,
    REPORT_BUCKET,
)


def handler(event, context):
    try:
        return bulk_import_csv(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def bulk_import_csv(event):
    """Bulk import records from CSV. Validates: Requirements 14.3, 14.4"""
    caller = require_user_type(event, ["superadmin"])
    file_input = event["arguments"]["file"]
    bucket = file_input.get("bucket", REPORT_BUCKET)
    key = file_input["key"]

    rows = read_csv_from_s3(bucket, key)
    table = get_table()
    now = now_iso()
    valid_items = []
    rejected_rows = []

    for idx, row in enumerate(rows, start=1):
        item, errors = validate_csv_row(row, idx)
        if errors:
            rejected_rows.append({"row": idx, "errors": errors})
        else:
            item["updatedAt"] = now
            item["updatedBy"] = caller["userId"]
            valid_items.append(item)

    if valid_items:
        batch_write_items(table, valid_items)

    return {
        "importedCount": len(valid_items),
        "rejectedCount": len(rejected_rows),
        "rejectedRows": rejected_rows,
    }
