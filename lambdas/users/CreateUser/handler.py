"""CreateUser Lambda resolver for AppSync.

Creates a new user account with role-based authorization.
Superadmins can create admin and user accounts; Admins can create user accounts only.

Environment variables:
    USERS_TABLE: DynamoDB Users table name
    USER_POOL_ID: Cognito User Pool ID
"""

import os
import uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Attr, Key

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.auth import ForbiddenError, require_user_type

USERS_TABLE = os.environ.get("USERS_TABLE", "")
USER_POOL_ID = os.environ.get("USER_POOL_ID", "")

VALID_ROLES = {"Project_Manager", "Tech_Lead", "Employee"}
VALID_USER_TYPES = {"superadmin", "admin", "user"}

dynamodb = boto3.resource("dynamodb")
cognito = boto3.client("cognito-idp")


def handler(event, context):
    """AppSync Lambda resolver entry point for createUser."""
    try:
        return create_user(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def _get_table():
    """Return the DynamoDB Users table resource."""
    return dynamodb.Table(USERS_TABLE)


def _now_iso():
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _validate_enum(value, valid_values, field_name):
    """Raise ValueError if value is not in the valid set."""
    if value not in valid_values:
        raise ValueError(
            f"Invalid {field_name}: '{value}'. Must be one of: {sorted(valid_values)}"
        )


def _check_email_unique(table, email):
    """Query the email-index GSI to ensure email uniqueness."""
    response = table.query(
        IndexName="email-index",
        KeyConditionExpression=Key("email").eq(email),
    )
    for item in response.get("Items", []):
        raise ValueError(f"Email '{email}' is already in use")


ALLOWED_EMAIL_DOMAIN = "@axrail.com"


def _validate_email_domain(email):
    """Raise ValueError if email is not from the allowed domain."""
    if not email.lower().endswith(ALLOWED_EMAIL_DOMAIN):
        raise ValueError("Only @axrail.com email addresses are allowed")

def generate_next_user_code(table):
    """Generate the next sequential user code (USR-NNN).

    Scans the Users table for existing userCode values, finds the highest
    numeric suffix, and returns the next code in sequence. Returns USR-001
    when no existing codes are found.

    Validates: Requirements 3.2
    """
    response = table.scan(
        ProjectionExpression="userCode",
        FilterExpression=Attr("userCode").exists(),
    )
    items = response.get("Items", [])

    # Handle DynamoDB pagination for large tables
    while "LastEvaluatedKey" in response:
        response = table.scan(
            ProjectionExpression="userCode",
            FilterExpression=Attr("userCode").exists(),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))

    codes = [item["userCode"] for item in items if "userCode" in item]

    if not codes:
        return "USR-001"

    max_num = max(int(code.split("-")[1]) for code in codes)
    next_num = max_num + 1
    return f"USR-{next_num:03d}"



def _authorize_mutation(caller, target_user_type):
    """Validate that the caller can perform a mutation on the target user type."""
    caller_type = caller["userType"]
    if caller_type == "superadmin":
        if target_user_type not in ("admin", "user"):
            raise ForbiddenError(f"Superadmin cannot manage '{target_user_type}' accounts")
    elif caller_type == "admin":
        if target_user_type != "user":
            raise ForbiddenError("Admin can only manage user accounts")
    else:
        raise ForbiddenError("Insufficient permissions to manage users")


def create_user(event):
    """Create a new user account.

    Validates: Requirements 2.1, 2.4, 2.7, 2.8, 2.9, 2.10
    """
    caller = require_user_type(event, ["superadmin", "admin"])
    args = event["arguments"]["input"]

    target_user_type = args["userType"]
    email = args["email"]
    full_name = args["fullName"]
    department_id = args.get("departmentId", "")
    supervisor_id = args.get("supervisorId") or None

    _validate_enum(target_user_type, VALID_USER_TYPES, "userType")
    _authorize_mutation(caller, target_user_type)

    # role and positionId are only required for regular users
    if target_user_type == "user":
        role = args.get("role", "")
        position_id = args.get("positionId", "")
        if not role:
            raise ValueError("role is required for userType 'user'")
        if not position_id:
            raise ValueError("positionId is required for userType 'user'")
        _validate_enum(role, VALID_ROLES, "role")
    else:
        role = args.get("role", "")
        position_id = args.get("positionId", "")

    # When an admin creates a user (userType: user), force role to Employee
    if caller["userType"] == "admin" and target_user_type == "user":
        role = "Employee"

    _validate_email_domain(email)

    table = _get_table()
    _check_email_unique(table, email)

    user_code = generate_next_user_code(table)

    now = _now_iso()

    approval_status = "Approved"

    # Create Cognito user first to get the sub (used as userId)
    cognito_response = cognito.admin_create_user(
        UserPoolId=USER_POOL_ID,
        Username=email,
        UserAttributes=[
            {"Name": "email", "Value": email},
            {"Name": "email_verified", "Value": "true"},
            {"Name": "name", "Value": full_name},
            {"Name": "custom:userType", "Value": target_user_type},
            {"Name": "custom:role", "Value": role},
            {"Name": "custom:departmentId", "Value": department_id},
            {"Name": "custom:positionId", "Value": position_id},
        ],
        DesiredDeliveryMediums=["EMAIL"],
    )

    # Use Cognito sub as the userId so resolvers can match by token sub
    cognito_attrs = cognito_response.get("User", {}).get("Attributes", [])
    user_id = next(
        (a["Value"] for a in cognito_attrs if a["Name"] == "sub"),
        str(uuid.uuid4()),  # fallback, should not happen
    )

    item = {
        "userId": user_id,
        "userCode": user_code,
        "email": email,
        "fullName": full_name,
        "userType": target_user_type,
        "status": "active",
        "approval_status": approval_status,
        "rejectionReason": "",
        "createdAt": now,
        "createdBy": caller["userId"],
        "updatedAt": now,
        "updatedBy": caller["userId"],
    }
    # Only include GSI key attributes if non-empty (DynamoDB rejects empty string GSI keys)
    if role:
        item["role"] = role
    if position_id:
        item["positionId"] = position_id
    if department_id:
        item["departmentId"] = department_id
    if supervisor_id:
        item["supervisorId"] = supervisor_id

    table.put_item(Item=item)

    cognito.admin_add_user_to_group(
        UserPoolId=USER_POOL_ID,
        Username=email,
        GroupName=target_user_type,
    )

    # Auto-create a Draft timesheet submission for the current period (user type only)
    if target_user_type == "user":
        try:
            _create_draft_submission_for_current_period(user_id, now)
        except Exception:
            pass  # Don't fail user creation if submission creation fails

    return item


def _create_draft_submission_for_current_period(employee_id, now):
    """Find the current active period and create a Draft submission for the new user."""
    from datetime import date, timedelta, timezone as tz
    from decimal import Decimal

    periods_table_name = os.environ.get("PERIODS_TABLE", "")
    submissions_table_name = os.environ.get("SUBMISSIONS_TABLE", "")
    if not periods_table_name or not submissions_table_name:
        return

    periods_table = dynamodb.Table(periods_table_name)
    submissions_table = dynamodb.Table(submissions_table_name)

    # Find the current active (unlocked) period
    MYT = tz(timedelta(hours=8))
    today = datetime.now(MYT).date()

    from boto3.dynamodb.conditions import Attr
    response = periods_table.scan(FilterExpression=Attr("isLocked").eq(False))
    items = response.get("Items", [])

    current_period = None
    for item in items:
        start = date.fromisoformat(str(item["startDate"]))
        end = date.fromisoformat(str(item["endDate"]))
        if start <= today <= end:
            current_period = item
            break

    if not current_period:
        return

    period_id = current_period["periodId"]

    # Check if submission already exists for this user + period
    from boto3.dynamodb.conditions import Key
    existing = submissions_table.query(
        IndexName="periodId-status-index",
        KeyConditionExpression=Key("periodId").eq(period_id),
    )
    for sub in existing.get("Items", []):
        if sub.get("employeeId") == employee_id:
            return  # Already has a submission

    submission_id = str(uuid.uuid4())
    submissions_table.put_item(Item={
        "submissionId": submission_id,
        "periodId": period_id,
        "employeeId": employee_id,
        "status": "Draft",
        "archived": False,
        "totalHours": Decimal("0"),
        "chargeableHours": Decimal("0"),
        "createdAt": now,
        "updatedAt": now,
        "updatedBy": employee_id,
    })
