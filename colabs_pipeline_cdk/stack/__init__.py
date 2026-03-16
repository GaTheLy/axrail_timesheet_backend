"""
COLABS Timesheet Stack — split into separate CDK stacks.

Stacks:
- TimesheetDynamoDBStack: All DynamoDB tables with GSIs
- TimesheetAuthStack: Cognito User Pool, groups, and client
- TimesheetStorageStack: S3 report bucket
- TimesheetApiStack: AppSync GraphQL API
- TimesheetLambdaStack: All Lambda functions, resolvers, EventBridge rules, and stream triggers
"""

from colabs_pipeline_cdk.stack.dynamodb_stack import TimesheetDynamoDBStack
from colabs_pipeline_cdk.stack.auth_stack import TimesheetAuthStack
from colabs_pipeline_cdk.stack.storage_stack import TimesheetStorageStack
from colabs_pipeline_cdk.stack.api_stack import TimesheetApiStack
from colabs_pipeline_cdk.stack.lambda_stack import TimesheetLambdaStack

__all__ = [
    "TimesheetDynamoDBStack",
    "TimesheetAuthStack",
    "TimesheetStorageStack",
    "TimesheetApiStack",
    "TimesheetLambdaStack",
]
