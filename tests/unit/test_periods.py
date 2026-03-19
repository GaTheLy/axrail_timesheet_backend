"""Unit tests for Timesheet Period resolvers.

Periods are now Monday-Friday (5 working days).
Deadline is auto-computed to Friday 5PM MYT (09:00 UTC).
No manual submissionDeadline input.

Validates: Requirements 5.2, 5.3, 5.5
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lambdas"))

os.environ.setdefault("PERIODS_TABLE", "PeriodsTable")


def _make_event(
    field_name="createTimesheetPeriod",
    user_type="superadmin",
    role="Tech_Lead",
    user_id="caller-001",
    arguments=None,
):
    return {
        "info": {"fieldName": field_name},
        "identity": {
            "claims": {
                "sub": user_id,
                "custom:userType": user_type,
                "custom:role": role,
                "email": "caller@example.com",
                "custom:departmentId": "dept-1",
                "custom:positionId": "pos-1",
            }
        },
        "arguments": arguments or {},
    }


def _valid_period_input(
    start="2025-01-06",
    end="2025-01-10",
    period_string="Jan 06 - Jan 10, 2025",
):
    """Build valid period input. Mon-Fri, no submissionDeadline (auto-computed)."""
    return {
        "input": {
            "startDate": start,
            "endDate": end,
            "periodString": period_string,
        }
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _mock_boto(monkeypatch):
    mock_table = MagicMock()
    mock_table.scan.return_value = {"Items": []}
    mock_table.put_item.return_value = {}
    mock_table.get_item.return_value = {
        "Item": {
            "periodId": "period-100",
            "startDate": "2025-01-06",
            "endDate": "2025-01-10",
            "submissionDeadline": "2025-01-10T09:00:00+00:00",
            "periodString": "Jan 06 - Jan 10, 2025",
            "isLocked": False,
            "createdAt": "2025-01-01T00:00:00+00:00",
            "createdBy": "caller-001",
        }
    }
    mock_table.update_item.return_value = {
        "Attributes": {
            "periodId": "period-100",
            "startDate": "2025-01-06",
            "endDate": "2025-01-10",
            "submissionDeadline": "2025-01-10T09:00:00+00:00",
            "periodString": "Jan 06 - Jan 10, 2025",
            "isLocked": False,
            "updatedAt": "2025-06-01T00:00:00+00:00",
            "updatedBy": "caller-001",
        }
    }

    mock_dynamodb = MagicMock()
    mock_dynamodb.Table.return_value = mock_table

    with patch("boto3.resource", return_value=mock_dynamodb):
        # Clear cached modules for periods handlers
        for mod_name in list(sys.modules):
            if "periods" in mod_name and "handler" in mod_name:
                del sys.modules[mod_name]

        from lambdas.periods.CreateTimesheetPeriod import handler as create_mod
        from lambdas.periods.UpdateTimesheetPeriod import handler as update_mod

        create_mod.dynamodb = mock_dynamodb
        update_mod.dynamodb = mock_dynamodb

        yield {
            "table": mock_table,
            "create_mod": create_mod,
            "update_mod": update_mod,
        }


# ---------------------------------------------------------------------------
# Monday/Friday validation
# ---------------------------------------------------------------------------


class TestPeriodDateValidation:
    def test_non_monday_start_rejected(self, _mock_boto):
        """startDate on a Saturday should be rejected."""
        mod = _mock_boto["create_mod"]
        event = _make_event(
            arguments=_valid_period_input(start="2025-01-04", end="2025-01-08"),
        )
        with pytest.raises(ValueError, match="not a Monday"):
            mod.create_timesheet_period(event)

    def test_non_friday_end_rejected(self, _mock_boto):
        """endDate on a Thursday should be rejected."""
        mod = _mock_boto["create_mod"]
        event = _make_event(
            arguments=_valid_period_input(start="2025-01-06", end="2025-01-09"),
        )
        with pytest.raises(ValueError, match="not a Friday"):
            mod.create_timesheet_period(event)

    def test_sunday_start_rejected(self, _mock_boto):
        mod = _mock_boto["create_mod"]
        event = _make_event(
            arguments=_valid_period_input(start="2025-01-05", end="2025-01-09"),
        )
        with pytest.raises(ValueError, match="not a Monday"):
            mod.create_timesheet_period(event)

    def test_end_not_four_days_after_start_rejected(self, _mock_boto):
        """endDate that is a Friday but not startDate + 4 should be rejected."""
        mod = _mock_boto["create_mod"]
        # 2025-01-06 (Mon) + 11 days = 2025-01-17 (Fri) — wrong span
        event = _make_event(
            arguments=_valid_period_input(start="2025-01-06", end="2025-01-17"),
        )
        with pytest.raises(ValueError, match="exactly 4 days"):
            mod.create_timesheet_period(event)

    def test_valid_monday_friday_accepted(self, _mock_boto):
        """A valid Mon-to-Fri period should be created successfully."""
        mod = _mock_boto["create_mod"]
        event = _make_event(arguments=_valid_period_input())
        result = mod.create_timesheet_period(event)
        assert result["startDate"] == "2025-01-06"
        assert result["endDate"] == "2025-01-10"

    def test_deadline_auto_computed(self, _mock_boto):
        """submissionDeadline should be auto-computed to Friday 5PM MYT (09:00 UTC)."""
        mod = _mock_boto["create_mod"]
        event = _make_event(arguments=_valid_period_input())
        result = mod.create_timesheet_period(event)
        assert "2025-01-10T09:00:00" in result["submissionDeadline"]

    def test_update_with_invalid_start_rejected(self, _mock_boto):
        """Updating startDate to a non-Monday should be rejected."""
        mod = _mock_boto["update_mod"]
        event = _make_event(
            field_name="updateTimesheetPeriod",
            arguments={
                "periodId": "period-100",
                "input": {
                    "startDate": "2025-01-04",  # Saturday
                    "endDate": "2025-01-08",
                },
            },
        )
        with pytest.raises(ValueError, match="not a Monday"):
            mod.update_timesheet_period(event)


# ---------------------------------------------------------------------------
# Overlap detection
# ---------------------------------------------------------------------------


class TestPeriodOverlapDetection:
    def test_exact_overlap_rejected(self, _mock_boto):
        mod = _mock_boto["create_mod"]
        table = _mock_boto["table"]
        table.scan.return_value = {
            "Items": [{
                "periodId": "period-existing",
                "startDate": "2025-01-06",
                "endDate": "2025-01-10",
                "periodString": "Jan 06 - Jan 10, 2025",
            }]
        }
        event = _make_event(arguments=_valid_period_input())
        with pytest.raises(ValueError, match="overlaps"):
            mod.create_timesheet_period(event)

    def test_adjacent_periods_accepted(self, _mock_boto):
        """Two back-to-back weeks should not overlap."""
        mod = _mock_boto["create_mod"]
        table = _mock_boto["table"]
        table.scan.return_value = {
            "Items": [{
                "periodId": "period-existing",
                "startDate": "2024-12-30",
                "endDate": "2025-01-03",
                "periodString": "Dec 30 - Jan 03, 2025",
            }]
        }
        event = _make_event(arguments=_valid_period_input())
        result = mod.create_timesheet_period(event)
        assert result["startDate"] == "2025-01-06"

    def test_no_existing_periods_accepted(self, _mock_boto):
        mod = _mock_boto["create_mod"]
        table = _mock_boto["table"]
        table.scan.return_value = {"Items": []}
        event = _make_event(arguments=_valid_period_input())
        result = mod.create_timesheet_period(event)
        assert result["periodId"] is not None

    def test_update_excludes_self_from_overlap_check(self, _mock_boto):
        mod = _mock_boto["update_mod"]
        table = _mock_boto["table"]
        table.scan.return_value = {
            "Items": [{
                "periodId": "period-100",
                "startDate": "2025-01-06",
                "endDate": "2025-01-10",
                "periodString": "Jan 06 - Jan 10, 2025",
            }]
        }
        event = _make_event(
            field_name="updateTimesheetPeriod",
            arguments={
                "periodId": "period-100",
                "input": {"periodString": "Week of Jan 06, 2025"},
            },
        )
        result = mod.update_timesheet_period(event)
        assert result is not None

    def test_update_detects_overlap_with_other_period(self, _mock_boto):
        mod = _mock_boto["update_mod"]
        table = _mock_boto["table"]
        table.scan.return_value = {
            "Items": [{
                "periodId": "period-other",
                "startDate": "2025-01-13",
                "endDate": "2025-01-17",
                "periodString": "Jan 13 - Jan 17, 2025",
            }]
        }
        event = _make_event(
            field_name="updateTimesheetPeriod",
            arguments={
                "periodId": "period-100",
                "input": {
                    "startDate": "2025-01-13",
                    "endDate": "2025-01-17",
                },
            },
        )
        with pytest.raises(ValueError, match="overlaps"):
            mod.update_timesheet_period(event)
