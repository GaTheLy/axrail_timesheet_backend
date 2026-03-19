"""Unit tests for Deadline Enforcement Lambda.

The deadline enforcement handler now:
  1. Auto-submits all Draft submissions (Draft -> Submitted)
  2. Creates Submitted submissions with zero hours for missing employees
  3. Sends under-40-hours email notifications to employees
  4. Marks the period as isLocked = true

Validates the new automated flow (no manual approval/rejection).
"""

import os
import sys
from decimal import Decimal
from unittest.mock import MagicMock, patch, call

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lambdas"))

os.environ.setdefault("PERIODS_TABLE", "PeriodsTable")
os.environ.setdefault("SUBMISSIONS_TABLE", "SubmissionsTable")
os.environ.setdefault("ENTRIES_TABLE", "EntriesTable")
os.environ.setdefault("USERS_TABLE", "UsersTable")
os.environ.setdefault("SES_FROM_EMAIL", "noreply@example.com")


def _make_period(
    period_id="period-001",
    submission_deadline="2025-01-10T09:00:00+00:00",
    is_locked=False,
    period_string="Jan 06 - Jan 10, 2025",
):
    return {
        "periodId": period_id,
        "startDate": "2025-01-06",
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
    mock_periods_table = MagicMock()
    mock_submissions_table = MagicMock()
    mock_entries_table = MagicMock()
    mock_users_table = MagicMock()

    def _table_router(name):
        mapping = {
            "PeriodsTable": mock_periods_table,
            "SubmissionsTable": mock_submissions_table,
            "EntriesTable": mock_entries_table,
            "UsersTable": mock_users_table,
        }
        return mapping.get(name, MagicMock())

    mock_dynamodb = MagicMock()
    mock_dynamodb.Table.side_effect = _table_router

    mock_ses = MagicMock()

    mock_periods_table.scan.return_value = {"Items": []}
    mock_submissions_table.query.return_value = {"Items": []}
    mock_submissions_table.update_item.return_value = {}
    mock_submissions_table.put_item.return_value = {}
    mock_entries_table.query.return_value = {"Items": []}
    mock_users_table.scan.return_value = {"Items": []}
    mock_users_table.get_item.return_value = {"Item": None}
    mock_periods_table.update_item.return_value = {}

    with patch("boto3.resource", return_value=mock_dynamodb), \
         patch("boto3.client", return_value=mock_ses):
        for mod_name in list(sys.modules):
            if "deadline_enforcement" in mod_name:
                del sys.modules[mod_name]

        from lambdas.deadline_enforcement import handler as de_mod

        de_mod.dynamodb = mock_dynamodb
        de_mod.ses_client = mock_ses

        yield {
            "de_mod": de_mod,
            "periods_table": mock_periods_table,
            "submissions_table": mock_submissions_table,
            "entries_table": mock_entries_table,
            "users_table": mock_users_table,
            "ses_client": mock_ses,
        }


# ---------------------------------------------------------------------------
# Draft submissions auto-submitted (Draft -> Submitted)
# ---------------------------------------------------------------------------


class TestAutoSubmitDraftSubmissions:
    """Draft submissions should be auto-submitted to Submitted at deadline."""

    def test_draft_submission_auto_submitted(self, _mock_boto):
        mod = _mock_boto["de_mod"]
        sub_table = _mock_boto["submissions_table"]

        draft_sub = _make_submission("sub-d1", "period-001", "emp-001", "Draft")

        with patch.object(mod, "_get_expired_unlocked_periods", return_value=[_make_period()]), \
             patch.object(mod, "_query_submissions_by_status") as mock_query, \
             patch.object(mod, "_get_all_employees", return_value=[_make_employee("emp-001")]), \
             patch.object(mod, "_get_employee_ids_with_submission", return_value={"emp-001"}), \
             patch.object(mod, "_send_under_40_hours_notifications"), \
             patch.object(mod, "_mark_period_locked"):

            mock_query.side_effect = lambda pid, status: [draft_sub] if status == "Draft" else []
            mod.handler({}, None)

        sub_table.update_item.assert_called_once()
        call_kwargs = sub_table.update_item.call_args[1]
        assert call_kwargs["Key"] == {"submissionId": "sub-d1"}
        assert call_kwargs["ExpressionAttributeValues"][":submitted"] == "Submitted"

    def test_multiple_drafts_all_auto_submitted(self, _mock_boto):
        mod = _mock_boto["de_mod"]
        sub_table = _mock_boto["submissions_table"]

        drafts = [
            _make_submission("sub-d1", "period-001", "emp-001", "Draft"),
            _make_submission("sub-d2", "period-001", "emp-002", "Draft"),
        ]

        with patch.object(mod, "_get_expired_unlocked_periods", return_value=[_make_period()]), \
             patch.object(mod, "_query_submissions_by_status") as mock_query, \
             patch.object(mod, "_get_all_employees", return_value=[
                 _make_employee("emp-001"), _make_employee("emp-002")
             ]), \
             patch.object(mod, "_get_employee_ids_with_submission", return_value={"emp-001", "emp-002"}), \
             patch.object(mod, "_send_under_40_hours_notifications"), \
             patch.object(mod, "_mark_period_locked"):

            mock_query.side_effect = lambda pid, status: drafts if status == "Draft" else []
            mod.handler({}, None)

        submitted_ids = {
            c[1]["Key"]["submissionId"]
            for c in sub_table.update_item.call_args_list
        }
        assert submitted_ids == {"sub-d1", "sub-d2"}


# ---------------------------------------------------------------------------
# Missing submissions created as Submitted with zero hours
# ---------------------------------------------------------------------------


class TestCreateMissingSubmittedSubmissions:
    """Employees without a submission get a Submitted submission with zero hours."""

    def test_missing_employee_gets_submitted_submission(self, _mock_boto):
        mod = _mock_boto["de_mod"]
        sub_table = _mock_boto["submissions_table"]

        with patch.object(mod, "_get_expired_unlocked_periods", return_value=[_make_period()]), \
             patch.object(mod, "_query_submissions_by_status", return_value=[]), \
             patch.object(mod, "_get_all_employees", return_value=[
                 _make_employee("emp-001"), _make_employee("emp-002")
             ]), \
             patch.object(mod, "_get_employee_ids_with_submission", return_value={"emp-001"}), \
             patch.object(mod, "_send_under_40_hours_notifications"), \
             patch.object(mod, "_mark_period_locked"):

            mod.handler({}, None)

        sub_table.put_item.assert_called_once()
        created_item = sub_table.put_item.call_args[1]["Item"]
        assert created_item["employeeId"] == "emp-002"
        assert created_item["periodId"] == "period-001"
        assert created_item["status"] == "Submitted"
        assert created_item["totalHours"] == Decimal("0")

    def test_no_missing_employees_no_put_item(self, _mock_boto):
        mod = _mock_boto["de_mod"]
        sub_table = _mock_boto["submissions_table"]

        with patch.object(mod, "_get_expired_unlocked_periods", return_value=[_make_period()]), \
             patch.object(mod, "_query_submissions_by_status", return_value=[]), \
             patch.object(mod, "_get_all_employees", return_value=[_make_employee("emp-001")]), \
             patch.object(mod, "_get_employee_ids_with_submission", return_value={"emp-001"}), \
             patch.object(mod, "_send_under_40_hours_notifications"), \
             patch.object(mod, "_mark_period_locked"):

            mod.handler({}, None)

        sub_table.put_item.assert_not_called()


# ---------------------------------------------------------------------------
# Period locking and edge cases
# ---------------------------------------------------------------------------


class TestPeriodLocking:
    """The period should be marked as isLocked = true after enforcement."""

    def test_period_marked_as_locked(self, _mock_boto):
        mod = _mock_boto["de_mod"]
        periods_table = _mock_boto["periods_table"]

        with patch.object(mod, "_get_expired_unlocked_periods", return_value=[_make_period()]), \
             patch.object(mod, "_submit_draft_submissions"), \
             patch.object(mod, "_create_missing_submitted_submissions"), \
             patch.object(mod, "_send_under_40_hours_notifications"):

            mod.handler({}, None)

        periods_table.update_item.assert_called_once()
        call_kwargs = periods_table.update_item.call_args[1]
        assert call_kwargs["Key"] == {"periodId": "period-001"}
        assert call_kwargs["ExpressionAttributeValues"][":locked"] is True

    def test_no_expired_periods_returns_zero(self, _mock_boto):
        mod = _mock_boto["de_mod"]

        with patch.object(mod, "_get_expired_unlocked_periods", return_value=[]):
            result = mod.handler({}, None)

        assert result == {"submittedPeriods": 0}

    def test_handler_returns_submitted_period_count(self, _mock_boto):
        mod = _mock_boto["de_mod"]

        periods = [
            _make_period(period_id="period-001"),
            _make_period(period_id="period-002"),
        ]

        with patch.object(mod, "_get_expired_unlocked_periods", return_value=periods), \
             patch.object(mod, "_submit_draft_submissions"), \
             patch.object(mod, "_create_missing_submitted_submissions"), \
             patch.object(mod, "_send_under_40_hours_notifications"), \
             patch.object(mod, "_mark_period_locked"):

            result = mod.handler({}, None)

        assert result == {"submittedPeriods": 2}
