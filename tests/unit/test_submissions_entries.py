"""Unit tests for Submission & Entry resolvers.

Validates: Requirements 6.5, 6.7, 6.9, 6.10, 6.11
Note: Manual submit (Draft→Submitted) no longer exists as a user action.
      Auto-submit is handled by deadline_enforcement Lambda only.
      Only two statuses exist: Draft and Submitted.
"""

import os
import sys
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lambdas"))

os.environ.setdefault("SUBMISSIONS_TABLE", "SubmissionsTable")
os.environ.setdefault("ENTRIES_TABLE", "EntriesTable")
os.environ.setdefault("PROJECTS_TABLE", "ProjectsTable")


def _make_event(
    field_name="createTimesheetSubmission",
    user_type="user",
    role="Employee",
    user_id="emp-001",
    arguments=None,
):
    """Build a minimal AppSync event with Cognito claims."""
    return {
        "info": {"fieldName": field_name},
        "identity": {
            "claims": {
                "sub": user_id,
                "custom:userType": user_type,
                "custom:role": role,
                "email": "emp@example.com",
                "custom:departmentId": "dept-1",
                "custom:positionId": "pos-1",
            }
        },
        "arguments": arguments or {},
    }


def _make_submission(
    submission_id="sub-001",
    employee_id="emp-001",
    period_id="period-001",
    status="Draft",
    archived=False,
):
    """Build a submission item dict."""
    return {
        "submissionId": submission_id,
        "periodId": period_id,
        "employeeId": employee_id,
        "status": status,
        "archived": archived,
        "totalHours": Decimal("0"),
        "chargeableHours": Decimal("0"),
    }


def _make_entry_input(project_code="PROJ-001", hours=None):
    """Build a TimesheetEntryInput dict with daily hours."""
    if hours is None:
        hours = {d: 1.0 for d in (
            "saturday", "sunday", "monday", "tuesday",
            "wednesday", "thursday", "friday",
        )}
    return {"projectCode": project_code, **hours}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _mock_boto(monkeypatch):
    """Patch boto3.resource used at module level in all handlers."""
    mock_submissions_table = MagicMock()
    mock_entries_table = MagicMock()
    mock_projects_table = MagicMock()

    def _table_router(name):
        mapping = {
            "SubmissionsTable": mock_submissions_table,
            "EntriesTable": mock_entries_table,
            "ProjectsTable": mock_projects_table,
        }
        return mapping.get(name, MagicMock())

    mock_dynamodb = MagicMock()
    mock_dynamodb.Table.side_effect = _table_router

    # Default: no existing submissions, no existing entries, approved project
    mock_submissions_table.query.return_value = {"Items": []}
    mock_submissions_table.put_item.return_value = {}
    mock_entries_table.query.return_value = {"Items": [], "Count": 0}
    mock_entries_table.put_item.return_value = {}
    mock_projects_table.query.return_value = {
        "Items": [{"projectCode": "PROJ-001", "approval_status": "Approved"}]
    }

    with patch("boto3.resource", return_value=mock_dynamodb):
        # Clear cached modules so module-level globals pick up mocks
        for mod_name in list(sys.modules):
            if "lambdas.submissions" in mod_name or "lambdas.entries" in mod_name:
                del sys.modules[mod_name]
        # Also clear the bare 'shared_utils' module that entry handlers
        # import via sys.path manipulation
        if "shared_utils" in sys.modules:
            del sys.modules["shared_utils"]

        from lambdas.submissions.CreateTimesheetSubmission import handler as create_sub_mod
        from lambdas.submissions.GetTimesheetSubmission import handler as get_sub_mod
        from lambdas.submissions.ListMySubmissions import handler as list_sub_mod
        from lambdas.entries.AddTimesheetEntry import handler as add_ent_mod
        from lambdas.entries.UpdateTimesheetEntry import handler as update_ent_mod
        from lambdas.entries.RemoveTimesheetEntry import handler as remove_ent_mod

        create_sub_mod.dynamodb = mock_dynamodb
        get_sub_mod.dynamodb = mock_dynamodb
        list_sub_mod.dynamodb = mock_dynamodb
        # The entry handlers import shared_utils as a bare module via sys.path;
        # patch it through the module that was actually loaded
        if "shared_utils" in sys.modules:
            sys.modules["shared_utils"].dynamodb = mock_dynamodb

        yield {
            "create_sub_mod": create_sub_mod,
            "get_sub_mod": get_sub_mod,
            "list_sub_mod": list_sub_mod,
            "add_ent_mod": add_ent_mod,
            "update_ent_mod": update_ent_mod,
            "remove_ent_mod": remove_ent_mod,
            "submissions_table": mock_submissions_table,
            "entries_table": mock_entries_table,
            "projects_table": mock_projects_table,
        }


# ---------------------------------------------------------------------------
# Requirement 6.9 — One submission per employee per period
# ---------------------------------------------------------------------------


class TestOneSubmissionPerPeriod:
    """Enforce that an employee cannot create two submissions for the same period."""

    def test_first_submission_succeeds(self, _mock_boto):
        mod = _mock_boto["create_sub_mod"]
        event = _make_event(arguments={"periodId": "period-001"})
        result = mod.create_timesheet_submission(event)
        assert result["status"] == "Draft"
        assert result["periodId"] == "period-001"

    def test_duplicate_submission_rejected(self, _mock_boto):
        mod = _mock_boto["create_sub_mod"]
        table = _mock_boto["submissions_table"]
        table.query.return_value = {"Items": [_make_submission()]}
        event = _make_event(arguments={"periodId": "period-001"})
        with pytest.raises(ValueError, match="already exists"):
            mod.create_timesheet_submission(event)


# ---------------------------------------------------------------------------
# Requirements 6.5 — Entry editing blocked when Submitted
# ---------------------------------------------------------------------------


class TestEntryEditingBlocked:
    """Entries cannot be added/updated/removed when submission is Submitted."""

    @pytest.mark.parametrize("status", ["Submitted"])
    def test_add_entry_blocked_non_editable_status(self, _mock_boto, status):
        mod = _mock_boto["add_ent_mod"]
        table = _mock_boto["submissions_table"]
        table.get_item.return_value = {"Item": _make_submission(status=status)}
        event = _make_event(
            field_name="addTimesheetEntry",
            arguments={
                "submissionId": "sub-001",
                "input": _make_entry_input(),
            },
        )
        with pytest.raises(ValueError, match="Cannot modify entries"):
            mod.add_timesheet_entry(event)

    @pytest.mark.parametrize("status", ["Submitted"])
    def test_update_entry_blocked_non_editable_status(self, _mock_boto, status):
        mod = _mock_boto["update_ent_mod"]
        sub_table = _mock_boto["submissions_table"]
        ent_table = _mock_boto["entries_table"]
        sub_table.get_item.return_value = {"Item": _make_submission(status=status)}
        ent_table.get_item.return_value = {
            "Item": {
                "entryId": "entry-001",
                "submissionId": "sub-001",
                "projectCode": "PROJ-001",
            }
        }
        event = _make_event(
            field_name="updateTimesheetEntry",
            arguments={
                "entryId": "entry-001",
                "input": _make_entry_input(),
            },
        )
        with pytest.raises(ValueError, match="Cannot modify entries"):
            mod.update_timesheet_entry(event)

    @pytest.mark.parametrize("status", ["Submitted"])
    def test_remove_entry_blocked_non_editable_status(self, _mock_boto, status):
        mod = _mock_boto["remove_ent_mod"]
        sub_table = _mock_boto["submissions_table"]
        ent_table = _mock_boto["entries_table"]
        sub_table.get_item.return_value = {"Item": _make_submission(status=status)}
        ent_table.get_item.return_value = {
            "Item": {
                "entryId": "entry-001",
                "submissionId": "sub-001",
            }
        }
        event = _make_event(
            field_name="removeTimesheetEntry",
            arguments={"entryId": "entry-001"},
        )
        with pytest.raises(ValueError, match="Cannot modify entries"):
            mod.remove_timesheet_entry(event)

    @pytest.mark.parametrize("status", ["Draft"])
    def test_add_entry_allowed_editable_status(self, _mock_boto, status):
        mod = _mock_boto["add_ent_mod"]
        sub_table = _mock_boto["submissions_table"]
        sub_table.get_item.return_value = {"Item": _make_submission(status=status)}
        event = _make_event(
            field_name="addTimesheetEntry",
            arguments={
                "submissionId": "sub-001",
                "input": _make_entry_input(),
            },
        )
        result = mod.add_timesheet_entry(event)
        assert result["projectCode"] == "PROJ-001"


# ---------------------------------------------------------------------------
# Requirement 6.7 — Max 27 entries per submission
# ---------------------------------------------------------------------------


class TestMaxEntries:
    """A submission cannot have more than 27 entries."""

    def test_28th_entry_rejected(self, _mock_boto):
        mod = _mock_boto["add_ent_mod"]
        sub_table = _mock_boto["submissions_table"]
        ent_table = _mock_boto["entries_table"]
        sub_table.get_item.return_value = {"Item": _make_submission(status="Draft")}
        # Simulate 27 existing entries
        ent_table.query.return_value = {"Items": [], "Count": 27}
        event = _make_event(
            field_name="addTimesheetEntry",
            arguments={
                "submissionId": "sub-001",
                "input": _make_entry_input(),
            },
        )
        with pytest.raises(ValueError, match="Maximum allowed is 27"):
            mod.add_timesheet_entry(event)

    def test_27th_entry_allowed(self, _mock_boto):
        mod = _mock_boto["add_ent_mod"]
        sub_table = _mock_boto["submissions_table"]
        ent_table = _mock_boto["entries_table"]
        sub_table.get_item.return_value = {"Item": _make_submission(status="Draft")}
        # Simulate 26 existing entries — 27th should be allowed
        ent_table.query.return_value = {"Items": [], "Count": 26}
        event = _make_event(
            field_name="addTimesheetEntry",
            arguments={
                "submissionId": "sub-001",
                "input": _make_entry_input(),
            },
        )
        result = mod.add_timesheet_entry(event)
        assert result["projectCode"] == "PROJ-001"


# ---------------------------------------------------------------------------
# Requirements 6.10, 6.11 — Employee can only see own submissions
# ---------------------------------------------------------------------------


class TestEmployeeSubmissionAccess:
    """Employees can only view their own submissions."""

    def test_owner_can_view_submission(self, _mock_boto):
        mod = _mock_boto["get_sub_mod"]
        table = _mock_boto["submissions_table"]
        ent_table = _mock_boto["entries_table"]
        table.get_item.return_value = {
            "Item": _make_submission(employee_id="emp-001")
        }
        ent_table.query.return_value = {"Items": []}
        event = _make_event(
            field_name="getTimesheetSubmission",
            user_id="emp-001",
            arguments={"submissionId": "sub-001"},
        )
        result = mod.get_timesheet_submission(event)
        assert result["employeeId"] == "emp-001"

    def test_other_employee_forbidden(self, _mock_boto):
        mod = _mock_boto["get_sub_mod"]
        table = _mock_boto["submissions_table"]
        table.get_item.return_value = {
            "Item": _make_submission(employee_id="emp-002")
        }
        event = _make_event(
            field_name="getTimesheetSubmission",
            user_id="emp-001",
            user_type="user",
            arguments={"submissionId": "sub-001"},
        )
        with pytest.raises(Exception, match="only view your own"):
            mod.get_timesheet_submission(event)

    def test_admin_can_view_any_submission(self, _mock_boto):
        mod = _mock_boto["get_sub_mod"]
        table = _mock_boto["submissions_table"]
        ent_table = _mock_boto["entries_table"]
        table.get_item.return_value = {
            "Item": _make_submission(employee_id="emp-002")
        }
        ent_table.query.return_value = {"Items": []}
        event = _make_event(
            field_name="getTimesheetSubmission",
            user_id="admin-001",
            user_type="admin",
            role="Tech_Lead",
            arguments={"submissionId": "sub-001"},
        )
        result = mod.get_timesheet_submission(event)
        assert result["employeeId"] == "emp-002"

    def test_list_my_submissions_returns_own_only(self, _mock_boto):
        mod = _mock_boto["list_sub_mod"]
        table = _mock_boto["submissions_table"]
        own_sub = _make_submission(employee_id="emp-001")
        table.query.return_value = {"Items": [own_sub]}
        event = _make_event(
            field_name="listMySubmissions",
            user_id="emp-001",
            arguments={},
        )
        result = mod.list_my_submissions(event)
        assert len(result) == 1
        assert result[0]["employeeId"] == "emp-001"
