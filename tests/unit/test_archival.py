"""Unit tests for Archival Lambda.

Validates: Requirements 13.1, 13.2, 13.3
"""

import os
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lambdas"))

os.environ.setdefault("SUBMISSIONS_TABLE", "SubmissionsTable")
os.environ.setdefault("PERIODS_TABLE", "PeriodsTable")


def _make_period(
    period_id="period-001",
    start_date="2025-01-04",
    end_date="2025-01-10",
    biweekly_period_id="bw-2025-01",
):
    """Build a timesheet period item."""
    return {
        "periodId": period_id,
        "startDate": start_date,
        "endDate": end_date,
        "biweeklyPeriodId": biweekly_period_id,
        "periodString": f"{start_date} to {end_date}",
    }


def _make_submission(
    submission_id="sub-001",
    period_id="period-001",
    employee_id="emp-001",
    status="Approved",
    archived=False,
    total_hours="40",
    chargeable_hours="32",
):
    """Build a timesheet submission item."""
    return {
        "submissionId": submission_id,
        "periodId": period_id,
        "employeeId": employee_id,
        "status": status,
        "archived": archived,
        "totalHours": Decimal(total_hours),
        "chargeableHours": Decimal(chargeable_hours),
        "createdAt": "2025-01-05T10:00:00+00:00",
        "updatedAt": "2025-01-08T14:00:00+00:00",
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _mock_boto(monkeypatch):
    """Patch boto3.resource used at module level in the archival handler."""
    mock_periods_table = MagicMock()
    mock_submissions_table = MagicMock()

    def _table_router(name):
        mapping = {
            "PeriodsTable": mock_periods_table,
            "SubmissionsTable": mock_submissions_table,
        }
        return mapping.get(name, MagicMock())

    mock_dynamodb = MagicMock()
    mock_dynamodb.Table.side_effect = _table_router

    # Defaults — no periods, no submissions
    mock_periods_table.scan.return_value = {"Items": []}
    mock_submissions_table.query.return_value = {"Items": []}
    mock_submissions_table.update_item.return_value = {}

    with patch("boto3.resource", return_value=mock_dynamodb):
        # Clear cached module so module-level globals pick up mocks
        for mod_name in list(sys.modules):
            if "archival" in mod_name and "test_archival" not in mod_name:
                del sys.modules[mod_name]

        from lambdas.archival import handler as arch_mod

        arch_mod.dynamodb = mock_dynamodb

        yield {
            "arch_mod": arch_mod,
            "periods_table": mock_periods_table,
            "submissions_table": mock_submissions_table,
        }


# ---------------------------------------------------------------------------
# Requirement 13.1 — Submissions are marked as archived
# ---------------------------------------------------------------------------


class TestSubmissionsMarkedAsArchived:
    """All submissions for an ended biweekly period should be archived."""

    def test_single_submission_archived(self, _mock_boto):
        mod = _mock_boto["arch_mod"]
        sub_table = _mock_boto["submissions_table"]

        submission = _make_submission(
            submission_id="sub-001",
            period_id="period-001",
            status="Approved",
        )

        with patch.object(
            mod, "_find_ended_biweekly_period", return_value="bw-2025-01"
        ), patch.object(
            mod, "_get_period_ids_for_biweekly", return_value=["period-001"]
        ), patch.object(
            mod, "_get_all_submissions_for_period", return_value=[submission]
        ):
            result = mod.handler({}, None)

        sub_table.update_item.assert_called_once()
        call_kwargs = sub_table.update_item.call_args[1]
        assert call_kwargs["Key"] == {"submissionId": "sub-001"}
        assert call_kwargs["ExpressionAttributeValues"][":archived"] is True
        assert result["archivedSubmissions"] == 1

    def test_multiple_submissions_all_archived(self, _mock_boto):
        mod = _mock_boto["arch_mod"]
        sub_table = _mock_boto["submissions_table"]

        submissions = [
            _make_submission("sub-001", "period-001", "emp-001", "Approved"),
            _make_submission("sub-002", "period-001", "emp-002", "Locked"),
            _make_submission("sub-003", "period-001", "emp-003", "Approved"),
        ]

        with patch.object(
            mod, "_find_ended_biweekly_period", return_value="bw-2025-01"
        ), patch.object(
            mod, "_get_period_ids_for_biweekly", return_value=["period-001"]
        ), patch.object(
            mod, "_get_all_submissions_for_period", return_value=submissions
        ):
            result = mod.handler({}, None)

        assert sub_table.update_item.call_count == 3
        archived_ids = {
            c[1]["Key"]["submissionId"]
            for c in sub_table.update_item.call_args_list
        }
        assert archived_ids == {"sub-001", "sub-002", "sub-003"}
        assert result["archivedSubmissions"] == 3

    def test_submissions_across_multiple_periods_archived(self, _mock_boto):
        """Biweekly cycle with two weekly periods — both get archived."""
        mod = _mock_boto["arch_mod"]
        sub_table = _mock_boto["submissions_table"]

        subs_period1 = [
            _make_submission("sub-001", "period-001", "emp-001", "Approved"),
        ]
        subs_period2 = [
            _make_submission("sub-002", "period-002", "emp-001", "Locked"),
        ]

        with patch.object(
            mod, "_find_ended_biweekly_period", return_value="bw-2025-01"
        ), patch.object(
            mod,
            "_get_period_ids_for_biweekly",
            return_value=["period-001", "period-002"],
        ), patch.object(
            mod, "_get_all_submissions_for_period"
        ) as mock_get_subs:
            mock_get_subs.side_effect = lambda pid: (
                subs_period1 if pid == "period-001" else subs_period2
            )
            result = mod.handler({}, None)

        assert sub_table.update_item.call_count == 2
        assert result["archivedSubmissions"] == 2

    def test_already_archived_submissions_skipped(self, _mock_boto):
        """Submissions already archived should not be updated again."""
        mod = _mock_boto["arch_mod"]
        sub_table = _mock_boto["submissions_table"]

        submissions = [
            _make_submission("sub-001", "period-001", "emp-001", "Approved", archived=True),
            _make_submission("sub-002", "period-001", "emp-002", "Approved", archived=False),
        ]

        with patch.object(
            mod, "_find_ended_biweekly_period", return_value="bw-2025-01"
        ), patch.object(
            mod, "_get_period_ids_for_biweekly", return_value=["period-001"]
        ), patch.object(
            mod, "_get_all_submissions_for_period", return_value=submissions
        ):
            result = mod.handler({}, None)

        # Only sub-002 should be updated (sub-001 already archived)
        sub_table.update_item.assert_called_once()
        call_kwargs = sub_table.update_item.call_args[1]
        assert call_kwargs["Key"] == {"submissionId": "sub-002"}
        assert result["archivedSubmissions"] == 1

    def test_no_ended_biweekly_period_returns_zero(self, _mock_boto):
        mod = _mock_boto["arch_mod"]
        sub_table = _mock_boto["submissions_table"]

        with patch.object(
            mod, "_find_ended_biweekly_period", return_value=None
        ):
            result = mod.handler({}, None)

        sub_table.update_item.assert_not_called()
        assert result["archivedSubmissions"] == 0

    def test_no_periods_for_biweekly_returns_zero(self, _mock_boto):
        mod = _mock_boto["arch_mod"]
        sub_table = _mock_boto["submissions_table"]

        with patch.object(
            mod, "_find_ended_biweekly_period", return_value="bw-2025-01"
        ), patch.object(
            mod, "_get_period_ids_for_biweekly", return_value=[]
        ):
            result = mod.handler({}, None)

        sub_table.update_item.assert_not_called()
        assert result["archivedSubmissions"] == 0


# ---------------------------------------------------------------------------
# Requirement 13.2 — Entries and metadata are retained
# ---------------------------------------------------------------------------


class TestEntriesAndMetadataRetained:
    """Archival only sets archived=true; entries and metadata are not deleted."""

    def test_archival_only_sets_archived_flag(self, _mock_boto):
        """The update_item call should only SET archived, updatedAt, updatedBy.
        No DELETE expressions should be used."""
        mod = _mock_boto["arch_mod"]
        sub_table = _mock_boto["submissions_table"]

        submission = _make_submission(
            submission_id="sub-001",
            period_id="period-001",
            status="Approved",
            total_hours="40",
            chargeable_hours="32",
        )

        with patch.object(
            mod, "_find_ended_biweekly_period", return_value="bw-2025-01"
        ), patch.object(
            mod, "_get_period_ids_for_biweekly", return_value=["period-001"]
        ), patch.object(
            mod, "_get_all_submissions_for_period", return_value=[submission]
        ):
            mod.handler({}, None)

        call_kwargs = sub_table.update_item.call_args[1]
        update_expr = call_kwargs["UpdateExpression"]

        # Should only SET fields, never REMOVE or DELETE
        assert "SET" in update_expr
        assert "REMOVE" not in update_expr
        assert "DELETE" not in update_expr

        # Verify the expression sets archived, updatedAt, and updatedBy
        attr_names = call_kwargs["ExpressionAttributeNames"]
        assert "#archived" in attr_names
        assert "#updatedAt" in attr_names
        assert "#updatedBy" in attr_names

    def test_no_delete_item_calls_on_submissions(self, _mock_boto):
        """Archival should never call delete_item on the submissions table."""
        mod = _mock_boto["arch_mod"]
        sub_table = _mock_boto["submissions_table"]

        submission = _make_submission("sub-001", "period-001", "emp-001", "Approved")

        with patch.object(
            mod, "_find_ended_biweekly_period", return_value="bw-2025-01"
        ), patch.object(
            mod, "_get_period_ids_for_biweekly", return_value=["period-001"]
        ), patch.object(
            mod, "_get_all_submissions_for_period", return_value=[submission]
        ):
            mod.handler({}, None)

        sub_table.delete_item.assert_not_called()

    def test_submission_metadata_preserved_in_update(self, _mock_boto):
        """The update only touches archived/updatedAt/updatedBy — original
        metadata fields (status, totalHours, etc.) are untouched."""
        mod = _mock_boto["arch_mod"]
        sub_table = _mock_boto["submissions_table"]

        submission = _make_submission(
            submission_id="sub-001",
            period_id="period-001",
            employee_id="emp-001",
            status="Locked",
            total_hours="20",
            chargeable_hours="15",
        )

        with patch.object(
            mod, "_find_ended_biweekly_period", return_value="bw-2025-01"
        ), patch.object(
            mod, "_get_period_ids_for_biweekly", return_value=["period-001"]
        ), patch.object(
            mod, "_get_all_submissions_for_period", return_value=[submission]
        ):
            mod.handler({}, None)

        call_kwargs = sub_table.update_item.call_args[1]
        attr_values = call_kwargs["ExpressionAttributeValues"]

        # Only archived, timestamp, and system marker should be in the update
        assert ":archived" in attr_values
        assert ":now" in attr_values
        assert ":system" in attr_values
        # Status, totalHours, chargeableHours should NOT be modified
        assert ":status" not in attr_values
        assert ":totalHours" not in attr_values
        assert ":chargeableHours" not in attr_values


# ---------------------------------------------------------------------------
# Requirement 13.3 — Archived submissions are read-only
# ---------------------------------------------------------------------------


class TestArchivedSubmissionsReadOnly:
    """Archived submissions should be rejected for edits via the submission
    and entry resolvers."""

    def test_submit_timesheet_rejects_archived_submission(self):
        """SubmitTimesheet handler raises ValueError for archived submissions."""
        with patch("boto3.resource") as mock_resource:
            mock_table = MagicMock()
            mock_resource.return_value.Table.return_value = mock_table

            mock_table.get_item.return_value = {
                "Item": {
                    "submissionId": "sub-001",
                    "employeeId": "emp-001",
                    "status": "Draft",
                    "archived": True,
                }
            }

            # Clear cached module
            for mod_name in list(sys.modules):
                if "SubmitTimesheet" in mod_name:
                    del sys.modules[mod_name]

            from lambdas.submissions.SubmitTimesheet.handler import submit_timesheet

            event = {
                "arguments": {"submissionId": "sub-001"},
                "identity": {
                    "claims": {
                        "sub": "emp-001",
                        "custom:userType": "user",
                        "custom:role": "Employee",
                    }
                },
            }

            with pytest.raises(ValueError, match="[Aa]rchived.*read-only"):
                submit_timesheet(event)

    def test_entry_validation_rejects_archived_submission(self):
        """The shared_utils validate_submission_editable raises ValueError
        for archived submissions."""
        with patch("boto3.resource") as mock_resource:
            mock_dynamodb = MagicMock()
            mock_resource.return_value = mock_dynamodb

            # Clear cached module
            for mod_name in list(sys.modules):
                if "entries" in mod_name and "test_" not in mod_name:
                    del sys.modules[mod_name]

            from lambdas.entries.shared_utils import validate_submission_editable

            archived_submission = {
                "submissionId": "sub-001",
                "status": "Draft",
                "archived": True,
            }

            with pytest.raises(ValueError, match="[Aa]rchived.*read-only"):
                validate_submission_editable(archived_submission)

    def test_non_archived_submission_not_rejected_by_archive_check(self):
        """A non-archived Draft submission should pass the archived check
        (may still be validated for status)."""
        with patch("boto3.resource") as mock_resource:
            mock_dynamodb = MagicMock()
            mock_resource.return_value = mock_dynamodb

            for mod_name in list(sys.modules):
                if "entries" in mod_name and "test_" not in mod_name:
                    del sys.modules[mod_name]

            from lambdas.entries.shared_utils import validate_submission_editable

            draft_submission = {
                "submissionId": "sub-001",
                "status": "Draft",
                "archived": False,
            }

            # Should not raise — Draft + not archived is editable
            validate_submission_editable(draft_submission)


# ---------------------------------------------------------------------------
# Internal helper tests
# ---------------------------------------------------------------------------


class TestFindEndedBiweeklyPeriod:
    """Test the _find_ended_biweekly_period helper."""

    def test_finds_most_recent_ended_biweekly(self, _mock_boto):
        mod = _mock_boto["arch_mod"]
        periods_table = _mock_boto["periods_table"]

        periods_table.scan.return_value = {
            "Items": [
                _make_period("p1", "2025-01-04", "2025-01-10", "bw-2025-01"),
                _make_period("p2", "2025-01-11", "2025-01-17", "bw-2025-01"),
                _make_period("p3", "2025-01-18", "2025-01-24", "bw-2025-02"),
                _make_period("p4", "2025-01-25", "2025-01-31", "bw-2025-02"),
            ]
        }

        # Today is Feb 1 — both biweekly periods have ended
        result = mod._find_ended_biweekly_period(date(2025, 2, 1))

        # bw-2025-02 has the most recent max endDate (Jan 31)
        assert result == "bw-2025-02"

    def test_returns_none_when_no_periods_ended(self, _mock_boto):
        mod = _mock_boto["arch_mod"]
        periods_table = _mock_boto["periods_table"]

        periods_table.scan.return_value = {
            "Items": [
                _make_period("p1", "2025-02-01", "2025-02-07", "bw-2025-03"),
            ]
        }

        # Today is Jan 30 — period hasn't ended yet
        result = mod._find_ended_biweekly_period(date(2025, 1, 30))
        assert result is None

    def test_skips_periods_without_biweekly_id(self, _mock_boto):
        mod = _mock_boto["arch_mod"]
        periods_table = _mock_boto["periods_table"]

        periods_table.scan.return_value = {
            "Items": [
                {
                    "periodId": "p1",
                    "startDate": "2025-01-04",
                    "endDate": "2025-01-10",
                    # No biweeklyPeriodId
                },
            ]
        }

        result = mod._find_ended_biweekly_period(date(2025, 2, 1))
        assert result is None
