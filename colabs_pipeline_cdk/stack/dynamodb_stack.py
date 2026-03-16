"""
Timesheet DynamoDB Stack

All 10 DynamoDB tables with GSIs for the Employee Timesheet Management System.
Exports table names and ARNs to SSM Parameter Store for cross-stack lookups.
"""

from aws_cdk import RemovalPolicy, Stack, Tags, aws_dynamodb as dynamodb, aws_ssm as ssm
from constructs import Construct

from colabs_pipeline_cdk.environment import (
    ENV_CONFIG,
    PROJECT_NAME,
    TIMESHEET_SSM_PREFIX,
    TIMESHEET_TABLE_NAMES,
)


class TimesheetDynamoDBStack(Stack):
    """CDK Stack for all Timesheet DynamoDB tables."""

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
        Tags.of(self).add("Component", "Timesheet-DynamoDB")
        Tags.of(self).add("Environment", env_name)

        removal_policy = (
            RemovalPolicy.DESTROY if env_name == "dev" else RemovalPolicy.RETAIN
        )

        self._create_tables(removal_policy)
        self._export_ssm_params()

    def _ssm_path(self, key: str) -> str:
        return f"{TIMESHEET_SSM_PREFIX}/{self.env_name}/dynamodb/{key}"

    def _table_name(self, key: str) -> str:
        return f"{TIMESHEET_TABLE_NAMES[key]}-{self.env_name}"

    def _export_ssm_params(self) -> None:
        """Export all table names, ARNs, and stream ARN to SSM."""
        tables = {
            "users": self.users_table,
            "departments": self.departments_table,
            "positions": self.positions_table,
            "projects": self.projects_table,
            "periods": self.periods_table,
            "submissions": self.submissions_table,
            "entries": self.entries_table,
            "employee_performance": self.employee_performance_table,
            "report_distribution_config": self.report_distribution_config_table,
            "main_database": self.main_database_table,
        }
        for key, table in tables.items():
            ssm.StringParameter(
                self,
                f"SSM-{key}-table-name",
                parameter_name=self._ssm_path(f"{key}/table-name"),
                string_value=table.table_name,
            )
            ssm.StringParameter(
                self,
                f"SSM-{key}-table-arn",
                parameter_name=self._ssm_path(f"{key}/table-arn"),
                string_value=table.table_arn,
            )

        # Submissions stream ARN (needed by Lambda stack for DynamoDB Streams)
        ssm.StringParameter(
            self,
            "SSM-submissions-stream-arn",
            parameter_name=self._ssm_path("submissions/stream-arn"),
            string_value=self.submissions_table.table_stream_arn,
        )

    def _create_tables(self, removal_policy: RemovalPolicy) -> None:
        # --- Users table ---
        self.users_table = dynamodb.Table(
            self,
            "UsersTable",
            table_name=self._table_name("users"),
            partition_key=dynamodb.Attribute(
                name="userId", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=removal_policy,
        )
        self.users_table.add_global_secondary_index(
            index_name="email-index",
            partition_key=dynamodb.Attribute(
                name="email", type=dynamodb.AttributeType.STRING
            ),
        )
        self.users_table.add_global_secondary_index(
            index_name="departmentId-index",
            partition_key=dynamodb.Attribute(
                name="departmentId", type=dynamodb.AttributeType.STRING
            ),
        )
        self.users_table.add_global_secondary_index(
            index_name="supervisorId-index",
            partition_key=dynamodb.Attribute(
                name="supervisorId", type=dynamodb.AttributeType.STRING
            ),
        )

        # --- Departments table ---
        self.departments_table = dynamodb.Table(
            self,
            "DepartmentsTable",
            table_name=self._table_name("departments"),
            partition_key=dynamodb.Attribute(
                name="departmentId", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=removal_policy,
        )
        self.departments_table.add_global_secondary_index(
            index_name="departmentName-index",
            partition_key=dynamodb.Attribute(
                name="departmentName", type=dynamodb.AttributeType.STRING
            ),
        )

        # --- Positions table ---
        self.positions_table = dynamodb.Table(
            self,
            "PositionsTable",
            table_name=self._table_name("positions"),
            partition_key=dynamodb.Attribute(
                name="positionId", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=removal_policy,
        )
        self.positions_table.add_global_secondary_index(
            index_name="positionName-index",
            partition_key=dynamodb.Attribute(
                name="positionName", type=dynamodb.AttributeType.STRING
            ),
        )

        # --- Projects table ---
        self.projects_table = dynamodb.Table(
            self,
            "ProjectsTable",
            table_name=self._table_name("projects"),
            partition_key=dynamodb.Attribute(
                name="projectId", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=removal_policy,
        )
        self.projects_table.add_global_secondary_index(
            index_name="projectCode-index",
            partition_key=dynamodb.Attribute(
                name="projectCode", type=dynamodb.AttributeType.STRING
            ),
        )
        self.projects_table.add_global_secondary_index(
            index_name="approval_status-index",
            partition_key=dynamodb.Attribute(
                name="approval_status", type=dynamodb.AttributeType.STRING
            ),
        )
        self.projects_table.add_global_secondary_index(
            index_name="projectManagerId-index",
            partition_key=dynamodb.Attribute(
                name="projectManagerId", type=dynamodb.AttributeType.STRING
            ),
        )

        # --- Timesheet_Periods table ---
        self.periods_table = dynamodb.Table(
            self,
            "TimesheetPeriodsTable",
            table_name=self._table_name("periods"),
            partition_key=dynamodb.Attribute(
                name="periodId", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=removal_policy,
        )
        self.periods_table.add_global_secondary_index(
            index_name="startDate-index",
            partition_key=dynamodb.Attribute(
                name="startDate", type=dynamodb.AttributeType.STRING
            ),
        )

        # --- Timesheet_Submissions table (with DynamoDB Streams) ---
        self.submissions_table = dynamodb.Table(
            self,
            "TimesheetSubmissionsTable",
            table_name=self._table_name("submissions"),
            partition_key=dynamodb.Attribute(
                name="submissionId", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=removal_policy,
            stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
        )
        self.submissions_table.add_global_secondary_index(
            index_name="employeeId-periodId-index",
            partition_key=dynamodb.Attribute(
                name="employeeId", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="periodId", type=dynamodb.AttributeType.STRING
            ),
        )
        self.submissions_table.add_global_secondary_index(
            index_name="periodId-status-index",
            partition_key=dynamodb.Attribute(
                name="periodId", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="status", type=dynamodb.AttributeType.STRING
            ),
        )
        self.submissions_table.add_global_secondary_index(
            index_name="status-index",
            partition_key=dynamodb.Attribute(
                name="status", type=dynamodb.AttributeType.STRING
            ),
        )

        # --- Timesheet_Entries table ---
        self.entries_table = dynamodb.Table(
            self,
            "TimesheetEntriesTable",
            table_name=self._table_name("entries"),
            partition_key=dynamodb.Attribute(
                name="entryId", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=removal_policy,
        )
        self.entries_table.add_global_secondary_index(
            index_name="submissionId-index",
            partition_key=dynamodb.Attribute(
                name="submissionId", type=dynamodb.AttributeType.STRING
            ),
        )
        self.entries_table.add_global_secondary_index(
            index_name="projectCode-index",
            partition_key=dynamodb.Attribute(
                name="projectCode", type=dynamodb.AttributeType.STRING
            ),
        )

        # --- Employee_Performance table (composite key) ---
        self.employee_performance_table = dynamodb.Table(
            self,
            "EmployeePerformanceTable",
            table_name=self._table_name("employee_performance"),
            partition_key=dynamodb.Attribute(
                name="userId", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="year", type=dynamodb.AttributeType.NUMBER
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=removal_policy,
        )

        # --- Report_Distribution_Config table ---
        self.report_distribution_config_table = dynamodb.Table(
            self,
            "ReportDistributionConfigTable",
            table_name=self._table_name("report_distribution_config"),
            partition_key=dynamodb.Attribute(
                name="configId", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=removal_policy,
        )

        # --- Main_Database table ---
        self.main_database_table = dynamodb.Table(
            self,
            "MainDatabaseTable",
            table_name=self._table_name("main_database"),
            partition_key=dynamodb.Attribute(
                name="recordId", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=removal_policy,
        )
