"""Notification Service Lambda for automated report distribution via email.

Triggered by EventBridge on a configured schedule. Performs the following:
  1. Reads Report_Distribution_Config from DynamoDB to check if enabled
  2. Generates a Project Summary CSV and sends it via SES to configured
     recipient_emails list
  3. For each Tech_Lead in the Users table, generates a TC Summary CSV
     and sends it via SES to that Tech_Lead's email
  4. On any SES failure, logs the recipient, report type, and error details
     without crashing the Lambda

Environment variables:
    SUBMISSIONS_TABLE: DynamoDB Timesheet_Submissions table name
    ENTRIES_TABLE: DynamoDB Timesheet_Entries table name
    USERS_TABLE: DynamoDB Users table name
    PROJECTS_TABLE: DynamoDB Projects table name
    EMPLOYEE_PERFORMANCE_TABLE: DynamoDB Employee_Performance table name
    PERIODS_TABLE: DynamoDB Timesheet_Periods table name
    REPORT_DISTRIBUTION_CONFIG_TABLE: DynamoDB Report_Distribution_Config table
    REPORT_BUCKET: S3 bucket for report storage
    SES_FROM_EMAIL: Sender email address for SES
"""

import csv
import io
import logging
import os
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import boto3
from boto3.dynamodb.conditions import Attr, Key

# Add parent directory to path for shared imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logger = logging.getLogger()
logger.setLevel(logging.INFO)

SUBMISSIONS_TABLE = os.environ.get("SUBMISSIONS_TABLE", "")
ENTRIES_TABLE = os.environ.get("ENTRIES_TABLE", "")
USERS_TABLE = os.environ.get("USERS_TABLE", "")
PROJECTS_TABLE = os.environ.get("PROJECTS_TABLE", "")
EMPLOYEE_PERFORMANCE_TABLE = os.environ.get("EMPLOYEE_PERFORMANCE_TABLE", "")
PERIODS_TABLE = os.environ.get("PERIODS_TABLE", "")
REPORT_DISTRIBUTION_CONFIG_TABLE = os.environ.get(
    "REPORT_DISTRIBUTION_CONFIG_TABLE", ""
)
REPORT_BUCKET = os.environ.get("REPORT_BUCKET", "")
SES_FROM_EMAIL = os.environ.get("SES_FROM_EMAIL", "")

dynamodb = boto3.resource("dynamodb")
ses_client = boto3.client("ses")
s3_client = boto3.client("s3")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def handler(event, context):
    """EventBridge scheduled event entry point.

    Reads the distribution config, then generates and emails reports.

    Validates: Requirements 12.1, 12.2, 12.3, 12.6
    """
    logger.info("Notification service Lambda invoked: %s", event)

    # 1. Check distribution config
    config = _get_distribution_config()
    if not config:
        logger.info("No report distribution config found. Skipping.")
        return {"sent": 0, "errors": 0}

    if not config.get("enabled", False):
        logger.info("Report distribution is disabled. Skipping.")
        return {"sent": 0, "errors": 0}

    recipient_emails = config.get("recipient_emails", [])

    # 2. Determine the current active period
    period = _get_current_period()
    if not period:
        logger.warning("No active timesheet period found. Skipping.")
        return {"sent": 0, "errors": 0}

    period_id = period["periodId"]
    period_string = period.get("periodString", period_id)
    logger.info("Using period: %s (%s)", period_id, period_string)

    sent_count = 0
    error_count = 0

    # 3. Generate and send Project Summary to configured recipients
    if recipient_emails:
        project_csv = _generate_project_summary_csv(period_id)
        if project_csv:
            for recipient in recipient_emails:
                success = _send_email_with_attachment(
                    recipient=recipient,
                    subject=f"Project Summary Report - {period_string}",
                    body_text=(
                        f"Please find attached the Project Summary Report "
                        f"for period {period_string}."
                    ),
                    attachment_content=project_csv,
                    attachment_filename=f"project_summary_{period_id}.csv",
                    report_type="Project Summary",
                )
                if success:
                    sent_count += 1
                else:
                    error_count += 1

    # 4. For each Tech_Lead, generate TC Summary and send to their email
    tech_leads = _get_tech_leads()
    for tech_lead in tech_leads:
        tl_id = tech_lead["userId"]
        tl_email = tech_lead.get("email", "")
        tl_name = tech_lead.get("fullName", "Unknown")

        if not tl_email:
            logger.warning(
                "Tech Lead %s (%s) has no email address. Skipping.",
                tl_id, tl_name,
            )
            continue

        tc_csv = _generate_tc_summary_csv(tl_id, period_id)
        if not tc_csv:
            logger.info(
                "No TC Summary data for Tech Lead %s (%s). Skipping email.",
                tl_id, tl_name,
            )
            continue

        success = _send_email_with_attachment(
            recipient=tl_email,
            subject=f"TC Summary Report - {period_string}",
            body_text=(
                f"Hi {tl_name},\n\n"
                f"Please find attached the TC Summary Report "
                f"for period {period_string}."
            ),
            attachment_content=tc_csv,
            attachment_filename=f"tc_summary_{tl_id}_{period_id}.csv",
            report_type="TC Summary",
        )
        if success:
            sent_count += 1
        else:
            error_count += 1

    logger.info(
        "Notification service complete. Sent: %d, Errors: %d",
        sent_count, error_count,
    )
    return {"sent": sent_count, "errors": error_count}


# ---------------------------------------------------------------------------
# Config and period helpers
# ---------------------------------------------------------------------------

def _get_distribution_config():
    """Read the singleton Report_Distribution_Config from DynamoDB.

    Returns:
        Config dict or None if not found.
    """
    table = dynamodb.Table(REPORT_DISTRIBUTION_CONFIG_TABLE)
    response = table.get_item(Key={"configId": "default"})
    return response.get("Item")


def _get_current_period():
    """Return the current active period (today falls between start and end).

    Falls back to the most recent period if none spans today.

    Returns:
        Period item dict, or None if no periods exist.
    """
    table = dynamodb.Table(PERIODS_TABLE)
    today = date.today()

    response = table.scan()
    items = response.get("Items", [])
    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response.get("Items", []))

    if not items:
        return None

    # Try to find a period that contains today
    for item in items:
        start = _parse_date(item["startDate"])
        end = _parse_date(item["endDate"])
        if start <= today <= end:
            return item

    # Fallback: return the most recent period by endDate
    items.sort(key=lambda p: p.get("endDate", ""), reverse=True)
    return items[0]


def _parse_date(date_str):
    """Parse an ISO 8601 date string to a date object.

    Args:
        date_str: Date string in YYYY-MM-DD format.

    Returns:
        A date object.
    """
    return datetime.strptime(date_str[:10], "%Y-%m-%d").date()


# ---------------------------------------------------------------------------
# Data query helpers
# ---------------------------------------------------------------------------

def _get_submissions_table():
    """Return the DynamoDB Timesheet_Submissions table resource."""
    return dynamodb.Table(SUBMISSIONS_TABLE)


def _get_entries_table():
    """Return the DynamoDB Timesheet_Entries table resource."""
    return dynamodb.Table(ENTRIES_TABLE)


def _get_users_table():
    """Return the DynamoDB Users table resource."""
    return dynamodb.Table(USERS_TABLE)


def _get_projects_table():
    """Return the DynamoDB Projects table resource."""
    return dynamodb.Table(PROJECTS_TABLE)


def _get_performance_table():
    """Return the DynamoDB Employee_Performance table resource."""
    return dynamodb.Table(EMPLOYEE_PERFORMANCE_TABLE)


def _get_tech_leads():
    """Query the Users table for all users with role Tech_Lead.

    Returns:
        List of Tech_Lead user items.
    """
    table = _get_users_table()
    response = table.scan(
        FilterExpression=Attr("role").eq("Tech_Lead"),
    )
    items = response.get("Items", [])

    while "LastEvaluatedKey" in response:
        response = table.scan(
            FilterExpression=Attr("role").eq("Tech_Lead"),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))

    return items


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

    Args:
        period_id: The timesheet period ID.
        statuses: List of status strings (e.g. ["Approved", "Locked"]).

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
    """
    table = _get_projects_table()
    response = table.scan()
    items = response.get("Items", [])

    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response.get("Items", []))

    return items


def _aggregate_hours_by_project(submission_ids):
    """Aggregate total hours by projectCode across entries for given submissions.

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
    table = dynamodb.Table(PERIODS_TABLE)
    response = table.get_item(Key={"periodId": period_id})
    item = response.get("Item")

    if not item:
        return None

    return item.get("biweeklyPeriodId")


def _get_biweekly_effort(biweekly_period_id):
    """Compute current biweekly effort per project.

    Args:
        biweekly_period_id: The biweekly period group identifier.

    Returns:
        Dict mapping projectCode to total Decimal hours for the biweekly period.
    """
    periods_table = dynamodb.Table(PERIODS_TABLE)
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

    all_submission_ids = []
    for period in periods:
        pid = period["periodId"]
        submissions = _get_submissions_for_period(pid, ["Approved", "Locked"])
        all_submission_ids.extend(sub["submissionId"] for sub in submissions)

    return _aggregate_hours_by_project(all_submission_ids)


# ---------------------------------------------------------------------------
# Report CSV generation
# ---------------------------------------------------------------------------

def _generate_project_summary_csv(period_id):
    """Generate Project Summary CSV content for a period.

    Columns: Project Charge Code, Project Name, Planned Hours, Charged Hours,
             Utilization, Current Biweekly Effort

    Args:
        period_id: The timesheet period ID.

    Returns:
        CSV content as a string, or None if no projects exist.

    Validates: Requirements 12.1
    """
    logger.info("Generating Project Summary CSV for period=%s", period_id)

    projects = _get_all_projects()
    if not projects:
        logger.info("No projects found for Project Summary")
        return None

    submissions = _get_submissions_for_period(period_id, ["Approved", "Locked"])
    submission_ids = [sub["submissionId"] for sub in submissions]
    project_hours = _aggregate_hours_by_project(submission_ids)

    biweekly_period_id = _get_biweekly_period_id(period_id)
    biweekly_hours = {}
    if biweekly_period_id:
        biweekly_hours = _get_biweekly_effort(biweekly_period_id)

    rows = []
    for project in projects:
        project_code = project.get("projectCode", "")
        project_name = project.get("projectName", "")
        planned_hours = _to_decimal(project.get("plannedHours", 0))
        charged_hours = _to_decimal(project_hours.get(project_code, 0))

        if planned_hours > 0:
            utilization = (
                charged_hours / planned_hours * Decimal("100")
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            utilization = Decimal("0")

        biweekly_effort = _to_decimal(biweekly_hours.get(project_code, 0))

        rows.append({
            "Project Charge Code": project_code,
            "Project Name": project_name,
            "Planned Hours": str(planned_hours),
            "Charged Hours": str(charged_hours),
            "Utilization": str(utilization),
            "Current Biweekly Effort": str(biweekly_effort),
        })

    return _build_csv(
        ["Project Charge Code", "Project Name", "Planned Hours",
         "Charged Hours", "Utilization", "Current Biweekly Effort"],
        rows,
    )


def _generate_tc_summary_csv(tech_lead_id, period_id):
    """Generate TC Summary CSV content for a Tech Lead and period.

    Columns: Name, Chargable Hours, Total Hours, Current Period Chargability,
             YTD Chargability

    Args:
        tech_lead_id: The Tech Lead's userId.
        period_id: The timesheet period ID.

    Returns:
        CSV content as a string, or None if no data.

    Validates: Requirements 12.2
    """
    logger.info(
        "Generating TC Summary CSV for tech_lead=%s, period=%s",
        tech_lead_id, period_id,
    )

    employees = _get_supervised_employees(tech_lead_id)
    if not employees:
        logger.info("No employees found under tech lead %s", tech_lead_id)
        return None

    employee_map = {emp["userId"]: emp for emp in employees}

    submissions = _get_submissions_for_period(period_id, ["Approved", "Locked"])
    supervised_ids = set(employee_map.keys())
    relevant_submissions = [
        sub for sub in submissions
        if sub.get("employeeId") in supervised_ids
    ]

    if not relevant_submissions:
        logger.info(
            "No Approved/Locked submissions for tech lead %s in period %s",
            tech_lead_id, period_id,
        )
        return None

    year = datetime.now(timezone.utc).year

    rows = []
    for submission in relevant_submissions:
        emp_id = submission["employeeId"]
        emp = employee_map.get(emp_id, {})
        name = emp.get("fullName", "Unknown")

        chargeable_hours = _to_decimal(submission.get("chargeableHours", 0))
        total_hours = _to_decimal(submission.get("totalHours", 0))

        if total_hours > 0:
            current_chargeability = (
                chargeable_hours / total_hours * Decimal("100")
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            current_chargeability = Decimal("0")

        ytd_chargeability = _get_ytd_chargeability(emp_id, year)

        rows.append({
            "Name": name,
            "Chargable Hours": str(chargeable_hours),
            "Total Hours": str(total_hours),
            "Current Period Chargability": str(current_chargeability),
            "YTD Chargability": str(ytd_chargeability),
        })

    return _build_csv(
        ["Name", "Chargable Hours", "Total Hours",
         "Current Period Chargability", "YTD Chargability"],
        rows,
    )


# ---------------------------------------------------------------------------
# Email sending via SES
# ---------------------------------------------------------------------------

def _send_email_with_attachment(
    recipient, subject, body_text, attachment_content,
    attachment_filename, report_type,
):
    """Send an email with a CSV attachment using SES send_raw_email.

    Constructs a MIME multipart message with a text body and CSV attachment,
    then sends via SES. On failure, logs the recipient, report type, and
    error details without raising.

    Args:
        recipient: Destination email address.
        subject: Email subject line.
        body_text: Plain text email body.
        attachment_content: CSV content as a string.
        attachment_filename: Filename for the CSV attachment.
        report_type: Report type label for logging (e.g. "Project Summary").

    Returns:
        True if sent successfully, False on failure.

    Validates: Requirements 12.3, 12.6
    """
    try:
        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"] = SES_FROM_EMAIL
        msg["To"] = recipient

        # Text body
        body_part = MIMEText(body_text, "plain")
        msg.attach(body_part)

        # CSV attachment
        attachment = MIMEApplication(attachment_content.encode("utf-8"))
        attachment.add_header(
            "Content-Disposition", "attachment",
            filename=attachment_filename,
        )
        attachment.add_header("Content-Type", "text/csv")
        msg.attach(attachment)

        ses_client.send_raw_email(
            Source=SES_FROM_EMAIL,
            Destinations=[recipient],
            RawMessage={"Data": msg.as_string()},
        )

        logger.info(
            "Successfully sent %s report to %s", report_type, recipient,
        )
        return True

    except Exception:
        logger.error(
            "Failed to send email. recipient=%s, report_type=%s",
            recipient, report_type,
            exc_info=True,
        )
        return False


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
