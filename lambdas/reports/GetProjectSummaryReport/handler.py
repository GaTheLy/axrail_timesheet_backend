"""GetProjectSummaryReport Lambda resolver for AppSync.

Returns a pre-signed S3 URL for the most recent Project Summary report.

Environment variables:
    SUBMISSIONS_TABLE, ENTRIES_TABLE, USERS_TABLE, PROJECTS_TABLE,
    EMPLOYEE_PERFORMANCE_TABLE, PERIODS_TABLE, REPORT_BUCKET
"""

import os
from datetime import datetime, timedelta, timezone

import boto3

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.auth import ForbiddenError, require_role

REPORT_BUCKET = os.environ.get("REPORT_BUCKET", "")
PRESIGNED_URL_EXPIRY = 3600
RESOLVER_ROLES = ["Project_Manager", "Tech_Lead"]

s3_client = boto3.client("s3")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from handler import _generate_project_summary, _find_latest_report


def handler(event, context):
    try:
        return get_project_summary_report(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def get_project_summary_report(event):
    """Return a pre-signed URL for Project Summary. Validates: Requirements 10.7"""
    require_role(event, RESOLVER_ROLES)
    args = event["arguments"]
    period_id = args["periodId"]

    prefix = f"reports/project-summary/{period_id}/"
    s3_key = _find_latest_report(prefix)

    if not s3_key:
        s3_key = _generate_project_summary(period_id)
        if not s3_key:
            raise ValueError(f"No Project Summary data available for period '{period_id}'")

    url = s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": REPORT_BUCKET, "Key": s3_key},
        ExpiresIn=PRESIGNED_URL_EXPIRY,
    )
    expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=PRESIGNED_URL_EXPIRY)
    ).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return {"url": url, "expiresAt": expires_at}
