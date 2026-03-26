"""Shared utilities for querying the ProjectAssignments DynamoDB table.

Provides helper functions to look up supervised employees and employee supervisors
via the Timesheet_ProjectAssignments table's GSIs, with pagination and deduplication.
"""

import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource("dynamodb")


def get_supervised_employee_ids(project_assignments_table_name, supervisor_id):
    """Query ProjectAssignments table to get unique employee IDs for a supervisor.

    Queries the ``supervisorId-index`` GSI and handles pagination so that all
    matching records are retrieved regardless of result-set size.  The returned
    list contains each ``employeeId`` at most once, even when the same employee
    appears in multiple assignments for the given supervisor.

    Args:
        project_assignments_table_name: DynamoDB table name for ProjectAssignments.
        supervisor_id: The supervisor's userId to look up.

    Returns:
        List of unique employee ID strings.
    """
    table = dynamodb.Table(project_assignments_table_name)

    response = table.query(
        IndexName="supervisorId-index",
        KeyConditionExpression=Key("supervisorId").eq(supervisor_id),
    )
    items = response.get("Items", [])

    while "LastEvaluatedKey" in response:
        response = table.query(
            IndexName="supervisorId-index",
            KeyConditionExpression=Key("supervisorId").eq(supervisor_id),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))

    employee_ids = {item["employeeId"] for item in items}
    return list(employee_ids)


def get_employee_supervisor_ids(project_assignments_table_name, employee_id):
    """Query ProjectAssignments table to get unique supervisor IDs for an employee.

    Queries the ``employeeId-index`` GSI and handles pagination so that all
    matching records are retrieved.  The returned list contains each
    ``supervisorId`` at most once.

    Args:
        project_assignments_table_name: DynamoDB table name for ProjectAssignments.
        employee_id: The employee's userId to look up.

    Returns:
        List of unique supervisor ID strings.
    """
    table = dynamodb.Table(project_assignments_table_name)

    response = table.query(
        IndexName="employeeId-index",
        KeyConditionExpression=Key("employeeId").eq(employee_id),
    )
    items = response.get("Items", [])

    while "LastEvaluatedKey" in response:
        response = table.query(
            IndexName="employeeId-index",
            KeyConditionExpression=Key("employeeId").eq(employee_id),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))

    supervisor_ids = {item["supervisorId"] for item in items}
    return list(supervisor_ids)
