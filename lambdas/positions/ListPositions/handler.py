"""ListPositions Lambda resolver for AppSync.

Environment variables:
    POSITIONS_TABLE: DynamoDB Positions table name
"""

import os

import boto3

POSITIONS_TABLE = os.environ.get("POSITIONS_TABLE", "")
dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    return list_positions(event)


def list_positions(event):
    """List all positions. Validates: Requirements 3.2"""
    table = dynamodb.Table(POSITIONS_TABLE)
    response = table.scan()
    return response.get("Items", [])
