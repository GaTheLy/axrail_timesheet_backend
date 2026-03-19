"""Report Generator Lambda for TC Summary and Project Summary reports.

Handles BOTH DynamoDB Stream events AND AppSync resolver events:
- DynamoDB Stream: triggered when Timesheet_Submissions status changes to
  Submitted. Generates both TC Summary and Project Summary CSVs
  and stores them in S3.
- AppSync resolver: returns pre-signed S3 URLs for downloading reports.

Event routing:
- If 'Records' key exists -> DynamoDB Stream handler
- If 'info' key exists -> AppSync resolver

Environment variables:
    SUBMISSIONS_TABLE: DynamoDB Timesheet_Submissions table name
    ENTRIES_TABLE: DynamoDB Timesheet_Entries table name
    USERS_TABLE: DynamoDB Users table name
    PROJECTS_TABLE: DynamoDB Projects table name
    EMPLOYEE_PERFORMANCE_TABLE: DynamoDB Employee_Performance table name
    PERIODS_TABLE: DynamoDB Timesheet_Periods table name
    REPORT_BUCKET: S3 bucket name for report storage
"""

import csv
import io
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

import boto3
from boto3.dynamodb.conditions import Attr, Key

# Add parent directory to path for shared imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.auth import ForbiddenError, require_role

logger = logging.getLogger()
logger.setLevel(logging.INFO)

SUBMISSIONS_TABLE = os.environ.get("SUBMISSIONS_TABLE", "")
ENTRIES_TABLE = os.environ.get("ENTRIES_TABLE", "")
USERS_TABLE = os.environ.get("USERS_TABLE", "")
PROJECTS_TABLE = os.environ.get("PROJECTS_TABLE", "")
EMPLOYEE_PERFORMANCE_TABLE = os.environ.get("EMPLOYEE_PERFORMANCE_TABLE", "")
REPORT_BUCKET = os.environ.get("REPORT_BUCKET", "")

PRESIGNED_URL_EXPIRY = 3600  # 1 hour

dynamodb = boto3.resource("dynamodb")
s3_client = boto3.client("s3")


def handler(event, context):
    """Main entry point. Routes based on event structure.

    - DynamoDB Stream events contain a 'Records' key.
    - AppSync resolver events contain an 'info' key.
    """
    if "Records" in event:
        return _handle_stream_event(event)
    elif "info" in event:
        return _handle_appsync_event(event)
    else:
        raise ValueError("Unknown event type: expected DynamoDB Stream or AppSync event")


# ---------------------------------------------------------------------------
# Table accessors
# ---------------------------------------------------------------------------

def _get_submissions_table():
    return dynamodb.Table(SUBMISSIONS_TABLE)


def _get_entries_table():
    return dynamodb.Table(ENTRIES_TABLE)


def _get_users_table():
    return dynamodb.Table(USERS_TABLE)


def _get_projects_table():
    return dynamodb.Table(PROJECTS_TABLE)


def _get_performance_table():
    return dynamodb.Table(EMPLOYEE_PERFORMANCE_TABLE)


# ---------------------------------------------------------------------------
# DynamoDB Stream handling
# ---------------------------------------------------------------------------

def _handle_stream_event(event):
    """Process DynamoDB Stream records from Timesheet_Submissions table.

    For each record where status transitions to Submitted,
    generates both TC Summary and Project Summary reports.

    Validates: Requirements 9.1, 10.1
    """
    logger.info("Report generator invoked with %d stream record(s)",
                len(event.get("Records", [])))

    processed = 0
    for record in event["Records"]:
        if _should_process_stream_record(record):
            new_image = record["dynamodb"]["NewImage"]
            period_id = new_image.get("periodId", {}).get("S", "")
            employee_id = new_image.get("employeeId", {}).get("S", "")

            if not period_id:
                logger.warning("Stream record missing periodId, skipping")
                continue

            # Find the tech lead (supervisor) for this employee
            supervisor_id = _get_employee_supervisor_id(employee_id)

            # Generate TC Summary for the supervisor/period if supervisor exists
            if supervisor_id:
                _generate_tc_summary(supervisor_id, period_id)

            # Generate Project Summary for the period
            _generate_project_summary(period_id)

            processed += 1

    logger.info("Report generation complete. Processed %d record(s)", processed)
    return {"processedRecords": processed}


def _should_process_stream_record(record):
    """Determine if a DynamoDB Stream record should trigger report generation.

    Only processes INSERT or MODIFY events where the new status is
    Submitted, and the old status was different (to avoid
    duplicate processing).

    Args:
        record: A single DynamoDB Stream record.

    Returns:
        True if the record represents a transition to Submitted.
    """
    event_name = record.get("eventName")
    if event_name not in ("INSERT", "MODIFY"):
        return False

    new_image = record.get("dynamodb", {}).get("NewImage")
    if not new_image:
        return False

    new_status = new_image.get("status", {}).get("S", "")
    if new_status not in ("Submitted",):
        return False

    # For MODIFY events, skip if old status was already the same
    if event_name == "MODIFY":
        old_image = record.get("dynamodb", {}).get("OldImage", {})
        old_status = old_image.get("status", {}).get("S", "")
        if old_status == new_status:
            return False

    return True


def _get_employee_supervisor_id(employee_id):
    """Look up the supervisorId for an employee.

    Args:
        employee_id: The employee's userId.

    Returns:
        The supervisorId string, or None if not found.
    """
    if not employee_id:
        return None

    table = _get_users_table()
    response = table.get_item(Key={"userId": employee_id})
    item = response.get("Item")
    if not item:
        logger.warning("Employee %s not found in Users table", employee_id)
        return None

    return item.get("supervisorId")


# ---------------------------------------------------------------------------
# TC Summary Report generation
# ---------------------------------------------------------------------------

def _generate_tc_summary(tech_lead_id, period_id):
    """Generate TC Summary CSV for a Tech Lead and period, upload to S3.

    Columns: Name, Chargable Hours, Total Hours, Current Period Chargability,
             YTD Chargability

    Includes only employees with Submitted submissions for the period.

    Validates: Requirements 9.2, 9.3, 9.4, 9.5, 9.6
    """
    logger.info("Generating TC Summary for tech_lead=%s, period=%s",
                tech_lead_id, period_id)

    # Get employees under this tech lead
    employees = _get_supervised_employees(tech_lead_id)
    if not employees:
        logger.info("No employees found under tech lead %s", tech_lead_id)
        return None

    # Build employee lookup by userId
    employee_map = {emp["userId"]: emp for emp in employees}

    # Get Submitted submissions for this period
    submissions = _get_submissions_for_period(period_id, ["Submitted"])

    # Filter to only submissions from supervised employees
    supervised_ids = set(employee_map.keys())
    relevant_submissions = [
        sub for sub in submissions
        if sub.get("employeeId") in supervised_ids
    ]

    if not relevant_submissions:
        logger.info("No Submitted submissions for tech lead %s in period %s",
                     tech_lead_id, period_id)
        return None

    # Determine year for YTD lookup
    year = datetime.now(timezone.utc).year

    # Build CSV rows
    rows = []
    for submission in relevant_submissions:
        emp_id = submission["employeeId"]
        emp = employee_map.get(emp_id, {})
        name = emp.get("fullName", "Unknown")

        chargeable_hours = _to_decimal(submission.get("chargeableHours", 0))
        total_hours = _to_decimal(submission.get("totalHours", 0))

        # Current period chargeability
        current_chargeability = calculate_current_period_chargeability(
            chargeable_hours, total_hours
        )

        # YTD chargeability from Employee_Performance table
        ytd_chargeability = _get_ytd_chargeability(emp_id, year)

        rows.append({
            "Name": name,
            "Chargable Hours": str(chargeable_hours),
            "Total Hours": str(total_hours),
            "Current Period Chargability": str(current_chargeability),
            "YTD Chargability": str(ytd_chargeability),
        })

    # Write CSV and upload to S3
    csv_content = _build_csv(
        ["Name", "Chargable Hours", "Total Hours",
         "Current Period Chargability", "YTD Chargability"],
        rows,
    )

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    s3_key = f"reports/tc-summary/{period_id}/{timestamp}.csv"
    _upload_to_s3(s3_key, csv_content)

    logger.info("TC Summary uploaded to s3://%s/%s", REPORT_BUCKET, s3_key)
    return s3_key


# ---------------------------------------------------------------------------
# Project Summary Report generation
# ---------------------------------------------------------------------------

def _generate_project_summary(period_id):
    """Generate Project Summary CSV for a period, upload to S3.

    Columns: Project Charge Code, Project Name, Planned Hours, Charged Hours,
             Utilization, Current Biweekly Effort

    Includes ALL projects regardless of status.

    Validates: Requirements 10.2, 10.3, 10.4, 10.5, 10.6
    """
    logger.info("Generating Project Summary for period=%s", period_id)

    # Get all projects
    projects = _get_all_projects()
    if not projects:
        logger.info("No projects found")
        return None

    # Get all Submitted submissions for this period
    submissions = _get_submissions_for_period(period_id, ["Submitted"])
    submission_ids = [sub["submissionId"] for sub in submissions]

    # Get all entries for these submissions, grouped by projectCode
    project_hours = _aggregate_hours_by_project(submission_ids)

    # Get biweekly period info and compute biweekly effort
    biweekly_period_id = _get_biweekly_period_id(period_id)
    biweekly_hours = {}
    if biweekly_period_id:
        biweekly_hours = _get_biweekly_effort(biweekly_period_id)

    # Build CSV rows
    rows = []
    for project in projects:
        project_code = project.get("projectCode", "")
        project_name = project.get("projectName", "")
        planned_hours = _to_decimal(project.get("plannedHours", 0))
        charged_hours = _to_decimal(project_hours.get(project_code, 0))

        # Utilization = (charged hours / planned hours) * 100
        utilization = calculate_project_utilization(charged_hours, planned_hours)

        biweekly_effort = _to_decimal(biweekly_hours.get(project_code, 0))

        rows.append({
            "Project Charge Code": project_code,
            "Project Name": project_name,
            "Planned Hours": str(planned_hours),
            "Charged Hours": str(charged_hours),
            "Utilization": str(utilization),
            "Current Biweekly Effort": str(biweekly_effort),
        })

    # Write CSV and upload to S3
    csv_content = _build_csv(
        ["Project Charge Code", "Project Name", "Planned Hours",
         "Charged Hours", "Utilization", "Current Biweekly Effort"],
        rows,
    )

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    s3_key = f"reports/project-summary/{period_id}/{timestamp}.csv"
    _upload_to_s3(s3_key, csv_content)

    logger.info("Project Summary uploaded to s3://%s/%s", REPORT_BUCKET, s3_key)
    return s3_key


# ---------------------------------------------------------------------------
# AppSync resolver handling
# ---------------------------------------------------------------------------

RESOLVER_ROLES = ["Project_Manager", "Tech_Lead"]


def _handle_appsync_event(event):
    """Route AppSync resolver events to the appropriate handler.

    Validates: Requirements 9.7, 10.7
    """
    field = event["info"]["fieldName"]
    resolvers = {
        "getTCSummaryReport": get_tc_summary_report,
        "getProjectSummaryReport": get_project_summary_report,
    }

    resolver = resolvers.get(field)
    if not resolver:
        raise ValueError(f"Unknown field: {field}")

    try:
        return resolver(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def get_tc_summary_report(event):
    """Return a pre-signed S3 URL for the most recent TC Summary report.

    Args (from event['arguments']):
        techLeadId: The Tech Lead's userId.
        periodId: The timesheet period ID.

    Returns:
        dict with 'url' containing the pre-signed download URL.

    Validates: Requirements 9.7
    """
    require_role(event, RESOLVER_ROLES)
    args = event["arguments"]
    tech_lead_id = args["techLeadId"]
    period_id = args["periodId"]

    prefix = f"reports/tc-summary/{period_id}/"
    s3_key = _find_latest_report(prefix)

    if not s3_key:
        # Generate on demand if no report exists yet
        s3_key = _generate_tc_summary(tech_lead_id, period_id)
        if not s3_key:
            raise ValueError(
                f"No TC Summary data available for tech lead '{tech_lead_id}' "
                f"and period '{period_id}'"
            )

    url = _generate_presigned_url(s3_key)
    return {"url": url}


def get_project_summary_report(event):
    """Return a pre-signed S3 URL for the most recent Project Summary report.

    Args (from event['arguments']):
        periodId: The timesheet period ID.

    Returns:
        dict with 'url' containing the pre-signed download URL.

    Validates: Requirements 10.7
    """
    require_role(event, RESOLVER_ROLES)
    args = event["arguments"]
    period_id = args["periodId"]

    prefix = f"reports/project-summary/{period_id}/"
    s3_key = _find_latest_report(prefix)

    if not s3_key:
        # Generate on demand if no report exists yet
        s3_key = _generate_project_summary(period_id)
        if not s3_key:
            raise ValueError(
                f"No Project Summary data available for period '{period_id}'"
            )

    url = _generate_presigned_url(s3_key)
    return {"url": url}


# ---------------------------------------------------------------------------
# Data query helpers
# ---------------------------------------------------------------------------

def _get_supervised_employees(tech_lead_id):
    """Query employees under a Tech Lead using supervisorId-index GSI.

    Args:
        tech_lead_id: The Tech Lead's userId.

    Returns:
        List of employee items.
    """
    table = _get_users_table()
    response = table.query(
        IndexName="supervisorId-index",
        KeyConditionExpression=Key("supervisorId").eq(tech_lead_id),
    )
    items = response.get("Items", [])

    while "LastEvaluatedKey" in response:
        response = table.query(
            IndexName="supervisorId-index",
            KeyConditionExpression=Key("supervisorId").eq(tech_lead_id),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))

    return items


def _get_submissions_for_period(period_id, statuses):
    """Get submissions for a period filtered by status list.

    Uses the periodId-status-index GSI to query for each status.

    Args:
        period_id: The timesheet period ID.
        statuses: List of status strings (e.g. ["Submitted"]).

    Returns:
        List of submission items.
    """
    table = _get_submissions_table()
    all_items = []

    for status in statuses:
        response = table.query(
            IndexName="periodId-status-index",
            KeyConditionExpression=(
                Key("periodId").eq(period_id) & Key("status").eq(status)
            ),
        )
        items = response.get("Items", [])

        while "LastEvaluatedKey" in response:
            response = table.query(
                IndexName="periodId-status-index",
                KeyConditionExpression=(
                    Key("periodId").eq(period_id) & Key("status").eq(status)
                ),
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            items.extend(response.get("Items", []))

        all_items.extend(items)

    return all_items


def _get_all_projects():
    """Scan the Projects table for all projects regardless of status.

    Returns:
        List of all project items.

    Validates: Requirements 10.6
    """
    table = _get_projects_table()
    response = table.scan()
    items = response.get("Items", [])

    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response.get("Items", []))

    return items


def _aggregate_hours_by_project(submission_ids):
    """Aggregate total hours by projectCode across all entries for given submissions.

    Queries the submissionId-index GSI on the Entries table for each submission,
    then sums totalHours per projectCode.

    Args:
        submission_ids: List of submissionId strings.

    Returns:
        Dict mapping projectCode to total Decimal hours.
    """
    if not submission_ids:
        return {}

    table = _get_entries_table()
    project_hours = {}

    for submission_id in submission_ids:
        response = table.query(
            IndexName="submissionId-index",
            KeyConditionExpression=Key("submissionId").eq(submission_id),
        )
        entries = response.get("Items", [])

        while "LastEvaluatedKey" in response:
            response = table.query(
                IndexName="submissionId-index",
                KeyConditionExpression=Key("submissionId").eq(submission_id),
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            entries.extend(response.get("Items", []))

        for entry in entries:
            code = entry.get("projectCode", "")
            hours = _to_decimal(entry.get("totalHours", 0))
            project_hours[code] = project_hours.get(code, Decimal("0")) + hours

    return project_hours


def _get_ytd_chargeability(employee_id, year):
    """Look up YTD chargeability percentage from Employee_Performance table.

    Args:
        employee_id: The employee's userId.
        year: The calendar year.

    Returns:
        Decimal YTD chargeability percentage, or Decimal("0") if not found.

    Validates: Requirements 9.4
    """
    table = _get_performance_table()
    response = table.get_item(Key={"userId": employee_id, "year": year})
    item = response.get("Item")

    if not item:
        return Decimal("0")

    return _to_decimal(item.get("ytdChargabilityPercentage", 0))


def _get_biweekly_period_id(period_id):
    """Look up the biweeklyPeriodId for a given period.

    Args:
        period_id: The timesheet period ID.

    Returns:
        The biweeklyPeriodId string, or None if not found.
    """
    table = dynamodb.Table(os.environ.get("PERIODS_TABLE", ""))
    response = table.get_item(Key={"periodId": period_id})
    item = response.get("Item")

    if not item:
        return None

    return item.get("biweeklyPeriodId")


def _get_biweekly_effort(biweekly_period_id):
    """Compute current biweekly effort per project.

    Finds all periods in the same biweekly cycle, gets their Submitted
    submissions, and aggregates hours by projectCode.

    Args:
        biweekly_period_id: The biweekly period group identifier.

    Returns:
        Dict mapping projectCode to total Decimal hours for the biweekly period.

    Validates: Requirements 10.4
    """
    # Find all periods in this biweekly cycle
    periods_table = dynamodb.Table(os.environ.get("PERIODS_TABLE", ""))
    response = periods_table.scan(
        FilterExpression=Attr("biweeklyPeriodId").eq(biweekly_period_id),
    )
    periods = response.get("Items", [])

    while "LastEvaluatedKey" in response:
        response = periods_table.scan(
            FilterExpression=Attr("biweeklyPeriodId").eq(biweekly_period_id),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        periods.extend(response.get("Items", []))

    # Collect all submission IDs across biweekly periods
    all_submission_ids = []
    for period in periods:
        pid = period["periodId"]
        submissions = _get_submissions_for_period(pid, ["Submitted"])
        all_submission_ids.extend(sub["submissionId"] for sub in submissions)

    return _aggregate_hours_by_project(all_submission_ids)


# ---------------------------------------------------------------------------
# S3 helpers
# ---------------------------------------------------------------------------

def _upload_to_s3(s3_key, content):
    """Upload string content to S3.

    Args:
        s3_key: The S3 object key.
        content: The string content to upload.
    """
    s3_client.put_object(
        Bucket=REPORT_BUCKET,
        Key=s3_key,
        Body=content.encode("utf-8"),
        ContentType="text/csv",
    )


def _find_latest_report(prefix):
    """Find the most recent report file under an S3 prefix.

    Lists objects under the prefix and returns the key with the latest
    LastModified timestamp.

    Args:
        prefix: The S3 key prefix (e.g. "reports/tc-summary/{periodId}/").

    Returns:
        The S3 key of the latest report, or None if no reports exist.
    """
    response = s3_client.list_objects_v2(
        Bucket=REPORT_BUCKET,
        Prefix=prefix,
    )

    contents = response.get("Contents", [])
    if not contents:
        return None

    # Sort by LastModified descending and return the latest
    contents.sort(key=lambda obj: obj["LastModified"], reverse=True)
    return contents[0]["Key"]


def _generate_presigned_url(s3_key):
    """Generate a pre-signed URL for downloading a report from S3.

    Args:
        s3_key: The S3 object key.

    Returns:
        A pre-signed URL string valid for PRESIGNED_URL_EXPIRY seconds.
    """
    url = s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": REPORT_BUCKET, "Key": s3_key},
        ExpiresIn=PRESIGNED_URL_EXPIRY,
    )
    return url


# ---------------------------------------------------------------------------
# CSV and utility helpers
# ---------------------------------------------------------------------------

def _build_csv(columns, rows):
    """Build a CSV string from column headers and row dicts.

    Args:
        columns: List of column header strings.
        rows: List of dicts, each mapping column name to value.

    Returns:
        CSV content as a string.
    """
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return output.getvalue()


def calculate_current_period_chargeability(chargeable_hours, total_hours):
    """Calculate current period chargeability percentage.

    Pure function that computes (chargeable_hours / total_hours) * 100,
    rounded to 2 decimal places using ROUND_HALF_UP.

    Args:
        chargeable_hours: Decimal chargeable hours for the period.
        total_hours: Decimal total hours for the period.

    Returns:
        Decimal chargeability percentage, or Decimal("0") if total hours is 0.

    Validates: Requirements 9.3
    """
    if total_hours > 0:
        return (chargeable_hours / total_hours * Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    return Decimal("0")

def calculate_project_utilization(charged_hours, planned_hours):
    """Calculate project utilization percentage.

    Pure function that computes (charged_hours / planned_hours) * 100,
    rounded to 2 decimal places using ROUND_HALF_UP.

    Args:
        charged_hours: Decimal charged hours for the project.
        planned_hours: Decimal planned hours for the project.

    Returns:
        Decimal utilization percentage, or Decimal("0") if planned hours is 0.

    Validates: Requirements 10.3
    """
    if planned_hours > 0:
        return (charged_hours / planned_hours * Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    return Decimal("0")



def _to_decimal(value):
    """Convert a value to Decimal safely.

    Handles DynamoDB Decimal types, floats, ints, and strings.

    Args:
        value: The value to convert.

    Returns:
        Decimal representation of the value.
    """
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")
