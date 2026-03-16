"""
Timesheet Auth Stack

Cognito User Pool, groups, and client for the Employee Timesheet Management System.
Exports User Pool ID and ARN to SSM Parameter Store.
"""

from aws_cdk import Duration, RemovalPolicy, Stack, Tags, aws_cognito as cognito, aws_ssm as ssm
from constructs import Construct

from colabs_pipeline_cdk.environment import (
    ENV_CONFIG,
    PROJECT_NAME,
    TIMESHEET_COGNITO_GROUPS,
    TIMESHEET_SSM_PREFIX,
    TIMESHEET_USER_POOL_NAME,
)


class TimesheetAuthStack(Stack):
    """CDK Stack for Timesheet Cognito authentication."""

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
        Tags.of(self).add("Component", "Timesheet-Auth")
        Tags.of(self).add("Environment", env_name)

        removal_policy = (
            RemovalPolicy.DESTROY if env_name == "dev" else RemovalPolicy.RETAIN
        )

        self._create_cognito_user_pool(removal_policy)
        self._export_ssm_params()

    def _ssm_path(self, key: str) -> str:
        return f"{TIMESHEET_SSM_PREFIX}/{self.env_name}/auth/{key}"

    def _export_ssm_params(self) -> None:
        ssm.StringParameter(
            self, "SSM-user-pool-id",
            parameter_name=self._ssm_path("user-pool-id"),
            string_value=self.user_pool.user_pool_id,
        )
        ssm.StringParameter(
            self, "SSM-user-pool-arn",
            parameter_name=self._ssm_path("user-pool-arn"),
            string_value=self.user_pool.user_pool_arn,
        )

    def _create_cognito_user_pool(self, removal_policy: RemovalPolicy) -> None:
        self.user_pool = cognito.UserPool(
            self,
            "TimesheetUserPool",
            user_pool_name=f"{TIMESHEET_USER_POOL_NAME}-{self.env_name}",
            removal_policy=removal_policy,
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(email=True),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_uppercase=True,
                require_lowercase=True,
                require_digits=True,
                require_symbols=True,
                temp_password_validity=Duration.days(7),
            ),
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=True),
                fullname=cognito.StandardAttribute(required=True, mutable=True),
            ),
            custom_attributes={
                "userType": cognito.StringAttribute(
                    min_len=1, max_len=20, mutable=True
                ),
                "role": cognito.StringAttribute(
                    min_len=1, max_len=30, mutable=True
                ),
                "departmentId": cognito.StringAttribute(
                    min_len=0, max_len=36, mutable=True
                ),
                "positionId": cognito.StringAttribute(
                    min_len=0, max_len=36, mutable=True
                ),
            },
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
        )

        for group_name in TIMESHEET_COGNITO_GROUPS:
            cognito.CfnUserPoolGroup(
                self,
                f"CognitoGroup-{group_name}",
                user_pool_id=self.user_pool.user_pool_id,
                group_name=group_name,
                description=f"{group_name} group for timesheet system",
            )

        self.user_pool_client = self.user_pool.add_client(
            "TimesheetUserPoolClient",
            user_pool_client_name=f"TimesheetWebClient-{self.env_name}",
            auth_flows=cognito.AuthFlow(
                user_password=True,
                user_srp=True,
            ),
            generate_secret=False,
            access_token_validity=Duration.hours(1),
            id_token_validity=Duration.hours(1),
            refresh_token_validity=Duration.days(30),
            prevent_user_existence_errors=True,
        )
