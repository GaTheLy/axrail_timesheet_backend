"""DeleteProject Lambda resolver for AppSync.

Environment variables:
    PROJECTS_TABLE: DynamoDB Projects table name
"""

import os

import boto3

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.auth import ForbiddenError, require_user_type

PROJECTS_TABLE = os.environ.get("PROJECTS_TABLE", "")
dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    try:
        return delete_project(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def delete_project(event):
    """Delete a project."""
    caller = require_user_type(event, ["superadmin", "admin"])
    project_id = event["arguments"]["projectId"]
    table = dynamodb.Table(PROJECTS_TABLE)

    existing = table.get_item(Key={"projectId": project_id}).get("Item")
    if not existing:
        raise ValueError(f"Project '{project_id}' not found")

    if existing.get("approval_status") == "Approved" and caller["userType"] != "superadmin":
        raise ValueError("Cannot delete project: approved entities cannot be deleted")

    table.delete_item(Key={"projectId": project_id})
    return True
