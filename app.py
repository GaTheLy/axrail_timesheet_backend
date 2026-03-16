#!/usr/bin/env python3
"""
COLABS CDK Application Entry Point

Instantiates all pipeline and infrastructure stacks
with environment-specific configurations.

Stacks are fully independent — they communicate via SSM Parameter Store.
"""

import aws_cdk as cdk

from colabs_pipeline_cdk.environment import (
    ENV_CONFIG,
    TIMESHEET_API_STACK_NAME,
    TIMESHEET_AUTH_STACK_NAME,
    TIMESHEET_DYNAMODB_STACK_NAME,
    TIMESHEET_LAMBDA_STACK_NAME,
    TIMESHEET_STORAGE_STACK_NAME,
)
from colabs_pipeline_cdk.stack import (
    TimesheetApiStack,
    TimesheetAuthStack,
    TimesheetDynamoDBStack,
    TimesheetLambdaStack,
    TimesheetStorageStack,
)

app = cdk.App()

# Instantiate Timesheet stacks for each environment
# Each stack is independent — no cross-stack references.
# Deploy order: DynamoDB → Auth → Storage → Api → Lambda
for env_name, config in ENV_CONFIG.items():
    env = cdk.Environment(
        account=config["account"] or None,
        region=config["region"],
    )
    suffix = config["suffix"]

    TimesheetDynamoDBStack(
        app, f"{TIMESHEET_DYNAMODB_STACK_NAME}-{suffix}",
        env_name=env_name, env=env,
    )

    TimesheetAuthStack(
        app, f"{TIMESHEET_AUTH_STACK_NAME}-{suffix}",
        env_name=env_name, env=env,
    )

    TimesheetStorageStack(
        app, f"{TIMESHEET_STORAGE_STACK_NAME}-{suffix}",
        env_name=env_name, env=env,
    )

    TimesheetApiStack(
        app, f"{TIMESHEET_API_STACK_NAME}-{suffix}",
        env_name=env_name, env=env,
    )

    TimesheetLambdaStack(
        app, f"{TIMESHEET_LAMBDA_STACK_NAME}-{suffix}",
        env_name=env_name, env=env,
    )

app.synth()
