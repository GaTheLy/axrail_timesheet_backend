"""Unit tests for Deadline Enforcement Lambda.

Validates: Requirements 8.1, 8.2, 8.4
"""

import os
import sys
from decimal import Decimal
from unittest.mock import MagicMock, patch, call

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lambdas"))

os.environ.setdefault("PERIODS_TABLE", "PeriodsTable")
os.environ.setdefault("SUBMISSIONS_TABLE", "SubmissionsTable")
os.environ.setdefault("USERS_TABLE", "UsersTable")


def _make_period(
    period_id="period-001",
    submission_deadline="2025-01-10T23:59:59+00:00",
    is_locked=False,
    period_string="2025-01-04 to 2025-01-10",
):
    """Build a timesheet period item."""
    return {
        "periodId": period_id,
        "startDate": "2025-01-04",
        "endDate": "2025-01-10",
        "submissionDeadline": submission_deadline,
        "periodString": period_string,
        "isLocked": is_locked,
    }


def _make_submission(
    submission_id="sub-001",
    period_id="period-001",
    employee_id="emp-001",
    status="Draft",
):
    """Build a timesheet submission item."""
    return {
        "submissionId": submission_id,
        "periodId": period_id,
        "employeeId": employee_id,
        "status": status,
        "archived": False,
        "totalHours": Decimal("40"),
        "chargeableHours": Decimal("32"),
    }


def _make_employee(user_id="emp-001"):
    """Build an employee user item."""
    return {
        "userId": user_id,
        "role": "Employee",
        "fullName": f"Employee {user_id}",
        "email": f"{user_id}@example.com",
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _mock_boto(monkeypatch):
    """Patch boto3.resource used at module level in the deadline enforcement handler."""
    mock_periods_table = MagicMock()
    mock_submissions_table = MagicMock()
    mock_users_table = MagicMock()

    def _table_router(name):
        mapping = {
            "PeriodsTable": mock_periods_table,
            "SubmissionsTable": mock_submissions_table,
            "UsersTable": mock_users_table,
        }
        return mapping.get(name, MagicMock())

    mock_dynamodb = MagicMock()
    mock_dynamodb.Table.side_effect = _table_router

    # Defaults — no expired periods, no submissions, no employees
    mock_periods_table.scan.return_value = {"Items": []}
    mock_submissions_table.query.return_value = {"Items": []}
    mock_submissions_table.update_item.return_value = {}
    mock_submissions_table.put_item.return_value = {}
    mock_users_table.scan.return_value = {"Items": []}
    mock_periods_table.update_item.return_value = {}

    with patch("boto3.resource", return_value=mock_dynamodb):
        # Clear cached module so module-level globals pick up mocks
        for mod_name in list(sys.modules):
            if "deadline_enforcement" in mod_name:
                del sys.modules[mod_name]

        from lambdas.deadline_enforcement import handler as de_mod

        de_mod.dynamodb = mock_dynamodb

        yield {
            "de_mod": de_mod,
            "periods_table": mock_periods_table,
            "submissions_table": mock_submissions_table,
            "users_table": mock_users_table,
        }


# ---------------------------------------------------------------------------
# Requirement 8.1 — Draft submissions are locked after deadline
# ---------------------------------------------------------------------------


class TestLockDraftSubmissions:
    """Draft submissions should be updated to Locked when deadline passes."""

    def test_draft_submission_locked_after_deadline(self, _mock_boto):
        mod = _mock_boto["de_mod"]
        sub_table = _mock_boto["submissions_table"]

        draft_sub = _make_submission(
            submission_id="sub-draft-001",
            period_id="period-001",
            employee_id="emp-001",
            status="Draft",
        )

        # Patch internal helpers to control behavior precisely
        with patch.object(mod, "_get_expired_unlocked_periods", return_value=[_make_period()]), \
             patch.object(mod, "_query_submissions_by_status") as mock_query, \
             patch.object(mod, "_get_all_employees", return_value=[_make_employee("emp-001")]), \
             patch.object(mod, "_get_employee_ids_with_submission", return_value={"emp-001"}), \
             patch.object(mod, "_mark_period_locked"):

            mock_query.side_effect = lambda pid, status: [draft_sub] if status == "Draft" else []

            mod.handler({}, None)

        # Verify update_item was called to lock the Draft submission
        sub_table.update_item.assert_called_once()
        call_kwargs = sub_table.update_item.call_args[1]
        assert call_kwargs["Key"] == {"submissionId": "sub-draft-001"}
        assert call_kwargs["ExpressionAttributeValues"][":locked"] == "Locked"

    def test_multiple_draft_submissions_all_locked(self, _mock_boto):
        mod = _mock_boto["de_mod"]
        sub_table = _mock_boto["submissions_table"]

        draft_subs = [
            _make_submission("sub-d1", "period-001", "emp-001", "Draft"),
            _make_submission("sub-d2", "period-001", "emp-002", "Draft"),
        ]

        with patch.object(mod, "_get_expired_unlocked_periods", return_value=[_make_period()]), \
             patch.object(mod, "_query_submissions_by_status") as mock_query, \
             patch.object(mod, "_get_all_employees", return_value=[
                 _make_employee("emp-001"), _make_employee("emp-002")
             ]), \
             patch.object(mod, "_get_employee_ids_with_submission", return_value={"emp-001", "emp-002"}), \
             patch.object(mod, "_mark_period_locked"):

            mock_query.side_effect = lambda pid, status: draft_subs if status == "Draft" else []

            mod.handler({}, None)

        locked_ids = {
            c[1]["Key"]["submissionId"]
            for c in sub_table.update_item.call_args_list
        }
        assert "sub-d1" in locked_ids
        assert "sub-d2" in locked_ids


# ---------------------------------------------------------------------------
# Requirement 8.1 — Submitted submissions are locked after deadline
# ---------------------------------------------------------------------------


class TestLockSubmittedSubmissions:
    """Submitted submissions should be updated to Locked when deadline passes."""

    def test_submitted_submission_locked_after_deadline(self, _mock_boto):
        mod = _mock_boto["de_mod"]
        sub_table = _mock_boto["submissions_table"]

        submitted_sub = _make_submission(
            submission_id="sub-submitted-001",
            period_id="period-001",
            employee_id="emp-001",
            status="Submitted",
        )

        with patch.object(mod, "_get_expired_unlocked_periods", return_value=[_make_period()]), \
             patch.object(mod, "_query_submissions_by_status") as mock_query, \
             patch.object(mod, "_get_all_employees", return_value=[_make_employee("emp-001")]), \
             patch.object(mod, "_get_employee_ids_with_submission", return_value={"emp-001"}), \
             patch.object(mod, "_mark_period_locked"):

            mock_query.side_effect = lambda pid, status: [submitted_sub] if status == "Submitted" else []

            mod.handler({}, None)

        sub_table.update_item.assert_called_once()
        call_kwargs = sub_table.update_item.call_args[1]
        assert call_kwargs["Key"] == {"submissionId": "sub-submitted-001"}
        assert call_kwargs["ExpressionAttributeValues"][":locked"] == "Locked"

    def test_draft_and_submitted_both_locked(self, _mock_boto):
        """Both Draft and Submitted submissions should be locked."""
        mod = _mock_boto["de_mod"]
        sub_table = _mock_boto["submissions_table"]

        draft_sub = _make_submission("sub-d1", "period-001", "emp-001", "Draft")
        submitted_sub = _make_submission("sub-s1", "period-001", "emp-002", "Submitted")

        with patch.object(mod, "_get_expired_unlocked_periods", return_value=[_make_period()]), \
             patch.object(mod, "_query_submissions_by_status") as mock_query, \
             patch.object(mod, "_get_all_employees", return_value=[
                 _make_employee("emp-001"), _make_employee("emp-002")
             ]), \
             patch.object(mod, "_get_employee_ids_with_submission", return_value={"emp-001", "emp-002"}), \
             patch.object(mod, "_mark_period_locked"):

            def _route(pid, status):
                if status == "Draft":
                    return [draft_sub]
                if status == "Submitted":
                    return [submitted_sub]
                return []

            mock_query.side_effect = _route

            mod.handler({}, None)

        locked_ids = {
            c[1]["Key"]["submissionId"]
            for c in sub_table.update_item.call_args_list
        }
        assert "sub-d1" in locked_ids
        assert "sub-s1" in locked_ids


# ---------------------------------------------------------------------------
# Requirement 8.4 — Missing submissions created as Locked with zero hours
# ---------------------------------------------------------------------------


class TestCreateMissingLockedSubmissions:
    """Employees without a submission get a Locked submission with zero hours."""

    def test_missing_employee_gets_locked_submission(self, _mock_boto):
        mod = _mock_boto["de_mod"]
        sub_table = _mock_boto["submissions_table"]

        with patch.object(mod, "_get_expired_unlocked_periods", return_value=[_make_period()]), \
             patch.object(mod, "_query_submissions_by_status", return_value=[]), \
             patch.object(mod, "_get_all_employees", return_value=[
                 _make_employee("emp-001"), _make_employee("emp-002")
             ]), \
             patch.object(mod, "_get_employee_ids_with_submission", return_value={"emp-001"}), \
             patch.object(mod, "_mark_period_locked"):

            mod.handler({}, None)

        # Only emp-002 is missing a submission
        sub_table.put_item.assert_called_once()
        created_item = sub_table.put_item.call_args[1]["Item"]
        assert created_item["employeeId"] == "emp-002"
        assert created_item["periodId"] == "period-001"
        assert created_item["status"] == "Locked"
        assert created_item["totalHours"] == Decimal("0")
        assert created_item["chargeableHours"] == Decimal("0")

    def test_multiple_missing_employees_all_get_locked(self, _mock_boto):
        mod = _mock_boto["de_mod"]
        sub_table = _mock_boto["submissions_table"]

        with patch.object(mod, "_get_expired_unlocked_periods", return_value=[_make_period()]), \
             patch.object(mod, "_query_submissions_by_status", return_value=[]), \
             patch.object(mod, "_get_all_employees", return_value=[
                 _make_employee("emp-001"),
                 _make_employee("emp-002"),
                 _make_employee("emp-003"),
             ]), \
             patch.object(mod, "_get_employee_ids_with_submission", return_value=set()), \
             patch.object(mod, "_mark_period_locked"):

            mod.handler({}, None)

        assert sub_table.put_item.call_count == 3
        created_employee_ids = {
            c[1]["Item"]["employeeId"]
            for c in sub_table.put_item.call_args_list
        }
        assert created_employee_ids == {"emp-001", "emp-002", "emp-003"}

        # All created submissions should be Locked with zero hours
        for c in sub_table.put_item.call_args_list:
            item = c[1]["Item"]
            assert item["status"] == "Locked"
            assert item["totalHours"] == Decimal("0")
            assert item["chargeableHours"] == Decimal("0")

    def test_no_missing_employees_no_put_item(self, _mock_boto):
        """When all employees have submissions, no new ones are created."""
        mod = _mock_boto["de_mod"]
        sub_table = _mock_boto["submissions_table"]

        with patch.object(mod, "_get_expired_unlocked_periods", return_value=[_make_period()]), \
             patch.object(mod, "_query_submissions_by_status", return_value=[]), \
             patch.object(mod, "_get_all_employees", return_value=[_make_employee("emp-001")]), \
             patch.object(mod, "_get_employee_ids_with_submission", return_value={"emp-001"}), \
             patch.object(mod, "_mark_period_locked"):

            mod.handler({}, None)

        sub_table.put_item.assert_not_called()


# ---------------------------------------------------------------------------
# Requirement 8.1 — Approved submissions are NOT modified
# ---------------------------------------------------------------------------


class TestApprovedSubmissionsNotModified:
    """Already Approved submissions should not be changed by deadline enforcement."""

    def test_approved_submission_not_locked(self, _mock_boto):
        """The handler only queries Draft and Submitted — Approved is never touched."""
        mod = _mock_boto["de_mod"]
        sub_table = _mock_boto["submissions_table"]

        with patch.object(mod, "_get_expired_unlocked_periods", return_value=[_make_period()]), \
             patch.object(mod, "_query_submissions_by_status", return_value=[]), \
             patch.object(mod, "_get_all_employees", return_value=[_make_employee("emp-001")]), \
             patch.object(mod, "_get_employee_ids_with_submission", return_value={"emp-001"}), \
             patch.object(mod, "_mark_period_locked"):

            mod.handler({}, None)

        # No submissions should be updated (Draft/Submitted queries returned empty)
        sub_table.update_item.assert_not_called()
        # Employee already has a submission, so no put_item either
        sub_table.put_item.assert_not_called()

    def test_mix_of_approved_and_draft_only_draft_locked(self, _mock_boto):
        """Approved stays untouched while Draft gets locked."""
        mod = _mock_boto["de_mod"]
        sub_table = _mock_boto["submissions_table"]

        draft_sub = _make_submission("sub-d1", "period-001", "emp-001", "Draft")

        with patch.object(mod, "_get_expired_unlocked_periods", return_value=[_make_period()]), \
             patch.object(mod, "_query_submissions_by_status") as mock_query, \
             patch.object(mod, "_get_all_employees", return_value=[
                 _make_employee("emp-001"), _make_employee("emp-002")
             ]), \
             patch.object(mod, "_get_employee_ids_with_submission", return_value={"emp-001", "emp-002"}), \
             patch.object(mod, "_mark_period_locked"):

            # Only Draft query returns a result; Submitted returns empty
            # Approved is never queried by the handler
            mock_query.side_effect = lambda pid, status: [draft_sub] if status == "Draft" else []

            mod.handler({}, None)

        # Only the Draft submission should be updated
        assert sub_table.update_item.call_count == 1
        call_kwargs = sub_table.update_item.call_args[1]
        assert call_kwargs["Key"] == {"submissionId": "sub-d1"}
        assert call_kwargs["ExpressionAttributeValues"][":locked"] == "Locked"


# ---------------------------------------------------------------------------
# Period locking and edge cases
# ---------------------------------------------------------------------------


class TestPeriodLocking:
    """The period itself should be marked as isLocked = true."""

    def test_period_marked_as_locked(self, _mock_boto):
        mod = _mock_boto["de_mod"]
        periods_table = _mock_boto["periods_table"]

        with patch.object(mod, "_get_expired_unlocked_periods", return_value=[_make_period()]), \
             patch.object(mod, "_lock_submissions_for_period"), \
             patch.object(mod, "_create_missing_locked_submissions"):

            mod.handler({}, None)

        periods_table.update_item.assert_called_once()
        call_kwargs = periods_table.update_item.call_args[1]
        assert call_kwargs["Key"] == {"periodId": "period-001"}
        assert call_kwargs["ExpressionAttributeValues"][":locked"] is True

    def test_no_expired_periods_returns_zero(self, _mock_boto):
        mod = _mock_boto["de_mod"]

        with patch.object(mod, "_get_expired_unlocked_periods", return_value=[]):
            result = mod.handler({}, None)

        assert result == {"lockedPeriods": 0}

    def test_handler_returns_locked_period_count(self, _mock_boto):
        mod = _mock_boto["de_mod"]

        periods = [
            _make_period(period_id="period-001"),
            _make_period(period_id="period-002"),
        ]

        with patch.object(mod, "_get_expired_unlocked_periods", return_value=periods), \
             patch.object(mod, "_lock_submissions_for_period"), \
             patch.object(mod, "_create_missing_locked_submissions"), \
             patch.object(mod, "_mark_period_locked"):

            result = mod.handler({}, None)

        assert result == {"lockedPeriods": 2}
