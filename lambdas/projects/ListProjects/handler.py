"""ListProjects Lambda resolver for AppSync.

Environment variables:
    PROJECTS_TABLE: DynamoDB Projects table name
"""

import os

import boto3
from boto3.dynamodb.conditions import Key

PROJECTS_TABLE = os.environ.get("PROJECTS_TABLE", "")
dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    return list_projects(event)


def list_projects(event):
    """List projects with optional filtering. Validates: Requirements 4.9"""
    table = dynamodb.Table(PROJECTS_TABLE)
    args = event.get("arguments") or {}
    filter_input = args.get("filter") or {}

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

    if "status" in filter_input:
        items = [i for i in items if i.get("status") == filter_input["status"]]

    return {"items": items}
