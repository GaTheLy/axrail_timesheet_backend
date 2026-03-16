"""Project Management Lambda resolver for AppSync.

Handles CRUD and approval operations for projects with role-based authorization.
Superadmin creates projects with Approved status; Admin creates with Pending_Approval.
Only Superadmin can approve or reject projects.

Environment variables:
    PROJECTS_TABLE: DynamoDB Projects table name
"""

import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import boto3
from boto3.dynamodb.conditions import Key

# Add parent directory to path for shared imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.auth import ForbiddenError, get_caller_identity, require_user_type

PROJECTS_TABLE = os.environ.get("PROJECTS_TABLE", "")

VALID_STATUSES = {"Active", "Inactive", "Completed"}
VALID_APPROVAL_STATUSES = {"Pending_Approval", "Approved", "Rejected"}

dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    """AppSync Lambda resolver entry point.

    Routes to the appropriate operation based on event['info']['fieldName'].
    """
    field = event["info"]["fieldName"]
    resolvers = {
        "createProject": create_project,
        "approveProject": approve_project,
        "rejectProject": reject_project,
        "updateProject": update_project,
        "listProjects": list_projects,
    }

    resolver = resolvers.get(field)
    if not resolver:
        raise ValueError(f"Unknown field: {field}")

    try:
        return resolver(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def _get_table():
    """Return the DynamoDB Projects table resource."""
    return dynamodb.Table(PROJECTS_TABLE)


def _now_iso():
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _validate_planned_hours(value):
    """Validate that plannedHours is a positive float.

    Args:
        value: The plannedHours value to validate.

    Returns:
        Decimal representation of the value for DynamoDB storage.

    Raises:
        ValueError: If the value is not a positive number.
    """
    try:
        hours = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(
            f"Invalid plannedHours: '{value}'. Must be a positive number"
        )

    if hours <= 0:
        raise ValueError(
            f"Invalid plannedHours: '{value}'. Must be a positive number"
        )

    return hours


def _check_project_code_unique(table, project_code, exclude_project_id=None):
    """Query the projectCode-index GSI to ensure projectCode uniqueness.

    Args:
        table: DynamoDB Projects Table resource.
        project_code: Project code to check.
        exclude_project_id: Optional projectId to exclude (for updates).

    Raises:
        ValueError: If the project code is already in use.
    """
    response = table.query(
        IndexName="projectCode-index",
        KeyConditionExpression=Key("projectCode").eq(project_code),
    )
    for item in response.get("Items", []):
        if item["projectId"] != exclude_project_id:
            raise ValueError(
                f"Project code '{project_code}' is already in use"
            )


def create_project(event):
    """Create a new project.

    Superadmin creates with approval_status=Approved.
    Admin creates with approval_status=Pending_Approval.

    Validates: Requirements 4.1, 4.2, 4.6, 4.8
    """
    caller = require_user_type(event, ["superadmin", "admin"])
    args = event["arguments"]["input"]

    project_code = args["projectCode"]
    project_name = args["projectName"]
    start_date = args["startDate"]
    planned_hours = _validate_planned_hours(args["plannedHours"])
    project_manager_id = args["projectManagerId"]
    status = args.get("status", "Active")

    if status not in VALID_STATUSES:
        raise ValueError(
            f"Invalid status: '{status}'. Must be one of: {sorted(VALID_STATUSES)}"
        )

    table = _get_table()

    # Enforce unique projectCode
    _check_project_code_unique(table, project_code)

    # Determine approval_status based on caller's userType
    if caller["userType"] == "superadmin":
        approval_status = "Approved"
    else:
        approval_status = "Pending_Approval"

    now = _now_iso()
    project_id = str(uuid.uuid4())

    item = {
        "projectId": project_id,
        "projectCode": project_code,
        "projectName": project_name,
        "startDate": start_date,
        "plannedHours": planned_hours,
        "projectManagerId": project_manager_id,
        "status": status,
        "approval_status": approval_status,
        "rejectionReason": "",
        "createdAt": now,
        "createdBy": caller["userId"],
        "updatedAt": now,
        "updatedBy": caller["userId"],
    }

    table.put_item(Item=item)

    return item


def approve_project(event):
    """Approve a Pending_Approval project.

    Only Superadmin can approve projects. The project must currently
    have approval_status of Pending_Approval.

    Validates: Requirements 4.3, 4.7
    """
    caller = require_user_type(event, ["superadmin"])
    project_id = event["arguments"]["projectId"]

    table = _get_table()

    existing = table.get_item(Key={"projectId": project_id}).get("Item")
    if not existing:
        raise ValueError(f"Project '{project_id}' not found")

    if existing["approval_status"] != "Pending_Approval":
        raise ValueError(
            f"Cannot approve project with approval_status "
            f"'{existing['approval_status']}'. "
            f"Only Pending_Approval projects can be approved"
        )

    now = _now_iso()

    result = table.update_item(
        Key={"projectId": project_id},
        UpdateExpression=(
            "SET #approval_status = :approval_status, "
            "#updatedAt = :updatedAt, #updatedBy = :updatedBy"
        ),
        ExpressionAttributeNames={
            "#approval_status": "approval_status",
            "#updatedAt": "updatedAt",
            "#updatedBy": "updatedBy",
        },
        ExpressionAttributeValues={
            ":approval_status": "Approved",
            ":updatedAt": now,
            ":updatedBy": caller["userId"],
        },
        ReturnValues="ALL_NEW",
    )

    return result["Attributes"]


def reject_project(event):
    """Reject a Pending_Approval project with a reason.

    Only Superadmin can reject projects. The project must currently
    have approval_status of Pending_Approval.

    Validates: Requirements 4.4, 4.7
    """
    caller = require_user_type(event, ["superadmin"])
    project_id = event["arguments"]["projectId"]
    reason = event["arguments"].get("reason", "")

    if not reason or not reason.strip():
        raise ValueError("Rejection reason is required")

    table = _get_table()

    existing = table.get_item(Key={"projectId": project_id}).get("Item")
    if not existing:
        raise ValueError(f"Project '{project_id}' not found")

    if existing["approval_status"] != "Pending_Approval":
        raise ValueError(
            f"Cannot reject project with approval_status "
            f"'{existing['approval_status']}'. "
            f"Only Pending_Approval projects can be rejected"
        )

    now = _now_iso()

    result = table.update_item(
        Key={"projectId": project_id},
        UpdateExpression=(
            "SET #approval_status = :approval_status, "
            "#rejectionReason = :rejectionReason, "
            "#updatedAt = :updatedAt, #updatedBy = :updatedBy"
        ),
        ExpressionAttributeNames={
            "#approval_status": "approval_status",
            "#rejectionReason": "rejectionReason",
            "#updatedAt": "updatedAt",
            "#updatedBy": "updatedBy",
        },
        ExpressionAttributeValues={
            ":approval_status": "Rejected",
            ":rejectionReason": reason.strip(),
            ":updatedAt": now,
            ":updatedBy": caller["userId"],
        },
        ReturnValues="ALL_NEW",
    )

    return result["Attributes"]


def update_project(event):
    """Update an existing project.

    Superadmin or Admin can update projects. Persists changes with
    updatedBy/updatedAt. Validates plannedHours and projectCode uniqueness
    if those fields are being changed.

    Validates: Requirements 4.7, 4.8
    """
    caller = require_user_type(event, ["superadmin", "admin"])
    project_id = event["arguments"]["projectId"]
    args = event["arguments"]["input"]

    table = _get_table()

    existing = table.get_item(Key={"projectId": project_id}).get("Item")
    if not existing:
        raise ValueError(f"Project '{project_id}' not found")

    # If projectCode is being changed, check uniqueness
    new_code = args.get("projectCode")
    if new_code and new_code != existing.get("projectCode"):
        _check_project_code_unique(table, new_code, exclude_project_id=project_id)

    # Validate plannedHours if provided
    if "plannedHours" in args:
        args["plannedHours"] = _validate_planned_hours(args["plannedHours"])

    # Validate status if provided
    if "status" in args and args["status"] not in VALID_STATUSES:
        raise ValueError(
            f"Invalid status: '{args['status']}'. "
            f"Must be one of: {sorted(VALID_STATUSES)}"
        )

    now = _now_iso()

    # Build update expression dynamically
    update_parts = []
    expr_names = {}
    expr_values = {":updatedAt": now, ":updatedBy": caller["userId"]}
    update_parts.append("#updatedAt = :updatedAt")
    update_parts.append("#updatedBy = :updatedBy")
    expr_names["#updatedAt"] = "updatedAt"
    expr_names["#updatedBy"] = "updatedBy"

    allowed_fields = [
        "projectCode", "projectName", "startDate",
        "plannedHours", "projectManagerId", "status",
    ]
    for field in allowed_fields:
        if field in args:
            placeholder = f":{field}"
            name_placeholder = f"#{field}"
            expr_values[placeholder] = args[field]
            expr_names[name_placeholder] = field
            update_parts.append(f"{name_placeholder} = {placeholder}")

    update_expr = "SET " + ", ".join(update_parts)

    result = table.update_item(
        Key={"projectId": project_id},
        UpdateExpression=update_expr,
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
        ReturnValues="ALL_NEW",
    )

    return result["Attributes"]


def list_projects(event):
    """List projects with optional filtering.

    Supports filtering by approval_status (via GSI) and projectManagerId (via GSI).
    All authenticated users can query projects.

    Validates: Requirements 4.9
    """
    table = _get_table()
    args = event.get("arguments") or {}
    filter_input = args.get("filter") or {}

    # Use GSI for approval_status filter
    if "approval_status" in filter_input:
        response = table.query(
            IndexName="approval_status-index",
            KeyConditionExpression=Key("approval_status").eq(
                filter_input["approval_status"]
            ),
        )
        items = response.get("Items", [])
    elif "projectManagerId" in filter_input:
        response = table.query(
            IndexName="projectManagerId-index",
            KeyConditionExpression=Key("projectManagerId").eq(
                filter_input["projectManagerId"]
            ),
        )
        items = response.get("Items", [])
    else:
        response = table.scan()
        items = response.get("Items", [])

    # Apply additional client-side filters
    if "status" in filter_input:
        items = [i for i in items if i.get("status") == filter_input["status"]]

    return {"items": items}
