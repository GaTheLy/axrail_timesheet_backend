"""Unit tests for Report Generator Lambda.

Validates: Requirements 9.5, 9.6, 10.5, 10.6
"""

import csv
import io
import os
import sys
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lambdas"))

os.environ.setdefault("SUBMISSIONS_TABLE", "SubmissionsTable")
os.environ.setdefault("ENTRIES_TABLE", "EntriesTable")
os.environ.setdefault("USERS_TABLE", "UsersTable")
os.environ.setdefault("PROJECTS_TABLE", "ProjectsTable")
os.environ.setdefault("EMPLOYEE_PERFORMANCE_TABLE", "PerformanceTable")
os.environ.setdefault("PERIODS_TABLE", "PeriodsTable")
os.environ.setdefault("REPORT_BUCKET", "report-bucket")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_employee(user_id="emp-001", full_name="Alice Smith", supervisor_id="tl-001"):
    return {
        "userId": user_id,
        "fullName": full_name,
        "supervisorId": supervisor_id,
        "role": "Employee",
        "email": f"{user_id}@example.com",
    }


def _make_submission(
    submission_id="sub-001",
    period_id="period-001",
    employee_id="emp-001",
    status="Approved",
    chargeable_hours=Decimal("20"),
    total_hours=Decimal("40"),
):
    return {
        "submissionId": submission_id,
        "periodId": period_id,
        "employeeId": employee_id,
        "status": status,
        "chargeableHours": chargeable_hours,
        "totalHours": total_hours,
    }


def _make_project(
    project_code="PROJ-001",
    project_name="Project Alpha",
    planned_hours=Decimal("100"),
    status="Active",
    approval_status="Approved",
):
    return {
        "projectId": f"pid-{project_code}",
        "projectCode": project_code,
        "projectName": project_name,
        "plannedHours": planned_hours,
        "status": status,
        "approval_status": approval_status,
    }


def _make_stream_record(
    employee_id="emp-001",
    period_id="period-001",
    new_status="Approved",
    old_status="Submitted",
    event_name="MODIFY",
):
    record = {
        "eventName": event_name,
        "dynamodb": {
            "NewImage": {
                "submissionId": {"S": "sub-001"},
                "periodId": {"S": period_id},
                "employeeId": {"S": employee_id},
                "status": {"S": new_status},
            },
        },
    }
    if event_name == "MODIFY":
        record["dynamodb"]["OldImage"] = {"status": {"S": old_status}}
    return record


def _parse_csv(csv_content):
    """Parse CSV string into list of dicts."""
    reader = csv.DictReader(io.StringIO(csv_content))
    return list(reader)



# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _mock_boto(monkeypatch):
    """Patch boto3 resources used at module level in the reports handler."""
    mock_submissions_table = MagicMock()
    mock_entries_table = MagicMock()
    mock_users_table = MagicMock()
    mock_projects_table = MagicMock()
    mock_performance_table = MagicMock()
    mock_periods_table = MagicMock()

    def _table_router(name):
        mapping = {
            "SubmissionsTable": mock_submissions_table,
            "EntriesTable": mock_entries_table,
            "UsersTable": mock_users_table,
            "ProjectsTable": mock_projects_table,
            "PerformanceTable": mock_performance_table,
            "PeriodsTable": mock_periods_table,
        }
        return mapping.get(name, MagicMock())

    mock_dynamodb = MagicMock()
    mock_dynamodb.Table.side_effect = _table_router

    mock_s3 = MagicMock()
    mock_s3.put_object.return_value = {}
    mock_s3.list_objects_v2.return_value = {"Contents": []}

    # Defaults
    mock_submissions_table.query.return_value = {"Items": []}
    mock_entries_table.query.return_value = {"Items": []}
    mock_users_table.query.return_value = {"Items": []}
    mock_users_table.get_item.return_value = {"Item": None}
    mock_projects_table.scan.return_value = {"Items": []}
    mock_performance_table.get_item.return_value = {}
    mock_periods_table.get_item.return_value = {"Item": None}
    mock_periods_table.scan.return_value = {"Items": []}

    with patch("boto3.resource", return_value=mock_dynamodb), \
         patch("boto3.client", return_value=mock_s3):
        # Clear cached module so module-level globals pick up mocks
        for mod_name in list(sys.modules):
            if "reports" in mod_name and "handler" in mod_name:
                del sys.modules[mod_name]

        from lambdas.reports import handler as reports_mod

        reports_mod.dynamodb = mock_dynamodb
        reports_mod.s3_client = mock_s3
        reports_mod.REPORT_BUCKET = "report-bucket"

        yield {
            "mod": reports_mod,
            "submissions_table": mock_submissions_table,
            "entries_table": mock_entries_table,
            "users_table": mock_users_table,
            "projects_table": mock_projects_table,
            "performance_table": mock_performance_table,
            "periods_table": mock_periods_table,
            "s3_client": mock_s3,
        }


# ---------------------------------------------------------------------------
# Requirement 9.5 — TC Summary includes only Approved/Locked submissions
# ---------------------------------------------------------------------------


class TestTCSummaryFiltersByStatus:
    """TC Summary should only include employees with Approved or Locked submissions."""

    def test_approved_submission_included(self, _mock_boto):
        """An Approved submission appears in the TC Summary CSV.

        Validates: Requirements 9.5
        """
        mod = _mock_boto["mod"]
        s3 = _mock_boto["s3_client"]

        emp = _make_employee("emp-001", "Alice Smith", "tl-001")
        sub = _make_submission("sub-001", "period-001", "emp-001", "Approved",
                               Decimal("20"), Decimal("40"))

        with patch.object(mod, "_get_supervised_employees", return_value=[emp]), \
             patch.object(mod, "_get_submissions_for_period", return_value=[sub]), \
             patch.object(mod, "_get_ytd_chargeability", return_value=Decimal("55.00")):
            result = mod._generate_tc_summary("tl-001", "period-001")

        assert result is not None
        s3.put_object.assert_called_once()
        csv_content = s3.put_object.call_args[1]["Body"].decode("utf-8")
        rows = _parse_csv(csv_content)
        assert len(rows) == 1
        assert rows[0]["Name"] == "Alice Smith"

    def test_locked_submission_included(self, _mock_boto):
        """A Locked submission appears in the TC Summary CSV.

        Validates: Requirements 9.5
        """
        mod = _mock_boto["mod"]
        s3 = _mock_boto["s3_client"]

        emp = _make_employee("emp-002", "Bob Jones", "tl-001")
        sub = _make_submission("sub-002", "period-001", "emp-002", "Locked",
                               Decimal("0"), Decimal("0"))

        with patch.object(mod, "_get_supervised_employees", return_value=[emp]), \
             patch.object(mod, "_get_submissions_for_period", return_value=[sub]), \
             patch.object(mod, "_get_ytd_chargeability", return_value=Decimal("0")):
            result = mod._generate_tc_summary("tl-001", "period-001")

        assert result is not None
        csv_content = s3.put_object.call_args[1]["Body"].decode("utf-8")
        rows = _parse_csv(csv_content)
        assert len(rows) == 1
        assert rows[0]["Name"] == "Bob Jones"

    def test_no_approved_locked_returns_none(self, _mock_boto):
        """When no Approved/Locked submissions exist, no report is generated.

        Validates: Requirements 9.5
        """
        mod = _mock_boto["mod"]
        s3 = _mock_boto["s3_client"]

        emp = _make_employee("emp-001", "Alice Smith", "tl-001")

        with patch.object(mod, "_get_supervised_employees", return_value=[emp]), \
             patch.object(mod, "_get_submissions_for_period", return_value=[]):
            result = mod._generate_tc_summary("tl-001", "period-001")

        assert result is None
        s3.put_object.assert_not_called()

    def test_mixed_statuses_only_approved_locked_included(self, _mock_boto):
        """Only Approved and Locked submissions appear; others are excluded.

        Validates: Requirements 9.5
        """
        mod = _mock_boto["mod"]
        s3 = _mock_boto["s3_client"]

        emp1 = _make_employee("emp-001", "Alice Smith", "tl-001")
        emp2 = _make_employee("emp-002", "Bob Jones", "tl-001")
        emp3 = _make_employee("emp-003", "Charlie Brown", "tl-001")

        approved_sub = _make_submission("sub-001", "period-001", "emp-001",
                                        "Approved", Decimal("30"), Decimal("40"))
        locked_sub = _make_submission("sub-002", "period-001", "emp-002",
                                      "Locked", Decimal("10"), Decimal("20"))

        with patch.object(mod, "_get_supervised_employees",
                          return_value=[emp1, emp2, emp3]), \
             patch.object(mod, "_get_submissions_for_period",
                          return_value=[approved_sub, locked_sub]), \
             patch.object(mod, "_get_ytd_chargeability", return_value=Decimal("50.00")):
            result = mod._generate_tc_summary("tl-001", "period-001")

        csv_content = s3.put_object.call_args[1]["Body"].decode("utf-8")
        rows = _parse_csv(csv_content)
        names = {row["Name"] for row in rows}
        assert names == {"Alice Smith", "Bob Jones"}
        assert "Charlie Brown" not in names

    def test_non_supervised_employee_excluded(self, _mock_boto):
        """Submissions from employees not under the tech lead are excluded.

        Validates: Requirements 9.5
        """
        mod = _mock_boto["mod"]

        emp = _make_employee("emp-001", "Alice Smith", "tl-001")
        other_sub = _make_submission("sub-other", "period-001", "emp-999",
                                     "Approved", Decimal("10"), Decimal("20"))

        with patch.object(mod, "_get_supervised_employees", return_value=[emp]), \
             patch.object(mod, "_get_submissions_for_period",
                          return_value=[other_sub]):
            result = mod._generate_tc_summary("tl-001", "period-001")

        assert result is None


# ---------------------------------------------------------------------------
# Requirement 10.6 — Project Summary includes all projects regardless of status
# ---------------------------------------------------------------------------


class TestProjectSummaryIncludesAllProjects:
    """Project Summary should include ALL projects regardless of status."""

    def test_all_approval_statuses_included(self, _mock_boto):
        """Projects with Approved, Pending_Approval, and Rejected all appear.

        Validates: Requirements 10.6
        """
        mod = _mock_boto["mod"]
        s3 = _mock_boto["s3_client"]

        projects = [
            _make_project("PROJ-A", "Alpha", Decimal("100"), "Active", "Approved"),
            _make_project("PROJ-B", "Beta", Decimal("200"), "Active", "Pending_Approval"),
            _make_project("PROJ-C", "Gamma", Decimal("50"), "Inactive", "Rejected"),
        ]

        with patch.object(mod, "_get_all_projects", return_value=projects), \
             patch.object(mod, "_get_submissions_for_period", return_value=[]), \
             patch.object(mod, "_aggregate_hours_by_project", return_value={}), \
             patch.object(mod, "_get_biweekly_period_id", return_value=None):
            result = mod._generate_project_summary("period-001")

        assert result is not None
        csv_content = s3.put_object.call_args[1]["Body"].decode("utf-8")
        rows = _parse_csv(csv_content)
        codes = {row["Project Charge Code"] for row in rows}
        assert codes == {"PROJ-A", "PROJ-B", "PROJ-C"}

    def test_inactive_projects_included(self, _mock_boto):
        """Inactive projects are included in the Project Summary.

        Validates: Requirements 10.6
        """
        mod = _mock_boto["mod"]
        s3 = _mock_boto["s3_client"]

        projects = [
            _make_project("PROJ-X", "Inactive Project", Decimal("80"), "Inactive", "Approved"),
        ]

        with patch.object(mod, "_get_all_projects", return_value=projects), \
             patch.object(mod, "_get_submissions_for_period", return_value=[]), \
             patch.object(mod, "_aggregate_hours_by_project", return_value={}), \
             patch.object(mod, "_get_biweekly_period_id", return_value=None):
            result = mod._generate_project_summary("period-001")

        csv_content = s3.put_object.call_args[1]["Body"].decode("utf-8")
        rows = _parse_csv(csv_content)
        assert len(rows) == 1
        assert rows[0]["Project Charge Code"] == "PROJ-X"

    def test_projects_with_zero_hours_included(self, _mock_boto):
        """Projects with no charged hours still appear in the report.

        Validates: Requirements 10.6
        """
        mod = _mock_boto["mod"]
        s3 = _mock_boto["s3_client"]

        projects = [_make_project("PROJ-EMPTY", "Empty Project", Decimal("50"))]

        with patch.object(mod, "_get_all_projects", return_value=projects), \
             patch.object(mod, "_get_submissions_for_period", return_value=[]), \
             patch.object(mod, "_aggregate_hours_by_project", return_value={}), \
             patch.object(mod, "_get_biweekly_period_id", return_value=None):
            mod._generate_project_summary("period-001")

        csv_content = s3.put_object.call_args[1]["Body"].decode("utf-8")
        rows = _parse_csv(csv_content)
        assert len(rows) == 1
        assert rows[0]["Charged Hours"] == "0"
        assert rows[0]["Utilization"] == "0.00"


# ---------------------------------------------------------------------------
# Requirements 9.6, 10.5 — CSV output format matches expected columns
# ---------------------------------------------------------------------------


class TestTCSummaryCSVFormat:
    """TC Summary CSV must have the correct columns and values."""

    def test_csv_columns(self, _mock_boto):
        """CSV header: Name, Chargable Hours, Total Hours,
        Current Period Chargability, YTD Chargability.

        Validates: Requirements 9.6
        """
        mod = _mock_boto["mod"]
        s3 = _mock_boto["s3_client"]

        emp = _make_employee("emp-001", "Alice Smith", "tl-001")
        sub = _make_submission("sub-001", "period-001", "emp-001", "Approved",
                               Decimal("20"), Decimal("40"))

        with patch.object(mod, "_get_supervised_employees", return_value=[emp]), \
             patch.object(mod, "_get_submissions_for_period", return_value=[sub]), \
             patch.object(mod, "_get_ytd_chargeability", return_value=Decimal("55.00")):
            mod._generate_tc_summary("tl-001", "period-001")

        csv_content = s3.put_object.call_args[1]["Body"].decode("utf-8")
        reader = csv.DictReader(io.StringIO(csv_content))
        assert reader.fieldnames == [
            "Name", "Chargable Hours", "Total Hours",
            "Current Period Chargability", "YTD Chargability",
        ]

    def test_csv_row_values(self, _mock_boto):
        """CSV row values are correctly populated.

        Validates: Requirements 9.6
        """
        mod = _mock_boto["mod"]
        s3 = _mock_boto["s3_client"]

        emp = _make_employee("emp-001", "Alice Smith", "tl-001")
        sub = _make_submission("sub-001", "period-001", "emp-001", "Approved",
                               Decimal("30"), Decimal("40"))

        with patch.object(mod, "_get_supervised_employees", return_value=[emp]), \
             patch.object(mod, "_get_submissions_for_period", return_value=[sub]), \
             patch.object(mod, "_get_ytd_chargeability", return_value=Decimal("72.50")):
            mod._generate_tc_summary("tl-001", "period-001")

        csv_content = s3.put_object.call_args[1]["Body"].decode("utf-8")
        rows = _parse_csv(csv_content)
        row = rows[0]
        assert row["Name"] == "Alice Smith"
        assert row["Chargable Hours"] == "30"
        assert row["Total Hours"] == "40"
        assert row["Current Period Chargability"] == "75.00"
        assert row["YTD Chargability"] == "72.50"


class TestProjectSummaryCSVFormat:
    """Project Summary CSV must have the correct columns and values."""

    def test_csv_columns(self, _mock_boto):
        """CSV header: Project Charge Code, Project Name, Planned Hours,
        Charged Hours, Utilization, Current Biweekly Effort.

        Validates: Requirements 10.5
        """
        mod = _mock_boto["mod"]
        s3 = _mock_boto["s3_client"]

        projects = [_make_project("PROJ-001", "Alpha", Decimal("100"))]

        with patch.object(mod, "_get_all_projects", return_value=projects), \
             patch.object(mod, "_get_submissions_for_period", return_value=[]), \
             patch.object(mod, "_aggregate_hours_by_project", return_value={}), \
             patch.object(mod, "_get_biweekly_period_id", return_value=None):
            mod._generate_project_summary("period-001")

        csv_content = s3.put_object.call_args[1]["Body"].decode("utf-8")
        reader = csv.DictReader(io.StringIO(csv_content))
        assert reader.fieldnames == [
            "Project Charge Code", "Project Name", "Planned Hours",
            "Charged Hours", "Utilization", "Current Biweekly Effort",
        ]

    def test_csv_row_values(self, _mock_boto):
        """CSV row values are correctly populated with hours and utilization.

        Validates: Requirements 10.5
        """
        mod = _mock_boto["mod"]
        s3 = _mock_boto["s3_client"]

        projects = [_make_project("PROJ-001", "Alpha", Decimal("200"))]
        project_hours = {"PROJ-001": Decimal("50")}
        biweekly_hours = {"PROJ-001": Decimal("25")}

        with patch.object(mod, "_get_all_projects", return_value=projects), \
             patch.object(mod, "_get_submissions_for_period", return_value=[
                 _make_submission("sub-001", "period-001", "emp-001", "Approved")
             ]), \
             patch.object(mod, "_aggregate_hours_by_project",
                          return_value=project_hours), \
             patch.object(mod, "_get_biweekly_period_id", return_value="bw-001"), \
             patch.object(mod, "_get_biweekly_effort", return_value=biweekly_hours):
            mod._generate_project_summary("period-001")

        csv_content = s3.put_object.call_args[1]["Body"].decode("utf-8")
        rows = _parse_csv(csv_content)
        row = rows[0]
        assert row["Project Charge Code"] == "PROJ-001"
        assert row["Project Name"] == "Alpha"
        assert row["Planned Hours"] == "200"
        assert row["Charged Hours"] == "50"
        assert row["Utilization"] == "25.00"
        assert row["Current Biweekly Effort"] == "25"


# ---------------------------------------------------------------------------
# S3 storage with correct key prefix
# ---------------------------------------------------------------------------


class TestS3StorageKeyPrefix:
    """Reports must be stored in S3 with the correct key prefix pattern."""

    def test_tc_summary_key_prefix(self, _mock_boto):
        """TC Summary stored under reports/tc-summary/{periodId}/{timestamp}.csv.

        Validates: Requirements 9.6
        """
        mod = _mock_boto["mod"]
        s3 = _mock_boto["s3_client"]

        emp = _make_employee("emp-001", "Alice Smith", "tl-001")
        sub = _make_submission("sub-001", "period-abc", "emp-001", "Approved",
                               Decimal("20"), Decimal("40"))

        with patch.object(mod, "_get_supervised_employees", return_value=[emp]), \
             patch.object(mod, "_get_submissions_for_period", return_value=[sub]), \
             patch.object(mod, "_get_ytd_chargeability", return_value=Decimal("0")):
            result = mod._generate_tc_summary("tl-001", "period-abc")

        assert result.startswith("reports/tc-summary/period-abc/")
        assert result.endswith(".csv")
        put_kwargs = s3.put_object.call_args[1]
        assert put_kwargs["Bucket"] == "report-bucket"
        assert put_kwargs["Key"] == result
        assert put_kwargs["ContentType"] == "text/csv"

    def test_project_summary_key_prefix(self, _mock_boto):
        """Project Summary stored under reports/project-summary/{periodId}/{timestamp}.csv.

        Validates: Requirements 10.5
        """
        mod = _mock_boto["mod"]
        s3 = _mock_boto["s3_client"]

        projects = [_make_project("PROJ-001", "Alpha", Decimal("100"))]

        with patch.object(mod, "_get_all_projects", return_value=projects), \
             patch.object(mod, "_get_submissions_for_period", return_value=[]), \
             patch.object(mod, "_aggregate_hours_by_project", return_value={}), \
             patch.object(mod, "_get_biweekly_period_id", return_value=None):
            result = mod._generate_project_summary("period-xyz")

        assert result.startswith("reports/project-summary/period-xyz/")
        assert result.endswith(".csv")
        put_kwargs = s3.put_object.call_args[1]
        assert put_kwargs["Bucket"] == "report-bucket"
        assert put_kwargs["Key"] == result
        assert put_kwargs["ContentType"] == "text/csv"

    def test_s3_body_is_utf8_bytes(self, _mock_boto):
        """The CSV content uploaded to S3 is UTF-8 encoded bytes.

        Validates: Requirements 9.6
        """
        mod = _mock_boto["mod"]
        s3 = _mock_boto["s3_client"]

        emp = _make_employee("emp-001", "Alice Smith", "tl-001")
        sub = _make_submission("sub-001", "period-001", "emp-001", "Approved",
                               Decimal("10"), Decimal("20"))

        with patch.object(mod, "_get_supervised_employees", return_value=[emp]), \
             patch.object(mod, "_get_submissions_for_period", return_value=[sub]), \
             patch.object(mod, "_get_ytd_chargeability", return_value=Decimal("0")):
            mod._generate_tc_summary("tl-001", "period-001")

        body = s3.put_object.call_args[1]["Body"]
        assert isinstance(body, bytes)
        body.decode("utf-8")  # Should not raise


# ---------------------------------------------------------------------------
# Stream event routing
# ---------------------------------------------------------------------------


class TestStreamEventRouting:
    """The handler should only process stream records for Approved/Locked."""

    def test_approved_transition_triggers_reports(self, _mock_boto):
        """A Submitted->Approved transition triggers both reports.

        Validates: Requirements 9.5
        """
        mod = _mock_boto["mod"]
        record = _make_stream_record(new_status="Approved", old_status="Submitted")

        with patch.object(mod, "_get_employee_supervisor_id", return_value="tl-001"), \
             patch.object(mod, "_generate_tc_summary") as mock_tc, \
             patch.object(mod, "_generate_project_summary") as mock_proj:
            result = mod.handler({"Records": [record]}, None)

        assert result["processedRecords"] == 1
        mock_tc.assert_called_once_with("tl-001", "period-001")
        mock_proj.assert_called_once_with("period-001")

    def test_locked_transition_triggers_reports(self, _mock_boto):
        """A Draft->Locked transition triggers both reports.

        Validates: Requirements 9.5
        """
        mod = _mock_boto["mod"]
        record = _make_stream_record(new_status="Locked", old_status="Draft")

        with patch.object(mod, "_get_employee_supervisor_id", return_value="tl-001"), \
             patch.object(mod, "_generate_tc_summary") as mock_tc, \
             patch.object(mod, "_generate_project_summary") as mock_proj:
            result = mod.handler({"Records": [record]}, None)

        assert result["processedRecords"] == 1
        mock_tc.assert_called_once()
        mock_proj.assert_called_once()

    def test_draft_status_does_not_trigger(self, _mock_boto):
        """A transition to Draft does not trigger report generation."""
        mod = _mock_boto["mod"]
        record = _make_stream_record(new_status="Draft", old_status="Rejected")

        with patch.object(mod, "_generate_tc_summary") as mock_tc, \
             patch.object(mod, "_generate_project_summary") as mock_proj:
            result = mod.handler({"Records": [record]}, None)

        assert result["processedRecords"] == 0
        mock_tc.assert_not_called()
        mock_proj.assert_not_called()

    def test_same_status_modify_skipped(self, _mock_boto):
        """A MODIFY where old and new status are both Approved is skipped."""
        mod = _mock_boto["mod"]
        record = _make_stream_record(
            new_status="Approved", old_status="Approved", event_name="MODIFY",
        )

        with patch.object(mod, "_generate_tc_summary") as mock_tc, \
             patch.object(mod, "_generate_project_summary") as mock_proj:
            result = mod.handler({"Records": [record]}, None)

        assert result["processedRecords"] == 0
        mock_tc.assert_not_called()
        mock_proj.assert_not_called()
