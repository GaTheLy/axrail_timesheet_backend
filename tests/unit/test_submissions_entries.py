"""Unit tests for Submission & Entry resolvers.

Validates: Requirements 6.4, 6.5, 6.6, 6.7, 6.9, 6.10, 6.11
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
    """Patch boto3.resource used at module level in both handlers."""
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

        from lambdas.submissions import handler as sub_mod
        from lambdas.entries import handler as ent_mod

        sub_mod.dynamodb = mock_dynamodb
        ent_mod.dynamodb = mock_dynamodb

        yield {
            "sub_mod": sub_mod,
            "ent_mod": ent_mod,
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
        mod = _mock_boto["sub_mod"]
        event = _make_event(arguments={"periodId": "period-001"})
        result = mod.create_timesheet_submission(event)
        assert result["status"] == "Draft"
        assert result["periodId"] == "period-001"

    def test_duplicate_submission_rejected(self, _mock_boto):
        mod = _mock_boto["sub_mod"]
        table = _mock_boto["submissions_table"]
        # Simulate existing submission for this employee+period
        table.query.return_value = {
            "Items": [_make_submission()]
        }
        event = _make_event(arguments={"periodId": "period-001"})
        with pytest.raises(ValueError, match="already exists"):
            mod.create_timesheet_submission(event)


# ---------------------------------------------------------------------------
# Requirement 6.4 — Status transition Draft to Submitted
# ---------------------------------------------------------------------------


class TestSubmitTimesheet:
    """Employee can submit a Draft timesheet, transitioning to Submitted."""

    def test_submit_draft_succeeds(self, _mock_boto):
        mod = _mock_boto["sub_mod"]
        table = _mock_boto["submissions_table"]
        table.get_item.return_value = {"Item": _make_submission(status="Draft")}
        table.update_item.return_value = {
            "Attributes": {**_make_submission(status="Submitted"), "status": "Submitted"}
        }
        event = _make_event(
            field_name="submitTimesheet",
            arguments={"submissionId": "sub-001"},
        )
        result = mod.submit_timesheet(event)
        assert result["status"] == "Submitted"

    def test_submit_rejected_succeeds(self, _mock_boto):
        """A Rejected timesheet can also be resubmitted."""
        mod = _mock_boto["sub_mod"]
        table = _mock_boto["submissions_table"]
        table.get_item.return_value = {"Item": _make_submission(status="Rejected")}
        table.update_item.return_value = {
            "Attributes": {**_make_submission(status="Submitted"), "status": "Submitted"}
        }
        event = _make_event(
            field_name="submitTimesheet",
            arguments={"submissionId": "sub-001"},
        )
        result = mod.submit_timesheet(event)
        assert result["status"] == "Submitted"

    def test_submit_approved_rejected(self, _mock_boto):
        """Cannot submit a timesheet that is already Approved."""
        mod = _mock_boto["sub_mod"]
        table = _mock_boto["submissions_table"]
        table.get_item.return_value = {"Item": _make_submission(status="Approved")}
        event = _make_event(
            field_name="submitTimesheet",
            arguments={"submissionId": "sub-001"},
        )
        with pytest.raises(ValueError, match="Cannot submit"):
            mod.submit_timesheet(event)

    def test_submit_locked_rejected(self, _mock_boto):
        """Cannot submit a timesheet that is Locked."""
        mod = _mock_boto["sub_mod"]
        table = _mock_boto["submissions_table"]
        table.get_item.return_value = {"Item": _make_submission(status="Locked")}
        event = _make_event(
            field_name="submitTimesheet",
            arguments={"submissionId": "sub-001"},
        )
        with pytest.raises(ValueError, match="Cannot submit"):
            mod.submit_timesheet(event)


# ---------------------------------------------------------------------------
# Requirements 6.5, 6.6 — Entry editing blocked when Submitted or Locked
# ---------------------------------------------------------------------------


class TestEntryEditingBlocked:
    """Entries cannot be added/updated/removed when submission is Submitted or Locked."""

    @pytest.mark.parametrize("status", ["Submitted", "Locked", "Approved"])
    def test_add_entry_blocked_non_editable_status(self, _mock_boto, status):
        mod = _mock_boto["ent_mod"]
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

    @pytest.mark.parametrize("status", ["Submitted", "Locked", "Approved"])
    def test_update_entry_blocked_non_editable_status(self, _mock_boto, status):
        mod = _mock_boto["ent_mod"]
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

    @pytest.mark.parametrize("status", ["Submitted", "Locked", "Approved"])
    def test_remove_entry_blocked_non_editable_status(self, _mock_boto, status):
        mod = _mock_boto["ent_mod"]
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

    @pytest.mark.parametrize("status", ["Draft", "Rejected"])
    def test_add_entry_allowed_editable_status(self, _mock_boto, status):
        mod = _mock_boto["ent_mod"]
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
        mod = _mock_boto["ent_mod"]
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
        mod = _mock_boto["ent_mod"]
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
        mod = _mock_boto["sub_mod"]
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
        mod = _mock_boto["sub_mod"]
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
        mod = _mock_boto["sub_mod"]
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
        mod = _mock_boto["sub_mod"]
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

    def test_submit_other_employee_forbidden(self, _mock_boto):
        """An employee cannot submit another employee's timesheet."""
        mod = _mock_boto["sub_mod"]
        table = _mock_boto["submissions_table"]
        table.get_item.return_value = {
            "Item": _make_submission(employee_id="emp-002", status="Draft")
        }
        event = _make_event(
            field_name="submitTimesheet",
            user_id="emp-001",
            arguments={"submissionId": "sub-001"},
        )
        with pytest.raises(Exception, match="only submit your own"):
            mod.submit_timesheet(event)
