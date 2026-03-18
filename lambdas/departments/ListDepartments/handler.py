"""ListDepartments Lambda resolver for AppSync.

Environment variables:
    DEPARTMENTS_TABLE: DynamoDB Departments table name
"""

import os

import boto3

DEPARTMENTS_TABLE = os.environ.get("DEPARTMENTS_TABLE", "")

dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    """AppSync Lambda resolver entry point for listDepartments."""
    return list_departments(event)


def list_departments(event):
    """List all departments. Validates: Requirements 3.1"""
    table = dynamodb.Table(DEPARTMENTS_TABLE)
    response = table.scan()
    return response.get("Items", [])
