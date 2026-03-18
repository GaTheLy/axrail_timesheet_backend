"""GetTCSummaryReport Lambda resolver for AppSync.

Returns a pre-signed S3 URL for the most recent TC Summary report.

Environment variables:
    SUBMISSIONS_TABLE, ENTRIES_TABLE, USERS_TABLE, PROJECTS_TABLE,
    EMPLOYEE_PERFORMANCE_TABLE, PERIODS_TABLE, REPORT_BUCKET
"""

import os

import boto3

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.auth import ForbiddenError, require_role

REPORT_BUCKET = os.environ.get("REPORT_BUCKET", "")
PRESIGNED_URL_EXPIRY = 3600
RESOLVER_ROLES = ["Project_Manager", "Tech_Lead"]

s3_client = boto3.client("s3")

# Import the report generation logic from the stream handler module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from handler import _generate_tc_summary, _find_latest_report


def handler(event, context):
    try:
        return get_tc_summary_report(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def get_tc_summary_report(event):
    """Return a pre-signed URL for TC Summary. Validates: Requirements 9.7"""
    require_role(event, RESOLVER_ROLES)
    args = event["arguments"]
    tech_lead_id = args["techLeadId"]
    period_id = args["periodId"]

    prefix = f"reports/tc-summary/{period_id}/"
    s3_key = _find_latest_report(prefix)

    if not s3_key:
        s3_key = _generate_tc_summary(tech_lead_id, period_id)
        if not s3_key:
            raise ValueError(
                f"No TC Summary data available for tech lead '{tech_lead_id}' "
                f"and period '{period_id}'"
            )

    url = s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": REPORT_BUCKET, "Key": s3_key},
        ExpiresIn=PRESIGNED_URL_EXPIRY,
    )
    return {"url": url}
