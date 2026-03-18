"""RefreshDatabase Lambda resolver for AppSync.

Environment variables:
    MAIN_DATABASE_TABLE: DynamoDB Main_Database table name
    REPORT_BUCKET: S3 bucket for reading CSV files
"""

import logging
import os

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.auth import ForbiddenError, require_user_type
from shared_utils import (
    get_table, now_iso, read_csv_from_s3, validate_csv_row,
    batch_write_items, delete_all_records, REPORT_BUCKET,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    try:
        return refresh_database(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def refresh_database(event):
    """Replace all records with imported CSV data. Validates: Requirements 14.5"""
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

    delete_all_records(table)

    if valid_items:
        batch_write_items(table, valid_items)

    logger.info(
        "Database refresh by %s at %s: imported=%d, rejected=%d, s3=%s/%s",
        caller["userId"], now, len(valid_items), len(rejected_rows), bucket, key,
    )

    return {
        "importedCount": len(valid_items),
        "rejectedCount": len(rejected_rows),
        "rejectedRows": rejected_rows,
        "refreshedAt": now,
        "refreshedBy": caller["userId"],
    }
