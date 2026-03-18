"""Unit tests for Employee Performance Tracking Lambda.

Validates: Requirements 11.1, 11.2, 11.3
"""

import os
import sys
from decimal import Decimal, ROUND_HALF_UP
from unittest.mock import MagicMock, patch, call

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lambdas"))

os.environ.setdefault("EMPLOYEE_PERFORMANCE_TABLE", "PerformanceTable")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_stream_record(
    employee_id="emp-001",
    submission_id="sub-001",
    new_status="Approved",
    old_status="Submitted",
    chargeable_hours="20",
    total_hours="40",
    approved_at="2025-06-15T10:30:00+00:00",
    event_name="MODIFY",
):
    """Build a DynamoDB Streams record for a Timesheet_Submissions change."""
    record = {
        "eventName": event_name,
        "dynamodb": {
            "NewImage": {
                "submissionId": {"S": submission_id},
                "employeeId": {"S": employee_id},
                "status": {"S": new_status},
                "chargeableHours": {"N": chargeable_hours},
                "totalHours": {"N": total_hours},
                "approvedAt": {"S": approved_at},
            },
        },
    }
    if event_name == "MODIFY":
        record["dynamodb"]["OldImage"] = {
            "status": {"S": old_status},
        }
    return record


def _make_stream_event(*records):
    """Wrap one or more stream records into a DynamoDB Streams event."""
    return {"Records": list(records)}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _mock_boto(monkeypatch):
    """Patch boto3.resource used at module level in the performance handler."""
    mock_perf_table = MagicMock()

    def _table_router(name):
        if name == "PerformanceTable":
            return mock_perf_table
        return MagicMock()

    mock_dynamodb = MagicMock()
    mock_dynamodb.Table.side_effect = _table_router

    # Default: update_item returns new totals (simulates new record)
    mock_perf_table.update_item.return_value = {
        "Attributes": {
            "ytdChargable_hours": Decimal("20"),
            "ytdTotalHours": Decimal("40"),
        }
    }

    with patch("boto3.resource", return_value=mock_dynamodb):
        # Clear cached module so module-level globals pick up mocks
        for mod_name in list(sys.modules):
            if "performance" in mod_name and "handler" in mod_name:
                del sys.modules[mod_name]

        from lambdas.performance import handler as perf_mod

        perf_mod.dynamodb = mock_dynamodb

        yield {
            "perf_mod": perf_mod,
            "perf_table": mock_perf_table,
        }


# ---------------------------------------------------------------------------
# Requirement 11.3 — New record creation when none exists for employee/year
# ---------------------------------------------------------------------------


class TestNewRecordCreation:
    """When no Employee_Performance record exists for (userId, year),
    DynamoDB ADD creates it with the submission's hours as initial values."""

    def test_new_record_created_with_initial_hours(self, _mock_boto):
        """First approved submission for an employee/year creates a new record.

        Validates: Requirements 11.1, 11.3
        """
        mod = _mock_boto["perf_mod"]
        table = _mock_boto["perf_table"]

        # Simulate DynamoDB ADD on a non-existent item — returns the added values
        table.update_item.return_value = {
            "Attributes": {
                "ytdChargable_hours": Decimal("15"),
                "ytdTotalHours": Decimal("40"),
            }
        }

        record = _make_stream_record(
            employee_id="emp-new",
            chargeable_hours="15",
            total_hours="40",
            approved_at="2025-03-10T08:00:00+00:00",
        )
        event = _make_stream_event(record)

        result = mod.handler(event, None)

        assert result["processedRecords"] == 1

        # First update_item call: ADD hours
        first_call = table.update_item.call_args_list[0]
        assert first_call[1]["Key"] == {"userId": "emp-new", "year": 2025}
        assert ":chargeable" in first_call[1]["ExpressionAttributeValues"]
        assert first_call[1]["ExpressionAttributeValues"][":chargeable"] == Decimal("15")
        assert first_call[1]["ExpressionAttributeValues"][":total"] == Decimal("40")

    def test_year_extracted_from_approved_at(self, _mock_boto):
        """The year is extracted from the approvedAt timestamp.

        Validates: Requirements 11.1, 11.3
        """
        mod = _mock_boto["perf_mod"]
        table = _mock_boto["perf_table"]

        record = _make_stream_record(
            approved_at="2024-12-20T15:00:00+00:00",
        )
        event = _make_stream_event(record)

        mod.handler(event, None)

        first_call = table.update_item.call_args_list[0]
        assert first_call[1]["Key"]["year"] == 2024


# ---------------------------------------------------------------------------
# Requirement 11.1 — Cumulative hour addition to existing record
# ---------------------------------------------------------------------------


class TestCumulativeHourAddition:
    """When an Employee_Performance record already exists, approved hours
    are atomically added to the existing ytd totals."""

    def test_hours_added_to_existing_record(self, _mock_boto):
        """Second approved submission adds hours to existing YTD totals.

        Validates: Requirements 11.1
        """
        mod = _mock_boto["perf_mod"]
        table = _mock_boto["perf_table"]

        # Simulate existing record: after ADD, totals reflect cumulative values
        table.update_item.return_value = {
            "Attributes": {
                "ytdChargable_hours": Decimal("35"),  # 20 existing + 15 new
                "ytdTotalHours": Decimal("80"),        # 40 existing + 40 new
            }
        }

        record = _make_stream_record(
            employee_id="emp-existing",
            chargeable_hours="15",
            total_hours="40",
            approved_at="2025-06-20T10:00:00+00:00",
        )
        event = _make_stream_event(record)

        result = mod.handler(event, None)

        assert result["processedRecords"] == 1

        # Verify ADD expression is used (not SET/PUT)
        first_call = table.update_item.call_args_list[0]
        update_expr = first_call[1]["UpdateExpression"]
        assert "ADD" in update_expr

    def test_multiple_submissions_processed_sequentially(self, _mock_boto):
        """Multiple approved submissions in one event batch are all processed.

        Validates: Requirements 11.1
        """
        mod = _mock_boto["perf_mod"]
        table = _mock_boto["perf_table"]

        table.update_item.return_value = {
            "Attributes": {
                "ytdChargable_hours": Decimal("20"),
                "ytdTotalHours": Decimal("40"),
            }
        }

        record1 = _make_stream_record(
            employee_id="emp-001",
            submission_id="sub-001",
            chargeable_hours="10",
            total_hours="20",
        )
        record2 = _make_stream_record(
            employee_id="emp-002",
            submission_id="sub-002",
            chargeable_hours="15",
            total_hours="30",
        )
        event = _make_stream_event(record1, record2)

        result = mod.handler(event, None)

        assert result["processedRecords"] == 2

    def test_uses_atomic_add_expression(self, _mock_boto):
        """The handler uses DynamoDB ADD to atomically increment hours.

        Validates: Requirements 11.1
        """
        mod = _mock_boto["perf_mod"]
        table = _mock_boto["perf_table"]

        record = _make_stream_record(
            chargeable_hours="8.5",
            total_hours="16",
        )
        event = _make_stream_event(record)

        mod.handler(event, None)

        first_call = table.update_item.call_args_list[0]
        update_expr = first_call[1]["UpdateExpression"]
        assert "ADD" in update_expr
        assert first_call[1]["ExpressionAttributeValues"][":chargeable"] == Decimal("8.5")
        assert first_call[1]["ExpressionAttributeValues"][":total"] == Decimal("16")


# ---------------------------------------------------------------------------
# Requirement 11.2 — Chargeability percentage recalculation
# ---------------------------------------------------------------------------


class TestChargeabilityRecalculation:
    """After adding hours, ytdChargabilityPercentage is recalculated as
    (ytdChargable_hours / ytdTotalHours) * 100."""

    def test_percentage_recalculated_after_update(self, _mock_boto):
        """The handler recalculates and stores the chargeability percentage.

        Validates: Requirements 11.2
        """
        mod = _mock_boto["perf_mod"]
        table = _mock_boto["perf_table"]

        # After ADD: 30 chargeable out of 40 total
        table.update_item.return_value = {
            "Attributes": {
                "ytdChargable_hours": Decimal("30"),
                "ytdTotalHours": Decimal("40"),
            }
        }

        record = _make_stream_record(
            chargeable_hours="10",
            total_hours="20",
        )
        event = _make_stream_event(record)

        mod.handler(event, None)

        # Second update_item call: SET percentage
        assert table.update_item.call_count == 2
        second_call = table.update_item.call_args_list[1]
        expected_pct = (Decimal("30") / Decimal("40") * Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        assert second_call[1]["ExpressionAttributeValues"][":pct"] == expected_pct

    def test_percentage_is_zero_when_total_hours_zero(self, _mock_boto):
        """When ytdTotalHours is 0, percentage should be 0 (no division by zero).

        Validates: Requirements 11.2
        """
        mod = _mock_boto["perf_mod"]
        table = _mock_boto["perf_table"]

        table.update_item.return_value = {
            "Attributes": {
                "ytdChargable_hours": Decimal("0"),
                "ytdTotalHours": Decimal("0"),
            }
        }

        record = _make_stream_record(
            chargeable_hours="0",
            total_hours="0",
        )
        event = _make_stream_event(record)

        mod.handler(event, None)

        second_call = table.update_item.call_args_list[1]
        assert second_call[1]["ExpressionAttributeValues"][":pct"] == Decimal("0")

    def test_100_percent_when_all_hours_chargeable(self, _mock_boto):
        """When chargeable equals total, percentage should be 100.00.

        Validates: Requirements 11.2
        """
        mod = _mock_boto["perf_mod"]
        table = _mock_boto["perf_table"]

        table.update_item.return_value = {
            "Attributes": {
                "ytdChargable_hours": Decimal("40"),
                "ytdTotalHours": Decimal("40"),
            }
        }

        record = _make_stream_record(
            chargeable_hours="40",
            total_hours="40",
        )
        event = _make_stream_event(record)

        mod.handler(event, None)

        second_call = table.update_item.call_args_list[1]
        assert second_call[1]["ExpressionAttributeValues"][":pct"] == Decimal("100.00")


# ---------------------------------------------------------------------------
# Filtering — _should_process logic
# ---------------------------------------------------------------------------


class TestShouldProcess:
    """Only records transitioning to Approved should be processed."""

    def test_non_approved_status_ignored(self, _mock_boto):
        """Records with status other than Approved are skipped.

        Validates: Requirements 11.1
        """
        mod = _mock_boto["perf_mod"]
        table = _mock_boto["perf_table"]

        record = _make_stream_record(new_status="Locked", old_status="Draft")
        event = _make_stream_event(record)

        result = mod.handler(event, None)

        assert result["processedRecords"] == 0
        table.update_item.assert_not_called()

    def test_already_approved_not_reprocessed(self, _mock_boto):
        """MODIFY events where old status was already Approved are skipped.

        Validates: Requirements 11.1
        """
        mod = _mock_boto["perf_mod"]
        table = _mock_boto["perf_table"]

        record = _make_stream_record(
            new_status="Approved",
            old_status="Approved",
            event_name="MODIFY",
        )
        event = _make_stream_event(record)

        result = mod.handler(event, None)

        assert result["processedRecords"] == 0
        table.update_item.assert_not_called()

    def test_remove_event_ignored(self, _mock_boto):
        """REMOVE events are not processed."""
        mod = _mock_boto["perf_mod"]
        table = _mock_boto["perf_table"]

        record = {
            "eventName": "REMOVE",
            "dynamodb": {
                "OldImage": {
                    "status": {"S": "Approved"},
                },
            },
        }
        event = _make_stream_event(record)

        result = mod.handler(event, None)

        assert result["processedRecords"] == 0
        table.update_item.assert_not_called()

    def test_insert_with_approved_status_processed(self, _mock_boto):
        """INSERT events with Approved status are processed (edge case).

        Validates: Requirements 11.1
        """
        mod = _mock_boto["perf_mod"]
        table = _mock_boto["perf_table"]

        record = _make_stream_record(
            event_name="INSERT",
            new_status="Approved",
        )
        # INSERT events don't have OldImage
        record["dynamodb"].pop("OldImage", None)
        event = _make_stream_event(record)

        result = mod.handler(event, None)

        assert result["processedRecords"] == 1

    def test_empty_event_returns_zero(self, _mock_boto):
        """An event with no records returns zero processed."""
        mod = _mock_boto["perf_mod"]

        result = mod.handler({"Records": []}, None)

        assert result["processedRecords"] == 0
