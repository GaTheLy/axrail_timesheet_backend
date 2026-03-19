"""
Environment configurations and constants for COLABS pipeline stacks.

Multi-environment support: dev, staging, prod.
Environment-specific configurations are centralized here.
"""


# Project-level constants
PROJECT_NAME = "Colabs"


# Supported environments
ENVIRONMENTS = ["dev", "staging", "prod"]

# Environment-specific configurations
ENV_CONFIG = {
    "dev": {
        "account": "815254799325",  # AWS account ID for dev
        "region": "ap-southeast-1",
        "suffix": "dev",
    },
    "staging": {
        "account": "815254799325",  # AWS account ID for staging
        "region": "ap-southeast-1",
        "suffix": "staging",
    },
    "prod": {
        "account": "815254799325",  # AWS account ID for prod
        "region": "ap-southeast-1",
        "suffix": "prod",
    },
}

# --------------------------------------------------------------------------
# Timesheet System Constants
# --------------------------------------------------------------------------

TIMESHEET_STACK_NAME = f"{PROJECT_NAME}TimesheetStack"
TIMESHEET_DYNAMODB_STACK_NAME = f"{PROJECT_NAME}TimesheetDynamoDBStack"
TIMESHEET_AUTH_STACK_NAME = f"{PROJECT_NAME}TimesheetAuthStack"
TIMESHEET_STORAGE_STACK_NAME = f"{PROJECT_NAME}TimesheetStorageStack"
TIMESHEET_API_STACK_NAME = f"{PROJECT_NAME}TimesheetApiStack"
TIMESHEET_LAMBDA_STACK_NAME = f"{PROJECT_NAME}TimesheetLambdaStack"

# SSM Parameter Store prefix for cross-stack references
TIMESHEET_SSM_PREFIX = "/timesheet"

# DynamoDB table name prefixes (suffixed with environment at deploy time)
TIMESHEET_TABLE_NAMES = {
    "users": "Timesheet_Users",
    "departments": "Timesheet_Departments",
    "positions": "Timesheet_Positions",
    "projects": "Timesheet_Projects",
    "periods": "Timesheet_Periods",
    "submissions": "Timesheet_Submissions",
    "entries": "Timesheet_Entries",
    "employee_performance": "Timesheet_EmployeePerformance",
    "report_distribution_config": "Timesheet_ReportDistributionConfig",
    "main_database": "Timesheet_MainDatabase",
}

# Cognito
TIMESHEET_USER_POOL_NAME = "TimesheetUserPool"
TIMESHEET_COGNITO_GROUPS = ["superadmin", "admin", "user"]
TIMESHEET_USER_ROLES = ["Project_Manager", "Tech_Lead", "Employee"]
TIMESHEET_USER_TYPES = ["superadmin", "admin", "user"]

# AppSync
TIMESHEET_API_NAME = "TimesheetGraphQLApi"

# S3
TIMESHEET_REPORT_BUCKET_PREFIX = "colabs-timesheet-reports"
TIMESHEET_REPORT_KEY_PREFIX = "reports/{type}/{period}/{timestamp}.csv"

# Lambda
TIMESHEET_LAMBDA_RUNTIME = "python3.12"
TIMESHEET_LAMBDA_TIMEOUT_SECONDS = 30
TIMESHEET_LAMBDA_MEMORY_MB = 256

# EventBridge
# Auto-provisioning: Every Monday 00:05 MYT (Sunday 16:05 UTC)
TIMESHEET_AUTO_PROVISIONING_SCHEDULE = "cron(5 16 ? * SUN *)"
# Deadline reminder: Every Friday 1PM MYT (05:00 UTC)
TIMESHEET_DEADLINE_REMINDER_SCHEDULE = "cron(0 5 ? * FRI *)"
# Deadline enforcement: Every Friday 5:05PM MYT (09:05 UTC) — 5 min after deadline
TIMESHEET_DEADLINE_ENFORCEMENT_SCHEDULE = "cron(5 9 ? * FRI *)"
# Notification (report distribution): Every Monday at 8am UTC
TIMESHEET_NOTIFICATION_SCHEDULE = "cron(0 8 ? * MON *)"
# Archival: Daily
TIMESHEET_ARCHIVAL_SCHEDULE = "rate(1 day)"

# SES
TIMESHEET_SES_FROM_EMAIL = "noreply@example.com"  # Replace with verified SES email

# Submission statuses
SUBMISSION_STATUSES = ["Draft", "Submitted"]

# Project approval statuses
APPROVAL_STATUSES = ["Pending_Approval", "Approved", "Rejected"]
