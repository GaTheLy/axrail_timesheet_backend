"""Unit tests for Timesheet Review resolvers.

Validates: Requirements 7.1, 7.2, 7.4, 7.5
"""

import os
import sys
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lambdas"))

os.environ.setdefault("SUBMISSIONS_TABLE", "SubmissionsTable")
os.environ.setdefault("USERS_TABLE", "UsersTable")


def _make_event(
    field_name="approveTimesheet",
    user_type="admin",
    role="Tech_Lead",
    user_id="reviewer-001",
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
                "email": "reviewer@example.com",
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
    status="Submitted",
):
    """Build a submission item dict."""
    return {
        "submissionId": submission_id,
        "periodId": period_id,
        "employeeId": employee_id,
        "status": status,
        "archived": False,
        "totalHours": Decimal("40"),
        "chargeableHours": Decimal("32"),
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _mock_boto(monkeypatch):
    """Patch boto3.resource used at module level in the reviews handler."""
    mock_submissions_table = MagicMock()
    mock_users_table = MagicMock()

    def _table_router(name):
        mapping = {
            "SubmissionsTable": mock_submissions_table,
            "UsersTable": mock_users_table,
        }
        return mapping.get(name, MagicMock())

    mock_dynamodb = MagicMock()
    mock_dynamodb.Table.side_effect = _table_router

    # Defaults
    mock_submissions_table.get_item.return_value = {
        "Item": _make_submission(status="Submitted")
    }
    mock_submissions_table.update_item.return_value = {
        "Attributes": _make_submission(status="Approved")
    }
    mock_submissions_table.query.return_value = {"Items": []}
    mock_users_table.query.return_value = {"Items": []}

    with patch("boto3.resource", return_value=mock_dynamodb):
        # Clear cached module so module-level globals pick up mocks
        for mod_name in list(sys.modules):
            if "lambdas.reviews" in mod_name:
                del sys.modules[mod_name]

        from lambdas.reviews import handler as rev_mod

        rev_mod.dynamodb = mock_dynamodb

        yield {
            "rev_mod": rev_mod,
            "submissions_table": mock_submissions_table,
            "users_table": mock_users_table,
        }


# ---------------------------------------------------------------------------
# Requirement 7.1 — Approve transitions Submitted → Approved
# ---------------------------------------------------------------------------


class TestApproveTimesheet:
    """Approve a Submitted timesheet, recording approvedBy/approvedAt."""

    def test_approve_submitted_succeeds(self, _mock_boto):
        mod = _mock_boto["rev_mod"]
        table = _mock_boto["submissions_table"]
        table.get_item.return_value = {"Item": _make_submission(status="Submitted")}
        table.update_item.return_value = {
            "Attributes": {
                **_make_submission(status="Approved"),
                "approvedBy": "reviewer-001",
                "approvedAt": "2025-06-01T00:00:00+00:00",
            }
        }
        event = _make_event(
            field_name="approveTimesheet",
            arguments={"submissionId": "sub-001"},
        )
        result = mod.approve_timesheet(event)
        assert result["status"] == "Approved"
        assert result["approvedBy"] == "reviewer-001"
        assert "approvedAt" in result

    def test_approve_calls_update_with_correct_status(self, _mock_boto):
        mod = _mock_boto["rev_mod"]
        table = _mock_boto["submissions_table"]
        table.get_item.return_value = {"Item": _make_submission(status="Submitted")}
        table.update_item.return_value = {
            "Attributes": _make_submission(status="Approved")
        }
        event = _make_event(
            field_name="approveTimesheet",
            arguments={"submissionId": "sub-001"},
        )
        mod.approve_timesheet(event)
        # Verify update_item was called with Approved status
        call_kwargs = table.update_item.call_args[1]
        assert call_kwargs["ExpressionAttributeValues"][":status"] == "Approved"

    def test_approve_by_project_manager_succeeds(self, _mock_boto):
        mod = _mock_boto["rev_mod"]
        table = _mock_boto["submissions_table"]
        table.get_item.return_value = {"Item": _make_submission(status="Submitted")}
        table.update_item.return_value = {
            "Attributes": _make_submission(status="Approved")
        }
        event = _make_event(
            field_name="approveTimesheet",
            role="Project_Manager",
            arguments={"submissionId": "sub-001"},
        )
        result = mod.approve_timesheet(event)
        assert result["status"] == "Approved"


# ---------------------------------------------------------------------------
# Requirement 7.2 — Reject transitions Submitted → Rejected
# ---------------------------------------------------------------------------


class TestRejectTimesheet:
    """Reject a Submitted timesheet, recording updatedBy/updatedAt."""

    def test_reject_submitted_succeeds(self, _mock_boto):
        mod = _mock_boto["rev_mod"]
        table = _mock_boto["submissions_table"]
        table.get_item.return_value = {"Item": _make_submission(status="Submitted")}
        table.update_item.return_value = {
            "Attributes": {
                **_make_submission(status="Rejected"),
                "updatedBy": "reviewer-001",
                "updatedAt": "2025-06-01T00:00:00+00:00",
            }
        }
        event = _make_event(
            field_name="rejectTimesheet",
            arguments={"submissionId": "sub-001"},
        )
        result = mod.reject_timesheet(event)
        assert result["status"] == "Rejected"

    def test_reject_calls_update_with_correct_status(self, _mock_boto):
        mod = _mock_boto["rev_mod"]
        table = _mock_boto["submissions_table"]
        table.get_item.return_value = {"Item": _make_submission(status="Submitted")}
        table.update_item.return_value = {
            "Attributes": _make_submission(status="Rejected")
        }
        event = _make_event(
            field_name="rejectTimesheet",
            arguments={"submissionId": "sub-001"},
        )
        mod.reject_timesheet(event)
        call_kwargs = table.update_item.call_args[1]
        assert call_kwargs["ExpressionAttributeValues"][":status"] == "Rejected"


# ---------------------------------------------------------------------------
# Requirement 7.5 — Invalid status transitions rejected
# ---------------------------------------------------------------------------


class TestInvalidStatusTransitions:
    """Only Submitted → Approved and Submitted → Rejected are valid."""

    @pytest.mark.parametrize("status", ["Draft", "Locked", "Approved", "Rejected"])
    def test_approve_non_submitted_rejected(self, _mock_boto, status):
        mod = _mock_boto["rev_mod"]
        table = _mock_boto["submissions_table"]
        table.get_item.return_value = {"Item": _make_submission(status=status)}
        event = _make_event(
            field_name="approveTimesheet",
            arguments={"submissionId": "sub-001"},
        )
        with pytest.raises(ValueError, match="Cannot transition"):
            mod.approve_timesheet(event)

    @pytest.mark.parametrize("status", ["Draft", "Locked", "Approved", "Rejected"])
    def test_reject_non_submitted_rejected(self, _mock_boto, status):
        mod = _mock_boto["rev_mod"]
        table = _mock_boto["submissions_table"]
        table.get_item.return_value = {"Item": _make_submission(status=status)}
        event = _make_event(
            field_name="rejectTimesheet",
            arguments={"submissionId": "sub-001"},
        )
        with pytest.raises(ValueError, match="Cannot transition"):
            mod.reject_timesheet(event)

    def test_approve_not_found_raises(self, _mock_boto):
        mod = _mock_boto["rev_mod"]
        table = _mock_boto["submissions_table"]
        table.get_item.return_value = {}
        event = _make_event(
            field_name="approveTimesheet",
            arguments={"submissionId": "nonexistent"},
        )
        with pytest.raises(ValueError, match="not found"):
            mod.approve_timesheet(event)

    def test_employee_cannot_approve(self, _mock_boto):
        """An Employee role should be forbidden from approving."""
        mod = _mock_boto["rev_mod"]
        event = _make_event(
            field_name="approveTimesheet",
            user_type="user",
            role="Employee",
            arguments={"submissionId": "sub-001"},
        )
        with pytest.raises(Exception, match="not authorized"):
            mod.approve_timesheet(event)


# ---------------------------------------------------------------------------
# Requirement 7.4 — Reviewer only sees supervised employees' submissions
# ---------------------------------------------------------------------------


class TestListPendingTimesheets:
    """Reviewer sees only Submitted timesheets from supervised employees."""

    def test_returns_supervised_submissions_only(self, _mock_boto):
        mod = _mock_boto["rev_mod"]
        users_table = _mock_boto["users_table"]
        sub_table = _mock_boto["submissions_table"]

        # Reviewer supervises emp-001 and emp-002
        users_table.query.return_value = {
            "Items": [
                {"userId": "emp-001", "supervisorId": "reviewer-001"},
                {"userId": "emp-002", "supervisorId": "reviewer-001"},
            ]
        }

        # Submitted submissions from emp-001, emp-002, and emp-003 (not supervised)
        sub_table.query.return_value = {
            "Items": [
                _make_submission(submission_id="sub-001", employee_id="emp-001"),
                _make_submission(submission_id="sub-002", employee_id="emp-002"),
                _make_submission(submission_id="sub-003", employee_id="emp-003"),
            ]
        }

        event = _make_event(
            field_name="listPendingTimesheets",
            arguments={},
        )
        result = mod.list_pending_timesheets(event)
        employee_ids = {s["employeeId"] for s in result}
        assert employee_ids == {"emp-001", "emp-002"}
        assert len(result) == 2

    def test_returns_empty_when_no_supervised_employees(self, _mock_boto):
        mod = _mock_boto["rev_mod"]
        users_table = _mock_boto["users_table"]
        users_table.query.return_value = {"Items": []}

        event = _make_event(
            field_name="listPendingTimesheets",
            arguments={},
        )
        result = mod.list_pending_timesheets(event)
        assert result == []

    def test_returns_empty_when_no_submitted_timesheets(self, _mock_boto):
        mod = _mock_boto["rev_mod"]
        users_table = _mock_boto["users_table"]
        sub_table = _mock_boto["submissions_table"]

        users_table.query.return_value = {
            "Items": [{"userId": "emp-001", "supervisorId": "reviewer-001"}]
        }
        sub_table.query.return_value = {"Items": []}

        event = _make_event(
            field_name="listPendingTimesheets",
            arguments={},
        )
        result = mod.list_pending_timesheets(event)
        assert result == []

    def test_employee_cannot_list_pending(self, _mock_boto):
        """An Employee role should be forbidden from listing pending timesheets."""
        mod = _mock_boto["rev_mod"]
        event = _make_event(
            field_name="listPendingTimesheets",
            user_type="user",
            role="Employee",
            arguments={},
        )
        with pytest.raises(Exception, match="not authorized"):
            mod.list_pending_timesheets(event)
