"""
Timesheet Lambda Stack

All 15 Lambda functions with permissions, AppSync resolvers,
EventBridge rules, and DynamoDB Stream triggers.

Fully independent — looks up all resources from SSM Parameter Store.
"""

from aws_cdk import (
    Duration,
    Stack,
    Tags,
    aws_appsync as appsync,
    aws_cognito as cognito,
    aws_dynamodb as dynamodb,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_lambda_event_sources as lambda_event_sources,
    aws_s3 as s3,
    aws_ssm as ssm,
)
from constructs import Construct

from colabs_pipeline_cdk.environment import (
    ENV_CONFIG,
    PROJECT_NAME,
    TIMESHEET_ARCHIVAL_SCHEDULE,
    TIMESHEET_DEADLINE_ENFORCEMENT_SCHEDULE,
    TIMESHEET_LAMBDA_MEMORY_MB,
    TIMESHEET_LAMBDA_TIMEOUT_SECONDS,
    TIMESHEET_NOTIFICATION_SCHEDULE,
    TIMESHEET_REPORT_BUCKET_PREFIX,
    TIMESHEET_SES_FROM_EMAIL,
    TIMESHEET_SSM_PREFIX,
    TIMESHEET_TABLE_NAMES,
)


class TimesheetLambdaStack(Stack):
    """CDK Stack for all Timesheet Lambda functions."""

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
        Tags.of(self).add("Component", "Timesheet-Lambda")
        Tags.of(self).add("Environment", env_name)

        # ----------------------------------------------------------
        # Look up all resources from SSM
        # ----------------------------------------------------------
        self._import_resources()

        # ----------------------------------------------------------
        # Create all Lambda functions
        # ----------------------------------------------------------
        self._create_user_management_lambda()
        self._create_department_management_lambda()
        self._create_position_management_lambda()
        self._create_project_management_lambda()
        self._create_period_management_lambda()
        self._create_submission_management_lambda()
        self._create_entry_management_lambda()
        self._create_review_management_lambda()
        self._create_deadline_enforcement_lambda()
        self._create_report_generator_lambda()
        self._create_performance_tracking_lambda()
        self._create_notification_lambda()
        self._create_notification_config_lambda()
        self._create_archival_lambda()
        self._create_main_database_lambda()

    def _ssm_lookup(self, path: str) -> str:
        """Look up an SSM parameter value at deploy time."""
        return ssm.StringParameter.value_for_string_parameter(
            self, f"{TIMESHEET_SSM_PREFIX}/{self.env_name}/{path}",
        )

    def _import_resources(self) -> None:
        """Import all cross-stack resources.

        DynamoDB tables and S3 bucket use deterministic names from environment.py.
        Cognito and AppSync use SSM lookups since their IDs are generated at deploy time.
        """

        # --- DynamoDB tables (deterministic names) ---
        table_keys = [
            "users", "departments", "positions", "projects", "periods",
            "submissions", "entries", "employee_performance",
            "report_distribution_config", "main_database",
        ]
        self._table_names = {}
        self._tables = {}
        for key in table_keys:
            name = f"{TIMESHEET_TABLE_NAMES[key]}-{self.env_name}"
            arn = self.format_arn(
                service="dynamodb", resource="table", resource_name=name,
            )
            self._table_names[key] = name
            self._tables[key] = dynamodb.Table.from_table_arn(
                self, f"Imported-{key}-table", arn,
            )

        # Submissions table with stream (stream ARN from SSM)
        submissions_stream_arn = self._ssm_lookup("dynamodb/submissions/stream-arn")
        self._submissions_with_stream = dynamodb.Table.from_table_attributes(
            self, "Imported-submissions-stream",
            table_arn=self.format_arn(
                service="dynamodb", resource="table",
                resource_name=self._table_names["submissions"],
            ),
            table_stream_arn=submissions_stream_arn,
        )

        # --- Cognito (SSM — IDs are generated at deploy time) ---
        user_pool_id = self._ssm_lookup("auth/user-pool-id")
        user_pool_arn = self._ssm_lookup("auth/user-pool-arn")
        self._user_pool = cognito.UserPool.from_user_pool_arn(
            self, "ImportedUserPool", user_pool_arn,
        )
        self._user_pool_id = user_pool_id
        self._user_pool_arn = user_pool_arn

        # --- S3 (deterministic bucket name) ---
        bucket_name = f"{TIMESHEET_REPORT_BUCKET_PREFIX}-{self.env_name}"
        self._report_bucket = s3.Bucket.from_bucket_name(
            self, "ImportedReportBucket", bucket_name,
        )

        # --- AppSync (SSM — API ID is generated at deploy time) ---
        api_id = self._ssm_lookup("api/graphql-api-id")
        api_arn = self._ssm_lookup("api/graphql-api-arn")
        self._graphql_api = appsync.GraphqlApi.from_graphql_api_attributes(
            self, "ImportedGraphqlApi",
            graphql_api_id=api_id,
            graphql_api_arn=api_arn,
        )

    def _create_user_management_lambda(self) -> None:
        fn = _lambda.Function(
            self,
            "UserManagementLambda",
            function_name=f"TimesheetUserManagement-{self.env_name}",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="users.handler.handler",
            code=_lambda.Code.from_asset("lambdas"),
            timeout=Duration.seconds(TIMESHEET_LAMBDA_TIMEOUT_SECONDS),
            memory_size=TIMESHEET_LAMBDA_MEMORY_MB,
            environment={
                "USERS_TABLE": self._table_names["users"],
                "USER_POOL_ID": self._user_pool_id,
            },
        )
        self._tables["users"].grant_read_write_data(fn)
        fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "cognito-idp:AdminCreateUser",
                    "cognito-idp:AdminDeleteUser",
                    "cognito-idp:AdminAddUserToGroup",
                    "cognito-idp:AdminUpdateUserAttributes",
                ],
                resources=[self._user_pool_arn],
            )
        )
        ds = self._graphql_api.add_lambda_data_source("UserManagementDataSource", fn)
        for field in ["createUser", "updateUser", "deleteUser"]:
            ds.create_resolver(f"Mutation_{field}_Resolver", type_name="Mutation", field_name=field)
        for field in ["getUser", "listUsers"]:
            ds.create_resolver(f"Query_{field}_Resolver", type_name="Query", field_name=field)

    def _create_department_management_lambda(self) -> None:
        fn = _lambda.Function(
            self,
            "DepartmentManagementLambda",
            function_name=f"TimesheetDepartmentManagement-{self.env_name}",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="departments.handler.handler",
            code=_lambda.Code.from_asset("lambdas"),
            timeout=Duration.seconds(TIMESHEET_LAMBDA_TIMEOUT_SECONDS),
            memory_size=TIMESHEET_LAMBDA_MEMORY_MB,
            environment={
                "DEPARTMENTS_TABLE": self._table_names["departments"],
                "USERS_TABLE": self._table_names["users"],
            },
        )
        self._tables["departments"].grant_read_write_data(fn)
        self._tables["users"].grant_read_data(fn)
        ds = self._graphql_api.add_lambda_data_source("DepartmentManagementDataSource", fn)
        for field in ["createDepartment", "updateDepartment", "deleteDepartment"]:
            ds.create_resolver(f"Mutation_{field}_Resolver", type_name="Mutation", field_name=field)
        ds.create_resolver("Query_listDepartments_Resolver", type_name="Query", field_name="listDepartments")

    def _create_position_management_lambda(self) -> None:
        fn = _lambda.Function(
            self,
            "PositionManagementLambda",
            function_name=f"TimesheetPositionManagement-{self.env_name}",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="positions.handler.handler",
            code=_lambda.Code.from_asset("lambdas"),
            timeout=Duration.seconds(TIMESHEET_LAMBDA_TIMEOUT_SECONDS),
            memory_size=TIMESHEET_LAMBDA_MEMORY_MB,
            environment={
                "POSITIONS_TABLE": self._table_names["positions"],
            },
        )
        self._tables["positions"].grant_read_write_data(fn)
        ds = self._graphql_api.add_lambda_data_source("PositionManagementDataSource", fn)
        for field in ["createPosition", "updatePosition", "deletePosition"]:
            ds.create_resolver(f"Mutation_{field}_Resolver", type_name="Mutation", field_name=field)
        ds.create_resolver("Query_listPositions_Resolver", type_name="Query", field_name="listPositions")

    def _create_project_management_lambda(self) -> None:
        fn = _lambda.Function(
            self,
            "ProjectManagementLambda",
            function_name=f"TimesheetProjectManagement-{self.env_name}",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="projects.handler.handler",
            code=_lambda.Code.from_asset("lambdas"),
            timeout=Duration.seconds(TIMESHEET_LAMBDA_TIMEOUT_SECONDS),
            memory_size=TIMESHEET_LAMBDA_MEMORY_MB,
            environment={
                "PROJECTS_TABLE": self._table_names["projects"],
            },
        )
        self._tables["projects"].grant_read_write_data(fn)
        ds = self._graphql_api.add_lambda_data_source("ProjectManagementDataSource", fn)
        for field in ["createProject", "approveProject", "rejectProject", "updateProject"]:
            ds.create_resolver(f"Mutation_{field}_Resolver", type_name="Mutation", field_name=field)
        ds.create_resolver("Query_listProjects_Resolver", type_name="Query", field_name="listProjects")

    def _create_period_management_lambda(self) -> None:
        fn = _lambda.Function(
            self,
            "PeriodManagementLambda",
            function_name=f"TimesheetPeriodManagement-{self.env_name}",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="periods.handler.handler",
            code=_lambda.Code.from_asset("lambdas"),
            timeout=Duration.seconds(TIMESHEET_LAMBDA_TIMEOUT_SECONDS),
            memory_size=TIMESHEET_LAMBDA_MEMORY_MB,
            environment={
                "PERIODS_TABLE": self._table_names["periods"],
            },
        )
        self._tables["periods"].grant_read_write_data(fn)
        ds = self._graphql_api.add_lambda_data_source("PeriodManagementDataSource", fn)
        for field in ["createTimesheetPeriod", "updateTimesheetPeriod"]:
            ds.create_resolver(f"Mutation_{field}_Resolver", type_name="Mutation", field_name=field)
        for field in ["listTimesheetPeriods", "getCurrentPeriod"]:
            ds.create_resolver(f"Query_{field}_Resolver", type_name="Query", field_name=field)

    def _create_submission_management_lambda(self) -> None:
        fn = _lambda.Function(
            self,
            "SubmissionManagementLambda",
            function_name=f"TimesheetSubmissionManagement-{self.env_name}",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="submissions.handler.handler",
            code=_lambda.Code.from_asset("lambdas"),
            timeout=Duration.seconds(TIMESHEET_LAMBDA_TIMEOUT_SECONDS),
            memory_size=TIMESHEET_LAMBDA_MEMORY_MB,
            environment={
                "SUBMISSIONS_TABLE": self._table_names["submissions"],
                "ENTRIES_TABLE": self._table_names["entries"],
            },
        )
        self._tables["submissions"].grant_read_write_data(fn)
        self._tables["entries"].grant_read_data(fn)
        ds = self._graphql_api.add_lambda_data_source("SubmissionManagementDataSource", fn)
        for field in ["createTimesheetSubmission", "submitTimesheet"]:
            ds.create_resolver(f"Mutation_{field}_Resolver", type_name="Mutation", field_name=field)
        for field in ["getTimesheetSubmission", "listMySubmissions"]:
            ds.create_resolver(f"Query_{field}_Resolver", type_name="Query", field_name=field)

    def _create_entry_management_lambda(self) -> None:
        fn = _lambda.Function(
            self,
            "EntryManagementLambda",
            function_name=f"TimesheetEntryManagement-{self.env_name}",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="entries.handler.handler",
            code=_lambda.Code.from_asset("lambdas"),
            timeout=Duration.seconds(TIMESHEET_LAMBDA_TIMEOUT_SECONDS),
            memory_size=TIMESHEET_LAMBDA_MEMORY_MB,
            environment={
                "ENTRIES_TABLE": self._table_names["entries"],
                "SUBMISSIONS_TABLE": self._table_names["submissions"],
                "PROJECTS_TABLE": self._table_names["projects"],
            },
        )
        self._tables["entries"].grant_read_write_data(fn)
        self._tables["submissions"].grant_read_data(fn)
        self._tables["projects"].grant_read_data(fn)
        ds = self._graphql_api.add_lambda_data_source("EntryManagementDataSource", fn)
        for field in ["addTimesheetEntry", "updateTimesheetEntry", "removeTimesheetEntry"]:
            ds.create_resolver(f"Mutation_{field}_Resolver", type_name="Mutation", field_name=field)

    def _create_review_management_lambda(self) -> None:
        fn = _lambda.Function(
            self,
            "ReviewManagementLambda",
            function_name=f"TimesheetReviewManagement-{self.env_name}",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="reviews.handler.handler",
            code=_lambda.Code.from_asset("lambdas"),
            timeout=Duration.seconds(TIMESHEET_LAMBDA_TIMEOUT_SECONDS),
            memory_size=TIMESHEET_LAMBDA_MEMORY_MB,
            environment={
                "SUBMISSIONS_TABLE": self._table_names["submissions"],
                "USERS_TABLE": self._table_names["users"],
            },
        )
        self._tables["submissions"].grant_read_write_data(fn)
        self._tables["users"].grant_read_data(fn)
        ds = self._graphql_api.add_lambda_data_source("ReviewManagementDataSource", fn)
        for field in ["approveTimesheet", "rejectTimesheet"]:
            ds.create_resolver(f"Mutation_{field}_Resolver", type_name="Mutation", field_name=field)
        ds.create_resolver("Query_listPendingTimesheets_Resolver", type_name="Query", field_name="listPendingTimesheets")

    def _create_deadline_enforcement_lambda(self) -> None:
        fn = _lambda.Function(
            self,
            "DeadlineEnforcementLambda",
            function_name=f"TimesheetDeadlineEnforcement-{self.env_name}",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="deadline_enforcement.handler.handler",
            code=_lambda.Code.from_asset("lambdas"),
            timeout=Duration.seconds(TIMESHEET_LAMBDA_TIMEOUT_SECONDS),
            memory_size=TIMESHEET_LAMBDA_MEMORY_MB,
            environment={
                "PERIODS_TABLE": self._table_names["periods"],
                "SUBMISSIONS_TABLE": self._table_names["submissions"],
                "USERS_TABLE": self._table_names["users"],
            },
        )
        self._tables["periods"].grant_read_write_data(fn)
        self._tables["submissions"].grant_read_write_data(fn)
        self._tables["users"].grant_read_data(fn)
        rule = events.Rule(
            self,
            "DeadlineEnforcementRule",
            rule_name=f"TimesheetDeadlineEnforcement-{self.env_name}",
            schedule=events.Schedule.expression(TIMESHEET_DEADLINE_ENFORCEMENT_SCHEDULE),
            description="Triggers deadline enforcement Lambda to lock expired timesheet periods",
        )
        rule.add_target(targets.LambdaFunction(fn))

    def _create_report_generator_lambda(self) -> None:
        fn = _lambda.Function(
            self,
            "ReportGeneratorLambda",
            function_name=f"TimesheetReportGenerator-{self.env_name}",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="reports.handler.handler",
            code=_lambda.Code.from_asset("lambdas"),
            timeout=Duration.seconds(TIMESHEET_LAMBDA_TIMEOUT_SECONDS),
            memory_size=TIMESHEET_LAMBDA_MEMORY_MB,
            environment={
                "SUBMISSIONS_TABLE": self._table_names["submissions"],
                "ENTRIES_TABLE": self._table_names["entries"],
                "USERS_TABLE": self._table_names["users"],
                "PROJECTS_TABLE": self._table_names["projects"],
                "EMPLOYEE_PERFORMANCE_TABLE": self._table_names["employee_performance"],
                "PERIODS_TABLE": self._table_names["periods"],
                "REPORT_BUCKET": self._report_bucket.bucket_name,
            },
        )
        self._tables["submissions"].grant_read_data(fn)
        self._tables["entries"].grant_read_data(fn)
        self._tables["users"].grant_read_data(fn)
        self._tables["projects"].grant_read_data(fn)
        self._tables["employee_performance"].grant_read_data(fn)
        self._tables["periods"].grant_read_data(fn)
        self._report_bucket.grant_read_write(fn)
        fn.add_event_source(
            lambda_event_sources.DynamoEventSource(
                self._submissions_with_stream,
                starting_position=_lambda.StartingPosition.TRIM_HORIZON,
                batch_size=10,
                retry_attempts=3,
            )
        )
        ds = self._graphql_api.add_lambda_data_source("ReportGeneratorDataSource", fn)
        ds.create_resolver("Query_getTCSummaryReport_Resolver", type_name="Query", field_name="getTCSummaryReport")
        ds.create_resolver("Query_getProjectSummaryReport_Resolver", type_name="Query", field_name="getProjectSummaryReport")

    def _create_performance_tracking_lambda(self) -> None:
        fn = _lambda.Function(
            self,
            "PerformanceTrackingLambda",
            function_name=f"TimesheetPerformanceTracking-{self.env_name}",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="performance.handler.handler",
            code=_lambda.Code.from_asset("lambdas"),
            timeout=Duration.seconds(TIMESHEET_LAMBDA_TIMEOUT_SECONDS),
            memory_size=TIMESHEET_LAMBDA_MEMORY_MB,
            environment={
                "EMPLOYEE_PERFORMANCE_TABLE": self._table_names["employee_performance"],
            },
        )
        self._tables["employee_performance"].grant_read_write_data(fn)
        fn.add_event_source(
            lambda_event_sources.DynamoEventSource(
                self._submissions_with_stream,
                starting_position=_lambda.StartingPosition.TRIM_HORIZON,
                batch_size=10,
                retry_attempts=3,
            )
        )

    def _create_notification_lambda(self) -> None:
        fn = _lambda.Function(
            self,
            "NotificationLambda",
            function_name=f"TimesheetNotification-{self.env_name}",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="notifications.handler.handler",
            code=_lambda.Code.from_asset("lambdas"),
            timeout=Duration.seconds(300),
            memory_size=TIMESHEET_LAMBDA_MEMORY_MB,
            environment={
                "SUBMISSIONS_TABLE": self._table_names["submissions"],
                "ENTRIES_TABLE": self._table_names["entries"],
                "USERS_TABLE": self._table_names["users"],
                "PROJECTS_TABLE": self._table_names["projects"],
                "EMPLOYEE_PERFORMANCE_TABLE": self._table_names["employee_performance"],
                "PERIODS_TABLE": self._table_names["periods"],
                "REPORT_DISTRIBUTION_CONFIG_TABLE": self._table_names["report_distribution_config"],
                "REPORT_BUCKET": self._report_bucket.bucket_name,
                "SES_FROM_EMAIL": TIMESHEET_SES_FROM_EMAIL,
            },
        )
        self._tables["submissions"].grant_read_data(fn)
        self._tables["entries"].grant_read_data(fn)
        self._tables["users"].grant_read_data(fn)
        self._tables["projects"].grant_read_data(fn)
        self._tables["employee_performance"].grant_read_data(fn)
        self._tables["periods"].grant_read_data(fn)
        self._tables["report_distribution_config"].grant_read_data(fn)
        self._report_bucket.grant_read_write(fn)
        fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ses:SendEmail", "ses:SendRawEmail"],
                resources=["*"],
            )
        )
        rule = events.Rule(
            self,
            "NotificationScheduleRule",
            rule_name=f"TimesheetNotification-{self.env_name}",
            schedule=events.Schedule.expression(TIMESHEET_NOTIFICATION_SCHEDULE),
            description="Triggers notification Lambda to generate and email timesheet reports",
        )
        rule.add_target(targets.LambdaFunction(fn))

    def _create_notification_config_lambda(self) -> None:
        fn = _lambda.Function(
            self,
            "NotificationConfigLambda",
            function_name=f"TimesheetNotificationConfig-{self.env_name}",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="notification_config.handler.handler",
            code=_lambda.Code.from_asset("lambdas"),
            timeout=Duration.seconds(TIMESHEET_LAMBDA_TIMEOUT_SECONDS),
            memory_size=TIMESHEET_LAMBDA_MEMORY_MB,
            environment={
                "REPORT_DISTRIBUTION_CONFIG_TABLE": self._table_names["report_distribution_config"],
            },
        )
        self._tables["report_distribution_config"].grant_read_write_data(fn)
        ds = self._graphql_api.add_lambda_data_source("NotificationConfigDataSource", fn)
        ds.create_resolver("Mutation_updateReportDistributionConfig_Resolver", type_name="Mutation", field_name="updateReportDistributionConfig")
        ds.create_resolver("Query_getReportDistributionConfig_Resolver", type_name="Query", field_name="getReportDistributionConfig")

    def _create_archival_lambda(self) -> None:
        fn = _lambda.Function(
            self,
            "ArchivalLambda",
            function_name=f"TimesheetArchival-{self.env_name}",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="archival.handler.handler",
            code=_lambda.Code.from_asset("lambdas"),
            timeout=Duration.seconds(TIMESHEET_LAMBDA_TIMEOUT_SECONDS),
            memory_size=TIMESHEET_LAMBDA_MEMORY_MB,
            environment={
                "SUBMISSIONS_TABLE": self._table_names["submissions"],
                "PERIODS_TABLE": self._table_names["periods"],
            },
        )
        self._tables["submissions"].grant_read_write_data(fn)
        self._tables["periods"].grant_read_data(fn)
        rule = events.Rule(
            self,
            "ArchivalScheduleRule",
            rule_name=f"TimesheetArchival-{self.env_name}",
            schedule=events.Schedule.expression(TIMESHEET_ARCHIVAL_SCHEDULE),
            description="Triggers archival Lambda to archive submissions for ended biweekly periods",
        )
        rule.add_target(targets.LambdaFunction(fn))

    def _create_main_database_lambda(self) -> None:
        fn = _lambda.Function(
            self,
            "MainDatabaseLambda",
            function_name=f"TimesheetMainDatabase-{self.env_name}",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="main_database.handler.handler",
            code=_lambda.Code.from_asset("lambdas"),
            timeout=Duration.seconds(TIMESHEET_LAMBDA_TIMEOUT_SECONDS),
            memory_size=TIMESHEET_LAMBDA_MEMORY_MB,
            environment={
                "MAIN_DATABASE_TABLE": self._table_names["main_database"],
                "REPORT_BUCKET": self._report_bucket.bucket_name,
            },
        )
        self._tables["main_database"].grant_read_write_data(fn)
        self._report_bucket.grant_read(fn)
        ds = self._graphql_api.add_lambda_data_source("MainDatabaseDataSource", fn)
        ds.create_resolver("Query_listMainDatabase_Resolver", type_name="Query", field_name="listMainDatabase")
        for field in ["updateMainDatabaseRecord", "bulkImportCSV", "refreshDatabase"]:
            ds.create_resolver(f"Mutation_{field}_Resolver", type_name="Mutation", field_name=field)
