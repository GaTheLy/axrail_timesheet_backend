"""
Timesheet Lambda Stack

All Lambda functions with permissions, AppSync resolvers,
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
    TIMESHEET_AUTO_PROVISIONING_SCHEDULE,
    TIMESHEET_DEADLINE_ENFORCEMENT_SCHEDULE,
    TIMESHEET_DEADLINE_REMINDER_SCHEDULE,
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
        self._create_user_lambdas()
        self._create_department_lambdas()
        self._create_position_lambdas()
        self._create_project_lambdas()
        self._create_period_lambdas()
        self._create_submission_lambdas()
        self._create_entry_lambdas()
        self._create_deadline_enforcement_lambda()
        self._create_auto_provisioning_lambda()
        self._create_deadline_reminder_lambda()
        self._create_report_lambdas()
        self._create_performance_tracking_lambda()
        self._create_notification_lambda()
        self._create_notification_config_lambdas()
        self._create_archival_lambda()
        self._create_main_database_lambdas()
        self._create_sync_from_projects_lambda()
        self._create_project_assignment_lambdas()

    def _ssm_lookup(self, path: str) -> str:
        return ssm.StringParameter.value_for_string_parameter(
            self, f"{TIMESHEET_SSM_PREFIX}/{self.env_name}/{path}",
        )

    def _import_resources(self) -> None:
        table_keys = [
            "users", "departments", "positions", "projects", "periods",
            "submissions", "entries", "employee_performance",
            "report_distribution_config", "main_database",
            "project_assignments",
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

        submissions_stream_arn = self._ssm_lookup("dynamodb/submissions/stream-arn")
        self._submissions_with_stream = dynamodb.Table.from_table_attributes(
            self, "Imported-submissions-stream",
            table_arn=self.format_arn(
                service="dynamodb", resource="table",
                resource_name=self._table_names["submissions"],
            ),
            table_stream_arn=submissions_stream_arn,
        )

        projects_stream_arn = self._ssm_lookup("dynamodb/projects/stream-arn")
        self._projects_with_stream = dynamodb.Table.from_table_attributes(
            self, "Imported-projects-stream",
            table_arn=self.format_arn(
                service="dynamodb", resource="table",
                resource_name=self._table_names["projects"],
            ),
            table_stream_arn=projects_stream_arn,
        )

        user_pool_id = self._ssm_lookup("auth/user-pool-id")
        user_pool_arn = self._ssm_lookup("auth/user-pool-arn")
        self._user_pool = cognito.UserPool.from_user_pool_arn(
            self, "ImportedUserPool", user_pool_arn,
        )
        self._user_pool_id = user_pool_id
        self._user_pool_arn = user_pool_arn

        bucket_name = f"{TIMESHEET_REPORT_BUCKET_PREFIX}-{self.env_name}"
        self._report_bucket = s3.Bucket.from_bucket_name(
            self, "ImportedReportBucket", bucket_name,
        )

        api_id = self._ssm_lookup("api/graphql-api-id")
        api_arn = self._ssm_lookup("api/graphql-api-arn")
        self._graphql_api = appsync.GraphqlApi.from_graphql_api_attributes(
            self, "ImportedGraphqlApi",
            graphql_api_id=api_id,
            graphql_api_arn=api_arn,
        )

    def _make_lambda(self, construct_id, function_name, handler_path, environment, timeout=None):
        """Helper to create a Lambda function with standard settings."""
        fn = _lambda.Function(
            self,
            construct_id,
            function_name=f"{function_name}-{self.env_name}",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler=handler_path,
            code=_lambda.Code.from_asset(
                "lambdas",
                exclude=["__pycache__", "*.pyc", ".pytest_cache", ".hypothesis"],
            ),
            timeout=Duration.seconds(timeout or TIMESHEET_LAMBDA_TIMEOUT_SECONDS),
            memory_size=TIMESHEET_LAMBDA_MEMORY_MB,
            environment=environment,
        )
        # Grant access to all DynamoDB GSIs referenced in environment tables
        index_arns = []
        for table_key in environment:
            if table_key in self._tables:
                index_arns.append(f"{self._tables[table_key].table_arn}/index/*")
            # Match by table name value
            for key, name in self._table_names.items():
                if environment[table_key] == name and key in self._tables:
                    index_arns.append(f"{self._tables[key].table_arn}/index/*")
        if index_arns:
            fn.add_to_role_policy(iam.PolicyStatement(
                actions=["dynamodb:Query"],
                resources=list(set(index_arns)),
            ))
        return fn

    # ------------------------------------------------------------------
    # User Management (5 Lambdas)
    # ------------------------------------------------------------------
    def _create_user_lambdas(self) -> None:
        user_env = {
            "USERS_TABLE": self._table_names["users"],
            "USER_POOL_ID": self._user_pool_id,
        }
        cognito_policy = iam.PolicyStatement(
            actions=[
                "cognito-idp:AdminCreateUser",
                "cognito-idp:AdminDeleteUser",
                "cognito-idp:AdminAddUserToGroup",
                "cognito-idp:AdminUpdateUserAttributes",
                "cognito-idp:AdminEnableUser",
                "cognito-idp:AdminDisableUser",
            ],
            resources=[self._user_pool_arn],
        )

        # CreateUser
        fn = self._make_lambda("CreateUserLambda", "TimesheetCreateUser",
                               "users.CreateUser.handler.handler", user_env)
        self._tables["users"].grant_read_write_data(fn)
        fn.add_to_role_policy(cognito_policy)
        ds = self._graphql_api.add_lambda_data_source("CreateUserDataSource", fn)
        ds.create_resolver("Mutation_createUser_Resolver", type_name="Mutation", field_name="createUser")

        # UpdateUser
        fn = self._make_lambda("UpdateUserLambda", "TimesheetUpdateUser",
                               "users.UpdateUser.handler.handler", user_env)
        self._tables["users"].grant_read_write_data(fn)
        fn.add_to_role_policy(cognito_policy)
        ds = self._graphql_api.add_lambda_data_source("UpdateUserDataSource", fn)
        ds.create_resolver("Mutation_updateUser_Resolver", type_name="Mutation", field_name="updateUser")

        # ApproveUser
        fn = self._make_lambda("ApproveUserLambda", "TimesheetApproveUser",
                               "users.ApproveUser.handler.handler",
                               {"USERS_TABLE": self._table_names["users"]})
        self._tables["users"].grant_read_write_data(fn)
        ds = self._graphql_api.add_lambda_data_source("ApproveUserDataSource", fn)
        ds.create_resolver("Mutation_approveUser_Resolver", type_name="Mutation", field_name="approveUser")

        # RejectUser
        fn = self._make_lambda("RejectUserLambda", "TimesheetRejectUser",
                               "users.RejectUser.handler.handler",
                               {"USERS_TABLE": self._table_names["users"]})
        self._tables["users"].grant_read_write_data(fn)
        ds = self._graphql_api.add_lambda_data_source("RejectUserDataSource", fn)
        ds.create_resolver("Mutation_rejectUser_Resolver", type_name="Mutation", field_name="rejectUser")

        # DeleteUser
        fn = self._make_lambda("DeleteUserLambda", "TimesheetDeleteUser",
                               "users.DeleteUser.handler.handler", user_env)
        self._tables["users"].grant_read_write_data(fn)
        fn.add_to_role_policy(cognito_policy)
        ds = self._graphql_api.add_lambda_data_source("DeleteUserDataSource", fn)
        ds.create_resolver("Mutation_deleteUser_Resolver", type_name="Mutation", field_name="deleteUser")

        # GetUser
        fn = self._make_lambda("GetUserLambda", "TimesheetGetUser",
                               "users.GetUser.handler.handler", {"USERS_TABLE": self._table_names["users"]})
        self._tables["users"].grant_read_data(fn)
        ds = self._graphql_api.add_lambda_data_source("GetUserDataSource", fn)
        ds.create_resolver("Query_getUser_Resolver", type_name="Query", field_name="getUser")

        # ListUsers
        fn = self._make_lambda("ListUsersLambda", "TimesheetListUsers",
                               "users.ListUsers.handler.handler", {"USERS_TABLE": self._table_names["users"]})
        self._tables["users"].grant_read_data(fn)
        ds = self._graphql_api.add_lambda_data_source("ListUsersDataSource", fn)
        ds.create_resolver("Query_listUsers_Resolver", type_name="Query", field_name="listUsers")

        # DeactivateUser
        fn = self._make_lambda("DeactivateUserLambda", "TimesheetDeactivateUser",
                               "users.DeactivateUser.handler.handler", user_env)
        self._tables["users"].grant_read_write_data(fn)
        fn.add_to_role_policy(cognito_policy)
        ds = self._graphql_api.add_lambda_data_source("DeactivateUserDataSource", fn)
        ds.create_resolver("Mutation_deactivateUser_Resolver", type_name="Mutation", field_name="deactivateUser")

        # ActivateUser
        fn = self._make_lambda("ActivateUserLambda", "TimesheetActivateUser",
                               "users.ActivateUser.handler.handler", user_env)
        self._tables["users"].grant_read_write_data(fn)
        fn.add_to_role_policy(cognito_policy)
        ds = self._graphql_api.add_lambda_data_source("ActivateUserDataSource", fn)
        ds.create_resolver("Mutation_activateUser_Resolver", type_name="Mutation", field_name="activateUser")

    # ------------------------------------------------------------------
    # Department Management (4 Lambdas)
    # ------------------------------------------------------------------
    def _create_department_lambdas(self) -> None:
        dept_env = {
            "DEPARTMENTS_TABLE": self._table_names["departments"],
            "USERS_TABLE": self._table_names["users"],
        }

        # CreateDepartment
        fn = self._make_lambda("CreateDepartmentLambda", "TimesheetCreateDepartment",
                               "departments.CreateDepartment.handler.handler", dept_env)
        self._tables["departments"].grant_read_write_data(fn)
        ds = self._graphql_api.add_lambda_data_source("CreateDepartmentDataSource", fn)
        ds.create_resolver("Mutation_createDepartment_Resolver", type_name="Mutation", field_name="createDepartment")

        # ApproveDepartment
        fn = self._make_lambda("ApproveDepartmentLambda", "TimesheetApproveDepartment",
                               "departments.ApproveDepartment.handler.handler",
                               {"DEPARTMENTS_TABLE": self._table_names["departments"]})
        self._tables["departments"].grant_read_write_data(fn)
        ds = self._graphql_api.add_lambda_data_source("ApproveDepartmentDataSource", fn)
        ds.create_resolver("Mutation_approveDepartment_Resolver", type_name="Mutation", field_name="approveDepartment")

        # RejectDepartment
        fn = self._make_lambda("RejectDepartmentLambda", "TimesheetRejectDepartment",
                               "departments.RejectDepartment.handler.handler",
                               {"DEPARTMENTS_TABLE": self._table_names["departments"]})
        self._tables["departments"].grant_read_write_data(fn)
        ds = self._graphql_api.add_lambda_data_source("RejectDepartmentDataSource", fn)
        ds.create_resolver("Mutation_rejectDepartment_Resolver", type_name="Mutation", field_name="rejectDepartment")

        # UpdateDepartment
        fn = self._make_lambda("UpdateDepartmentLambda", "TimesheetUpdateDepartment",
                               "departments.UpdateDepartment.handler.handler",
                               {"DEPARTMENTS_TABLE": self._table_names["departments"]})
        self._tables["departments"].grant_read_write_data(fn)
        ds = self._graphql_api.add_lambda_data_source("UpdateDepartmentDataSource", fn)
        ds.create_resolver("Mutation_updateDepartment_Resolver", type_name="Mutation", field_name="updateDepartment")

        # DeleteDepartment
        fn = self._make_lambda("DeleteDepartmentLambda", "TimesheetDeleteDepartment",
                               "departments.DeleteDepartment.handler.handler", dept_env)
        self._tables["departments"].grant_read_write_data(fn)
        self._tables["users"].grant_read_data(fn)
        ds = self._graphql_api.add_lambda_data_source("DeleteDepartmentDataSource", fn)
        ds.create_resolver("Mutation_deleteDepartment_Resolver", type_name="Mutation", field_name="deleteDepartment")

        # ListDepartments
        fn = self._make_lambda("ListDepartmentsLambda", "TimesheetListDepartments",
                               "departments.ListDepartments.handler.handler",
                               {"DEPARTMENTS_TABLE": self._table_names["departments"]})
        self._tables["departments"].grant_read_data(fn)
        ds = self._graphql_api.add_lambda_data_source("ListDepartmentsDataSource", fn)
        ds.create_resolver("Query_listDepartments_Resolver", type_name="Query", field_name="listDepartments")

    # ------------------------------------------------------------------
    # Position Management (4 Lambdas)
    # ------------------------------------------------------------------
    def _create_position_lambdas(self) -> None:
        pos_env = {"POSITIONS_TABLE": self._table_names["positions"]}

        # CreatePosition
        fn = self._make_lambda("CreatePositionLambda", "TimesheetCreatePosition",
                               "positions.CreatePosition.handler.handler", pos_env)
        self._tables["positions"].grant_read_write_data(fn)
        ds = self._graphql_api.add_lambda_data_source("CreatePositionDataSource", fn)
        ds.create_resolver("Mutation_createPosition_Resolver", type_name="Mutation", field_name="createPosition")

        # UpdatePosition
        fn = self._make_lambda("UpdatePositionLambda", "TimesheetUpdatePosition",
                               "positions.UpdatePosition.handler.handler", pos_env)
        self._tables["positions"].grant_read_write_data(fn)
        ds = self._graphql_api.add_lambda_data_source("UpdatePositionDataSource", fn)
        ds.create_resolver("Mutation_updatePosition_Resolver", type_name="Mutation", field_name="updatePosition")

        # ApprovePosition
        fn = self._make_lambda("ApprovePositionLambda", "TimesheetApprovePosition",
                               "positions.ApprovePosition.handler.handler",
                               {"POSITIONS_TABLE": self._table_names["positions"]})
        self._tables["positions"].grant_read_write_data(fn)
        ds = self._graphql_api.add_lambda_data_source("ApprovePositionDataSource", fn)
        ds.create_resolver("Mutation_approvePosition_Resolver", type_name="Mutation", field_name="approvePosition")

        # RejectPosition
        fn = self._make_lambda("RejectPositionLambda", "TimesheetRejectPosition",
                               "positions.RejectPosition.handler.handler",
                               {"POSITIONS_TABLE": self._table_names["positions"]})
        self._tables["positions"].grant_read_write_data(fn)
        ds = self._graphql_api.add_lambda_data_source("RejectPositionDataSource", fn)
        ds.create_resolver("Mutation_rejectPosition_Resolver", type_name="Mutation", field_name="rejectPosition")

        # DeletePosition
        fn = self._make_lambda("DeletePositionLambda", "TimesheetDeletePosition",
                               "positions.DeletePosition.handler.handler", pos_env)
        self._tables["positions"].grant_read_write_data(fn)
        ds = self._graphql_api.add_lambda_data_source("DeletePositionDataSource", fn)
        ds.create_resolver("Mutation_deletePosition_Resolver", type_name="Mutation", field_name="deletePosition")

        # ListPositions
        fn = self._make_lambda("ListPositionsLambda", "TimesheetListPositions",
                               "positions.ListPositions.handler.handler", pos_env)
        self._tables["positions"].grant_read_data(fn)
        ds = self._graphql_api.add_lambda_data_source("ListPositionsDataSource", fn)
        ds.create_resolver("Query_listPositions_Resolver", type_name="Query", field_name="listPositions")

    # ------------------------------------------------------------------
    # Project Management (5 Lambdas)
    # ------------------------------------------------------------------
    def _create_project_lambdas(self) -> None:
        proj_env = {"PROJECTS_TABLE": self._table_names["projects"]}

        # CreateProject
        fn = self._make_lambda("CreateProjectLambda", "TimesheetCreateProject",
                               "projects.CreateProject.handler.handler", proj_env)
        self._tables["projects"].grant_read_write_data(fn)
        ds = self._graphql_api.add_lambda_data_source("CreateProjectDataSource", fn)
        ds.create_resolver("Mutation_createProject_Resolver", type_name="Mutation", field_name="createProject")

        # ApproveProject
        fn = self._make_lambda("ApproveProjectLambda", "TimesheetApproveProject",
                               "projects.ApproveProject.handler.handler", proj_env)
        self._tables["projects"].grant_read_write_data(fn)
        ds = self._graphql_api.add_lambda_data_source("ApproveProjectDataSource", fn)
        ds.create_resolver("Mutation_approveProject_Resolver", type_name="Mutation", field_name="approveProject")

        # RejectProject
        fn = self._make_lambda("RejectProjectLambda", "TimesheetRejectProject",
                               "projects.RejectProject.handler.handler", proj_env)
        self._tables["projects"].grant_read_write_data(fn)
        ds = self._graphql_api.add_lambda_data_source("RejectProjectDataSource", fn)
        ds.create_resolver("Mutation_rejectProject_Resolver", type_name="Mutation", field_name="rejectProject")

        # UpdateProject
        fn = self._make_lambda("UpdateProjectLambda", "TimesheetUpdateProject",
                               "projects.UpdateProject.handler.handler", proj_env)
        self._tables["projects"].grant_read_write_data(fn)
        ds = self._graphql_api.add_lambda_data_source("UpdateProjectDataSource", fn)
        ds.create_resolver("Mutation_updateProject_Resolver", type_name="Mutation", field_name="updateProject")

        # DeleteProject
        fn = self._make_lambda("DeleteProjectLambda", "TimesheetDeleteProject",
                               "projects.DeleteProject.handler.handler",
                               {"PROJECTS_TABLE": self._table_names["projects"]})
        self._tables["projects"].grant_read_write_data(fn)
        ds = self._graphql_api.add_lambda_data_source("DeleteProjectDataSource", fn)
        ds.create_resolver("Mutation_deleteProject_Resolver", type_name="Mutation", field_name="deleteProject")

        # ListProjects
        fn = self._make_lambda("ListProjectsLambda", "TimesheetListProjects",
                               "projects.ListProjects.handler.handler", proj_env)
        self._tables["projects"].grant_read_data(fn)
        ds = self._graphql_api.add_lambda_data_source("ListProjectsDataSource", fn)
        ds.create_resolver("Query_listProjects_Resolver", type_name="Query", field_name="listProjects")

    # ------------------------------------------------------------------
    # Period Management (4 Lambdas)
    # ------------------------------------------------------------------
    def _create_period_lambdas(self) -> None:
        period_env = {"PERIODS_TABLE": self._table_names["periods"]}

        # CreateTimesheetPeriod
        fn = self._make_lambda("CreateTimesheetPeriodLambda", "TimesheetCreatePeriod",
                               "periods.CreateTimesheetPeriod.handler.handler", period_env)
        self._tables["periods"].grant_read_write_data(fn)
        ds = self._graphql_api.add_lambda_data_source("CreatePeriodDataSource", fn)
        ds.create_resolver("Mutation_createTimesheetPeriod_Resolver", type_name="Mutation", field_name="createTimesheetPeriod")

        # UpdateTimesheetPeriod
        fn = self._make_lambda("UpdateTimesheetPeriodLambda", "TimesheetUpdatePeriod",
                               "periods.UpdateTimesheetPeriod.handler.handler", period_env)
        self._tables["periods"].grant_read_write_data(fn)
        ds = self._graphql_api.add_lambda_data_source("UpdatePeriodDataSource", fn)
        ds.create_resolver("Mutation_updateTimesheetPeriod_Resolver", type_name="Mutation", field_name="updateTimesheetPeriod")

        # ListTimesheetPeriods
        fn = self._make_lambda("ListTimesheetPeriodsLambda", "TimesheetListPeriods",
                               "periods.ListTimesheetPeriods.handler.handler", period_env)
        self._tables["periods"].grant_read_data(fn)
        ds = self._graphql_api.add_lambda_data_source("ListPeriodsDataSource", fn)
        ds.create_resolver("Query_listTimesheetPeriods_Resolver", type_name="Query", field_name="listTimesheetPeriods")

        # GetCurrentPeriod
        fn = self._make_lambda("GetCurrentPeriodLambda", "TimesheetGetCurrentPeriod",
                               "periods.GetCurrentPeriod.handler.handler", period_env)
        self._tables["periods"].grant_read_data(fn)
        ds = self._graphql_api.add_lambda_data_source("GetCurrentPeriodDataSource", fn)
        ds.create_resolver("Query_getCurrentPeriod_Resolver", type_name="Query", field_name="getCurrentPeriod")

    # ------------------------------------------------------------------
    # Submission Management (4 Lambdas)
    # ------------------------------------------------------------------
    def _create_submission_lambdas(self) -> None:
        sub_env = {
            "SUBMISSIONS_TABLE": self._table_names["submissions"],
            "ENTRIES_TABLE": self._table_names["entries"],
        }

        # GetTimesheetSubmission
        fn = self._make_lambda("GetSubmissionLambda", "TimesheetGetSubmission",
                               "submissions.GetTimesheetSubmission.handler.handler", sub_env)
        self._tables["submissions"].grant_read_data(fn)
        self._tables["entries"].grant_read_data(fn)
        ds = self._graphql_api.add_lambda_data_source("GetSubmissionDataSource", fn)
        ds.create_resolver("Query_getTimesheetSubmission_Resolver", type_name="Query", field_name="getTimesheetSubmission")

        # ListMySubmissions
        fn = self._make_lambda("ListMySubmissionsLambda", "TimesheetListMySubmissions",
                               "submissions.ListMySubmissions.handler.handler",
                               {"SUBMISSIONS_TABLE": self._table_names["submissions"],
                                "ENTRIES_TABLE": self._table_names["entries"]})
        self._tables["submissions"].grant_read_data(fn)
        self._tables["entries"].grant_read_data(fn)
        ds = self._graphql_api.add_lambda_data_source("ListMySubmissionsDataSource", fn)
        ds.create_resolver("Query_listMySubmissions_Resolver", type_name="Query", field_name="listMySubmissions")

        # ListAllSubmissions
        fn = self._make_lambda("ListAllSubmissionsLambda", "TimesheetListAllSubmissions",
                               "submissions.ListAllSubmissions.handler.handler",
                               {"SUBMISSIONS_TABLE": self._table_names["submissions"],
                                "ENTRIES_TABLE": self._table_names["entries"],
                                "PROJECT_ASSIGNMENTS_TABLE": self._table_names["project_assignments"]})
        self._tables["submissions"].grant_read_data(fn)
        self._tables["entries"].grant_read_data(fn)
        self._tables["project_assignments"].grant_read_data(fn)
        ds = self._graphql_api.add_lambda_data_source("ListAllSubmissionsDataSource", fn)
        ds.create_resolver("Query_listAllSubmissions_Resolver", type_name="Query", field_name="listAllSubmissions")

    # ------------------------------------------------------------------
    # Entry Management (3 Lambdas)
    # ------------------------------------------------------------------
    def _create_entry_lambdas(self) -> None:
        entry_env = {
            "ENTRIES_TABLE": self._table_names["entries"],
            "SUBMISSIONS_TABLE": self._table_names["submissions"],
            "PROJECTS_TABLE": self._table_names["projects"],
        }

        # AddTimesheetEntry
        add_entry_env = {
            **entry_env,
            "PROJECT_ASSIGNMENTS_TABLE": self._table_names["project_assignments"],
        }
        fn = self._make_lambda("AddEntryLambda", "TimesheetAddEntry",
                               "entries.AddTimesheetEntry.handler.handler", add_entry_env)
        self._tables["entries"].grant_read_write_data(fn)
        self._tables["submissions"].grant_read_write_data(fn)
        self._tables["projects"].grant_read_data(fn)
        self._tables["project_assignments"].grant_read_write_data(fn)
        ds = self._graphql_api.add_lambda_data_source("AddEntryDataSource", fn)
        ds.create_resolver("Mutation_addTimesheetEntry_Resolver", type_name="Mutation", field_name="addTimesheetEntry")

        # UpdateTimesheetEntry
        fn = self._make_lambda("UpdateEntryLambda", "TimesheetUpdateEntry",
                               "entries.UpdateTimesheetEntry.handler.handler", entry_env)
        self._tables["entries"].grant_read_write_data(fn)
        self._tables["submissions"].grant_read_write_data(fn)
        self._tables["projects"].grant_read_data(fn)
        ds = self._graphql_api.add_lambda_data_source("UpdateEntryDataSource", fn)
        ds.create_resolver("Mutation_updateTimesheetEntry_Resolver", type_name="Mutation", field_name="updateTimesheetEntry")

        # RemoveTimesheetEntry
        fn = self._make_lambda("RemoveEntryLambda", "TimesheetRemoveEntry",
                               "entries.RemoveTimesheetEntry.handler.handler", entry_env)
        self._tables["entries"].grant_read_write_data(fn)
        self._tables["submissions"].grant_read_write_data(fn)
        ds = self._graphql_api.add_lambda_data_source("RemoveEntryDataSource", fn)
        ds.create_resolver("Mutation_removeTimesheetEntry_Resolver", type_name="Mutation", field_name="removeTimesheetEntry")

    # ------------------------------------------------------------------
    # Review Management (3 Lambdas)
    # ------------------------------------------------------------------
    def _create_auto_provisioning_lambda(self) -> None:
        """Lambda that runs every Monday to create period + Draft submissions."""
        fn = self._make_lambda("AutoProvisioningLambda", "TimesheetAutoProvisioning",
                               "auto_provisioning.handler.handler", {
                                   "PERIODS_TABLE": self._table_names["periods"],
                                   "SUBMISSIONS_TABLE": self._table_names["submissions"],
                                   "USERS_TABLE": self._table_names["users"],
                               })
        self._tables["periods"].grant_read_write_data(fn)
        self._tables["submissions"].grant_read_write_data(fn)
        self._tables["users"].grant_read_data(fn)
        rule = events.Rule(
            self, "AutoProvisioningRule",
            rule_name=f"TimesheetAutoProvisioning-{self.env_name}",
            schedule=events.Schedule.expression(TIMESHEET_AUTO_PROVISIONING_SCHEDULE),
            description="Creates weekly timesheet period and Draft submissions every Monday",
        )
        rule.add_target(targets.LambdaFunction(fn))

    def _create_deadline_reminder_lambda(self) -> None:
        """Lambda that runs Friday 1PM MYT to remind employees to fill timesheets."""
        fn = self._make_lambda("DeadlineReminderLambda", "TimesheetDeadlineReminder",
                               "deadline_reminder.handler.handler", {
                                   "PERIODS_TABLE": self._table_names["periods"],
                                   "SUBMISSIONS_TABLE": self._table_names["submissions"],
                                   "USERS_TABLE": self._table_names["users"],
                                   "SES_FROM_EMAIL": TIMESHEET_SES_FROM_EMAIL,
                               })
        self._tables["periods"].grant_read_data(fn)
        self._tables["submissions"].grant_read_data(fn)
        self._tables["users"].grant_read_data(fn)
        fn.add_to_role_policy(iam.PolicyStatement(
            actions=["ses:SendEmail"],
            resources=["*"],
        ))
        rule = events.Rule(
            self, "DeadlineReminderRule",
            rule_name=f"TimesheetDeadlineReminder-{self.env_name}",
            schedule=events.Schedule.expression(TIMESHEET_DEADLINE_REMINDER_SCHEDULE),
            description="Sends reminder emails 4 hours before timesheet deadline",
        )
        rule.add_target(targets.LambdaFunction(fn))

    # ------------------------------------------------------------------
    # Deadline Enforcement (1 Lambda — EventBridge triggered)
    # ------------------------------------------------------------------
    def _create_deadline_enforcement_lambda(self) -> None:
        fn = self._make_lambda("DeadlineEnforcementLambda", "TimesheetDeadlineEnforcement",
                               "deadline_enforcement.handler.handler", {
                                   "PERIODS_TABLE": self._table_names["periods"],
                                   "SUBMISSIONS_TABLE": self._table_names["submissions"],
                                   "ENTRIES_TABLE": self._table_names["entries"],
                                   "USERS_TABLE": self._table_names["users"],
                                   "SES_FROM_EMAIL": TIMESHEET_SES_FROM_EMAIL,
                               })
        self._tables["periods"].grant_read_write_data(fn)
        self._tables["submissions"].grant_read_write_data(fn)
        self._tables["entries"].grant_read_data(fn)
        self._tables["users"].grant_read_data(fn)
        fn.add_to_role_policy(iam.PolicyStatement(
            actions=["ses:SendEmail"],
            resources=["*"],
        ))
        rule = events.Rule(
            self, "DeadlineEnforcementRule",
            rule_name=f"TimesheetDeadlineEnforcement-{self.env_name}",
            schedule=events.Schedule.expression(TIMESHEET_DEADLINE_ENFORCEMENT_SCHEDULE),
            description="Auto-submits Draft timesheets and sends under-40h notifications at deadline",
        )
        rule.add_target(targets.LambdaFunction(fn))

    # ------------------------------------------------------------------
    # Report Generator (3 Lambdas — 1 stream + 2 AppSync)
    # ------------------------------------------------------------------
    def _create_report_lambdas(self) -> None:
        report_env = {
            "SUBMISSIONS_TABLE": self._table_names["submissions"],
            "ENTRIES_TABLE": self._table_names["entries"],
            "USERS_TABLE": self._table_names["users"],
            "PROJECTS_TABLE": self._table_names["projects"],
            "EMPLOYEE_PERFORMANCE_TABLE": self._table_names["employee_performance"],
            "PERIODS_TABLE": self._table_names["periods"],
            "PROJECT_ASSIGNMENTS_TABLE": self._table_names["project_assignments"],
            "REPORT_BUCKET": self._report_bucket.bucket_name,
        }
        report_read_tables = ["submissions", "entries", "users", "projects", "employee_performance", "periods", "project_assignments"]

        # Stream-triggered report generator (keeps original handler.py)
        fn = self._make_lambda("ReportGeneratorStreamLambda", "TimesheetReportGeneratorStream",
                               "reports.handler.handler", report_env)
        for t in report_read_tables:
            self._tables[t].grant_read_data(fn)
        self._report_bucket.grant_read_write(fn)
        fn.add_event_source(
            lambda_event_sources.DynamoEventSource(
                self._submissions_with_stream,
                starting_position=_lambda.StartingPosition.TRIM_HORIZON,
                batch_size=10,
                retry_attempts=3,
            )
        )

        # GetTCSummaryReport
        fn = self._make_lambda("GetTCSummaryReportLambda", "TimesheetGetTCSummaryReport",
                               "reports.GetTCSummaryReport.handler.handler", report_env)
        for t in report_read_tables:
            self._tables[t].grant_read_data(fn)
        self._report_bucket.grant_read_write(fn)
        ds = self._graphql_api.add_lambda_data_source("GetTCSummaryReportDataSource", fn)
        ds.create_resolver("Query_getTCSummaryReport_Resolver", type_name="Query", field_name="getTCSummaryReport")

        # GetProjectSummaryReport
        fn = self._make_lambda("GetProjectSummaryReportLambda", "TimesheetGetProjectSummaryReport",
                               "reports.GetProjectSummaryReport.handler.handler", report_env)
        for t in report_read_tables:
            self._tables[t].grant_read_data(fn)
        self._report_bucket.grant_read_write(fn)
        ds = self._graphql_api.add_lambda_data_source("GetProjectSummaryReportDataSource", fn)
        ds.create_resolver("Query_getProjectSummaryReport_Resolver", type_name="Query", field_name="getProjectSummaryReport")

    # ------------------------------------------------------------------
    # Performance Tracking (1 Lambda — DynamoDB Stream triggered)
    # ------------------------------------------------------------------
    def _create_performance_tracking_lambda(self) -> None:
        fn = self._make_lambda("PerformanceTrackingLambda", "TimesheetPerformanceTracking",
                               "performance.handler.handler", {
                                   "EMPLOYEE_PERFORMANCE_TABLE": self._table_names["employee_performance"],
                               })
        self._tables["employee_performance"].grant_read_write_data(fn)
        fn.add_event_source(
            lambda_event_sources.DynamoEventSource(
                self._submissions_with_stream,
                starting_position=_lambda.StartingPosition.TRIM_HORIZON,
                batch_size=10,
                retry_attempts=3,
            )
        )

    # ------------------------------------------------------------------
    # Notification Service (1 Lambda — EventBridge triggered)
    # ------------------------------------------------------------------
    def _create_notification_lambda(self) -> None:
        fn = self._make_lambda("NotificationLambda", "TimesheetNotification",
                               "notifications.handler.handler", {
                                   "SUBMISSIONS_TABLE": self._table_names["submissions"],
                                   "ENTRIES_TABLE": self._table_names["entries"],
                                   "USERS_TABLE": self._table_names["users"],
                                   "PROJECTS_TABLE": self._table_names["projects"],
                                   "EMPLOYEE_PERFORMANCE_TABLE": self._table_names["employee_performance"],
                                   "PERIODS_TABLE": self._table_names["periods"],
                                   "REPORT_DISTRIBUTION_CONFIG_TABLE": self._table_names["report_distribution_config"],
                                   "PROJECT_ASSIGNMENTS_TABLE": self._table_names["project_assignments"],
                                   "REPORT_BUCKET": self._report_bucket.bucket_name,
                                   "SES_FROM_EMAIL": TIMESHEET_SES_FROM_EMAIL,
                               }, timeout=300)
        self._tables["submissions"].grant_read_data(fn)
        self._tables["entries"].grant_read_data(fn)
        self._tables["users"].grant_read_data(fn)
        self._tables["projects"].grant_read_data(fn)
        self._tables["employee_performance"].grant_read_data(fn)
        self._tables["periods"].grant_read_data(fn)
        self._tables["report_distribution_config"].grant_read_data(fn)
        self._tables["project_assignments"].grant_read_data(fn)
        self._report_bucket.grant_read_write(fn)
        fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ses:SendEmail", "ses:SendRawEmail"],
                resources=["*"],
            )
        )
        rule = events.Rule(
            self, "NotificationScheduleRule",
            rule_name=f"TimesheetNotification-{self.env_name}",
            schedule=events.Schedule.expression(TIMESHEET_NOTIFICATION_SCHEDULE),
            description="Triggers notification Lambda to generate and email timesheet reports",
        )
        rule.add_target(targets.LambdaFunction(fn))

    # ------------------------------------------------------------------
    # Notification Config (2 Lambdas)
    # ------------------------------------------------------------------
    def _create_notification_config_lambdas(self) -> None:
        config_env = {"REPORT_DISTRIBUTION_CONFIG_TABLE": self._table_names["report_distribution_config"]}

        # UpdateReportDistributionConfig
        fn = self._make_lambda("UpdateNotificationConfigLambda", "TimesheetUpdateNotificationConfig",
                               "notification_config.UpdateReportDistributionConfig.handler.handler", config_env)
        self._tables["report_distribution_config"].grant_read_write_data(fn)
        ds = self._graphql_api.add_lambda_data_source("UpdateNotificationConfigDataSource", fn)
        ds.create_resolver("Mutation_updateReportDistributionConfig_Resolver", type_name="Mutation", field_name="updateReportDistributionConfig")

        # GetReportDistributionConfig
        fn = self._make_lambda("GetNotificationConfigLambda", "TimesheetGetNotificationConfig",
                               "notification_config.GetReportDistributionConfig.handler.handler", config_env)
        self._tables["report_distribution_config"].grant_read_data(fn)
        ds = self._graphql_api.add_lambda_data_source("GetNotificationConfigDataSource", fn)
        ds.create_resolver("Query_getReportDistributionConfig_Resolver", type_name="Query", field_name="getReportDistributionConfig")

    # ------------------------------------------------------------------
    # Archival (1 Lambda — EventBridge triggered)
    # ------------------------------------------------------------------
    def _create_archival_lambda(self) -> None:
        fn = self._make_lambda("ArchivalLambda", "TimesheetArchival",
                               "archival.handler.handler", {
                                   "SUBMISSIONS_TABLE": self._table_names["submissions"],
                                   "PERIODS_TABLE": self._table_names["periods"],
                               })
        self._tables["submissions"].grant_read_write_data(fn)
        self._tables["periods"].grant_read_data(fn)
        rule = events.Rule(
            self, "ArchivalScheduleRule",
            rule_name=f"TimesheetArchival-{self.env_name}",
            schedule=events.Schedule.expression(TIMESHEET_ARCHIVAL_SCHEDULE),
            description="Triggers archival Lambda to archive submissions for ended biweekly periods",
        )
        rule.add_target(targets.LambdaFunction(fn))

    # ------------------------------------------------------------------
    # Main Database (4 Lambdas)
    # ------------------------------------------------------------------
    def _create_main_database_lambdas(self) -> None:
        db_env = {
            "MAIN_DATABASE_TABLE": self._table_names["main_database"],
            "REPORT_BUCKET": self._report_bucket.bucket_name,
        }

        # ListMainDatabase
        fn = self._make_lambda("ListMainDatabaseLambda", "TimesheetListMainDatabase",
                               "main_database.ListMainDatabase.handler.handler",
                               {"MAIN_DATABASE_TABLE": self._table_names["main_database"]})
        self._tables["main_database"].grant_read_data(fn)
        ds = self._graphql_api.add_lambda_data_source("ListMainDatabaseDataSource", fn)
        ds.create_resolver("Query_listMainDatabase_Resolver", type_name="Query", field_name="listMainDatabase")

        # UpdateMainDatabaseRecord
        fn = self._make_lambda("UpdateMainDatabaseRecordLambda", "TimesheetUpdateMainDatabaseRecord",
                               "main_database.UpdateMainDatabaseRecord.handler.handler", db_env)
        self._tables["main_database"].grant_read_write_data(fn)
        ds = self._graphql_api.add_lambda_data_source("UpdateMainDatabaseRecordDataSource", fn)
        ds.create_resolver("Mutation_updateMainDatabaseRecord_Resolver", type_name="Mutation", field_name="updateMainDatabaseRecord")

        # BulkImportCSV
        fn = self._make_lambda("BulkImportCSVLambda", "TimesheetBulkImportCSV",
                               "main_database.BulkImportCSV.handler.handler", db_env)
        self._tables["main_database"].grant_read_write_data(fn)
        self._report_bucket.grant_read(fn)
        ds = self._graphql_api.add_lambda_data_source("BulkImportCSVDataSource", fn)
        ds.create_resolver("Mutation_bulkImportCSV_Resolver", type_name="Mutation", field_name="bulkImportCSV")

        # RefreshDatabase
        fn = self._make_lambda("RefreshDatabaseLambda", "TimesheetRefreshDatabase",
                               "main_database.RefreshDatabase.handler.handler", db_env)
        self._tables["main_database"].grant_read_write_data(fn)
        self._report_bucket.grant_read(fn)
        ds = self._graphql_api.add_lambda_data_source("RefreshDatabaseDataSource", fn)
        ds.create_resolver("Mutation_refreshDatabase_Resolver", type_name="Mutation", field_name="refreshDatabase")

    def _create_sync_from_projects_lambda(self) -> None:
        """Lambda triggered by Projects DynamoDB Stream to sync into Main_Database."""
        fn = self._make_lambda(
            "SyncFromProjectsLambda", "TimesheetSyncFromProjects",
            "main_database.SyncFromProjects.handler.handler",
            {"MAIN_DATABASE_TABLE": self._table_names["main_database"]},
        )
        self._tables["main_database"].grant_read_write_data(fn)
        fn.add_event_source(
            lambda_event_sources.DynamoEventSource(
                self._projects_with_stream,
                starting_position=_lambda.StartingPosition.TRIM_HORIZON,
                batch_size=10,
                retry_attempts=3,
            )
        )

    def _create_project_assignment_lambdas(self) -> None:
        pa_env = {
            "PROJECT_ASSIGNMENTS_TABLE": self._table_names["project_assignments"],
            "USERS_TABLE": self._table_names["users"],
            "PROJECTS_TABLE": self._table_names["projects"],
        }

        # CreateProjectAssignment
        fn = self._make_lambda("CreateProjectAssignmentLambda", "TimesheetCreateProjectAssignment",
                               "project_assignments.CreateProjectAssignment.handler.handler", pa_env)
        self._tables["project_assignments"].grant_read_write_data(fn)
        self._tables["users"].grant_read_data(fn)
        self._tables["projects"].grant_read_data(fn)
        ds = self._graphql_api.add_lambda_data_source("CreateProjectAssignmentDataSource", fn)
        ds.create_resolver("Mutation_createProjectAssignment_Resolver", type_name="Mutation", field_name="createProjectAssignment")

        # UpdateProjectAssignment
        fn = self._make_lambda("UpdateProjectAssignmentLambda", "TimesheetUpdateProjectAssignment",
                               "project_assignments.UpdateProjectAssignment.handler.handler", pa_env)
        self._tables["project_assignments"].grant_read_write_data(fn)
        self._tables["users"].grant_read_data(fn)
        self._tables["projects"].grant_read_data(fn)
        ds = self._graphql_api.add_lambda_data_source("UpdateProjectAssignmentDataSource", fn)
        ds.create_resolver("Mutation_updateProjectAssignment_Resolver", type_name="Mutation", field_name="updateProjectAssignment")

        # DeleteProjectAssignment
        fn = self._make_lambda("DeleteProjectAssignmentLambda", "TimesheetDeleteProjectAssignment",
                               "project_assignments.DeleteProjectAssignment.handler.handler",
                               {"PROJECT_ASSIGNMENTS_TABLE": self._table_names["project_assignments"]})
        self._tables["project_assignments"].grant_read_write_data(fn)
        ds = self._graphql_api.add_lambda_data_source("DeleteProjectAssignmentDataSource", fn)
        ds.create_resolver("Mutation_deleteProjectAssignment_Resolver", type_name="Mutation", field_name="deleteProjectAssignment")

        # ListProjectAssignments
        fn = self._make_lambda("ListProjectAssignmentsLambda", "TimesheetListProjectAssignments",
                               "project_assignments.ListProjectAssignments.handler.handler",
                               {"PROJECT_ASSIGNMENTS_TABLE": self._table_names["project_assignments"]})
        self._tables["project_assignments"].grant_read_data(fn)
        ds = self._graphql_api.add_lambda_data_source("ListProjectAssignmentsDataSource", fn)
        ds.create_resolver("Query_listProjectAssignments_Resolver", type_name="Query", field_name="listProjectAssignments")

