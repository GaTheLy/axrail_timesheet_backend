"""
Timesheet Storage Stack

S3 report bucket for the Employee Timesheet Management System.
Exports bucket name and ARN to SSM Parameter Store.
"""

from aws_cdk import Duration, RemovalPolicy, Stack, Tags, aws_s3 as s3, aws_ssm as ssm
from constructs import Construct

from colabs_pipeline_cdk.environment import (
    ENV_CONFIG,
    PROJECT_NAME,
    TIMESHEET_REPORT_BUCKET_PREFIX,
    TIMESHEET_SSM_PREFIX,
)


class TimesheetStorageStack(Stack):
    """CDK Stack for Timesheet S3 storage."""

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
        Tags.of(self).add("Component", "Timesheet-Storage")
        Tags.of(self).add("Environment", env_name)

        removal_policy = (
            RemovalPolicy.DESTROY if env_name == "dev" else RemovalPolicy.RETAIN
        )

        self._create_report_bucket(removal_policy)
        self._export_ssm_params()

    def _ssm_path(self, key: str) -> str:
        return f"{TIMESHEET_SSM_PREFIX}/{self.env_name}/storage/{key}"

    def _export_ssm_params(self) -> None:
        ssm.StringParameter(
            self, "SSM-report-bucket-name",
            parameter_name=self._ssm_path("report-bucket-name"),
            string_value=self.report_bucket.bucket_name,
        )
        ssm.StringParameter(
            self, "SSM-report-bucket-arn",
            parameter_name=self._ssm_path("report-bucket-arn"),
            string_value=self.report_bucket.bucket_arn,
        )

    def _create_report_bucket(self, removal_policy: RemovalPolicy) -> None:
        self.report_bucket = s3.Bucket(
            self,
            "TimesheetReportBucket",
            bucket_name=f"{TIMESHEET_REPORT_BUCKET_PREFIX}-{self.env_name}",
            removal_policy=removal_policy,
            auto_delete_objects=removal_policy == RemovalPolicy.DESTROY,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            cors=[
                s3.CorsRule(
                    allowed_methods=[s3.HttpMethods.GET],
                    allowed_origins=["*"],
                    allowed_headers=["*"],
                    max_age=3600,
                )
            ],
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="TransitionToIA",
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=Duration.days(90),
                        )
                    ],
                ),
                s3.LifecycleRule(
                    id="ExpireAfterOneYear",
                    expiration=Duration.days(365),
                ),
            ],
        )
