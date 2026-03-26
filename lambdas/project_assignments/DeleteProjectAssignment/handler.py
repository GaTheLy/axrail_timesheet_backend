"""DeleteProjectAssignment Lambda resolver for AppSync.

Environment variables:
    PROJECT_ASSIGNMENTS_TABLE: DynamoDB ProjectAssignments table name
"""

import os

import boto3

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.auth import ForbiddenError, require_user_type

PROJECT_ASSIGNMENTS_TABLE = os.environ.get("PROJECT_ASSIGNMENTS_TABLE", "")

dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    """AppSync Lambda resolver entry point for deleteProjectAssignment."""
    try:
        return delete_project_assignment(event)
    except ForbiddenError as exc:
        raise Exception(exc.message) from exc


def _get_assignments_table():
    return dynamodb.Table(PROJECT_ASSIGNMENTS_TABLE)


def delete_project_assignment(event):
    """Delete a project assignment by assignmentId.

    Validates: Requirements 2.3, 2.7
    """
    require_user_type(event, ["superadmin", "admin"])
    assignment_id = event["arguments"]["assignmentId"]

    table = _get_assignments_table()
    table.delete_item(Key={"assignmentId": assignment_id})

    return True
