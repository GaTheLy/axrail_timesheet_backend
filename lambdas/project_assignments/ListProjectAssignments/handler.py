"""ListProjectAssignments Lambda resolver for AppSync.

Environment variables:
    PROJECT_ASSIGNMENTS_TABLE: DynamoDB ProjectAssignments table name
"""

import os

import boto3
from boto3.dynamodb.conditions import Key

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

PROJECT_ASSIGNMENTS_TABLE = os.environ.get("PROJECT_ASSIGNMENTS_TABLE", "")

dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    """AppSync Lambda resolver entry point for listProjectAssignments."""
    return list_project_assignments(event)


def _get_assignments_table():
    return dynamodb.Table(PROJECT_ASSIGNMENTS_TABLE)


def _query_index(table, index_name, key_name, key_value):
    """Query a GSI with pagination support."""
    items = []
    kwargs = {
        "IndexName": index_name,
        "KeyConditionExpression": Key(key_name).eq(key_value),
    }
    while True:
        response = table.query(**kwargs)
        items.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        kwargs["ExclusiveStartKey"] = last_key
    return items


def _scan_all(table):
    """Scan the entire table with pagination support."""
    items = []
    kwargs = {}
    while True:
        response = table.scan(**kwargs)
        items.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        kwargs["ExclusiveStartKey"] = last_key
    return items


def list_project_assignments(event):
    """List project assignments with optional filtering.

    Validates: Requirements 2.4
    """
    filter_input = event["arguments"].get("filter") or {}

    table = _get_assignments_table()

    employee_id = filter_input.get("employeeId")
    supervisor_id = filter_input.get("supervisorId")
    project_id = filter_input.get("projectId")

    if employee_id:
        return _query_index(table, "employeeId-index", "employeeId", employee_id)
    elif supervisor_id:
        return _query_index(table, "supervisorId-index", "supervisorId", supervisor_id)
    elif project_id:
        return _query_index(table, "projectId-index", "projectId", project_id)
    else:
        return _scan_all(table)
