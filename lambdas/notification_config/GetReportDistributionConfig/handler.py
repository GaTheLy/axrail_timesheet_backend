"""GetReportDistributionConfig Lambda resolver for AppSync.

Environment variables:
    REPORT_DISTRIBUTION_CONFIG_TABLE: DynamoDB Report_Distribution_Config table name
"""

import os

import boto3

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.auth import get_caller_identity

REPORT_DISTRIBUTION_CONFIG_TABLE = os.environ.get("REPORT_DISTRIBUTION_CONFIG_TABLE", "")
dynamodb = boto3.resource("dynamodb")
CONFIG_ID = "default"


def handler(event, context):
    return get_report_distribution_config(event)


def get_report_distribution_config(event):
    """Get the current report distribution config. Validates: Requirements 12.5"""
    get_caller_identity(event)
    table = dynamodb.Table(REPORT_DISTRIBUTION_CONFIG_TABLE)
    response = table.get_item(Key={"configId": CONFIG_ID})
    item = response.get("Item")
    if not item:
        return {
            "configId": CONFIG_ID,
            "schedule_cron_expression": "",
            "recipient_emails": [],
            "enabled": False,
        }
    return item
