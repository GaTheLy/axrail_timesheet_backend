"""
Timesheet API Stack

AppSync GraphQL API with Cognito User Pool authorization.
Looks up User Pool from SSM. Exports API ID and URL to SSM.
"""

import os

from aws_cdk import Stack, Tags, aws_appsync as appsync, aws_cognito as cognito, aws_ssm as ssm
from constructs import Construct

from colabs_pipeline_cdk.environment import (
    ENV_CONFIG,
    PROJECT_NAME,
    TIMESHEET_API_NAME,
    TIMESHEET_SSM_PREFIX,
)


class TimesheetApiStack(Stack):
    """CDK Stack for the Timesheet AppSync GraphQL API."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        env_name: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.env_name = env_name
        self.env_config = ENV_CONFIG[env_name]

        Tags.of(self).add("Project", PROJECT_NAME)
        Tags.of(self).add("Component", "Timesheet-Api")
        Tags.of(self).add("Environment", env_name)

        # Look up User Pool from SSM (deploy-time resolution)
        user_pool_id = ssm.StringParameter.value_for_string_parameter(
            self, f"{TIMESHEET_SSM_PREFIX}/{env_name}/auth/user-pool-id",
        )
        user_pool = cognito.UserPool.from_user_pool_id(
            self, "ImportedUserPool", user_pool_id,
        )

        self._create_appsync_api(user_pool)
        self._export_ssm_params()

    def _ssm_path(self, key: str) -> str:
        return f"{TIMESHEET_SSM_PREFIX}/{self.env_name}/api/{key}"

    def _export_ssm_params(self) -> None:
        ssm.StringParameter(
            self, "SSM-graphql-api-id",
            parameter_name=self._ssm_path("graphql-api-id"),
            string_value=self.graphql_api.api_id,
        )
        ssm.StringParameter(
            self, "SSM-graphql-api-url",
            parameter_name=self._ssm_path("graphql-api-url"),
            string_value=self.graphql_api.graphql_url,
        )
        ssm.StringParameter(
            self, "SSM-graphql-api-arn",
            parameter_name=self._ssm_path("graphql-api-arn"),
            string_value=self.graphql_api.arn,
        )

    def _create_appsync_api(self, user_pool: cognito.IUserPool) -> None:
        schema_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "graphql",
            "schema.graphql",
        )

        self.graphql_api = appsync.GraphqlApi(
            self,
            "TimesheetGraphQLApi",
            name=f"{TIMESHEET_API_NAME}-{self.env_name}",
            definition=appsync.Definition.from_file(schema_path),
            authorization_config=appsync.AuthorizationConfig(
                default_authorization=appsync.AuthorizationMode(
                    authorization_type=appsync.AuthorizationType.USER_POOL,
                    user_pool_config=appsync.UserPoolConfig(
                        user_pool=user_pool,
                    ),
                ),
            ),
            log_config=appsync.LogConfig(
                field_log_level=appsync.FieldLogLevel.ERROR,
            ),
            xray_enabled=True,
        )
