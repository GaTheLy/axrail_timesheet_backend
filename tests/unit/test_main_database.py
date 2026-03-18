"""Unit tests for Main Database Management Lambda resolvers.

Validates: Requirements 14.3, 14.4, 14.5
"""

import csv
import io
import os
import sys
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lambdas"))

os.environ.setdefault("MAIN_DATABASE_TABLE", "MainDatabaseTable")
os.environ.setdefault("REPORT_BUCKET", "report-bucket")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _superadmin_event(arguments=None):
    return {
        "identity": {
            "claims": {
                "sub": "superadmin-001",
                "custom:userType": "superadmin",
                "custom:role": "Project_Manager",
                "email": "admin@example.com",
            }
        },
        "arguments": arguments or {},
    }


def _make_csv_content(rows, columns=None):
    """Build a CSV string from a list of dicts."""
    if columns is None:
        columns = ["type", "value", "project_name", "budget_effort", "project_status"]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return output.getvalue()


def _valid_csv_row(
    record_type="Chargeable",
    value="PROJ-001",
    project_name="Alpha",
    budget_effort="100",
    project_status="Active",
):
    return {
        "type": record_type,
        "value": value,
        "project_name": project_name,
        "budget_effort": budget_effort,
        "project_status": project_status,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _mock_boto(monkeypatch):
    """Patch boto3 resources used at module level in main_database handlers."""
    mock_main_table = MagicMock()

    def _table_router(name):
        if name == "MainDatabaseTable":
            return mock_main_table
        return MagicMock()

    mock_dynamodb = MagicMock()
    mock_dynamodb.Table.side_effect = _table_router

    mock_s3 = MagicMock()

    # Defaults
    mock_main_table.scan.return_value = {"Items": []}
    mock_main_table.get_item.return_value = {"Item": None}
    mock_main_table.update_item.return_value = {"Attributes": {}}

    # Set up batch_writer context manager
    mock_batch_writer = MagicMock()
    mock_main_table.batch_writer.return_value.__enter__ = MagicMock(
        return_value=mock_batch_writer
    )
    mock_main_table.batch_writer.return_value.__exit__ = MagicMock(return_value=False)

    with patch("boto3.resource", return_value=mock_dynamodb), \
         patch("boto3.client", return_value=mock_s3):
        # Clear cached modules so module-level globals pick up mocks
        for mod_name in list(sys.modules):
            if mod_name in sys.modules and "main_database" in mod_name and "test_" not in mod_name:
                sys.modules.pop(mod_name, None)
            if mod_name in sys.modules and "shared_utils" in mod_name and "entries" not in mod_name and "test_" not in mod_name:
                sys.modules.pop(mod_name, None)

        from lambdas.main_database.BulkImportCSV import handler as bulk_mod
        from lambdas.main_database.RefreshDatabase import handler as refresh_mod
        from lambdas.main_database import shared_utils as utils_mod

        bulk_mod.REPORT_BUCKET = "report-bucket"
        refresh_mod.REPORT_BUCKET = "report-bucket"
        utils_mod.REPORT_BUCKET = "report-bucket"
        utils_mod.MAIN_DATABASE_TABLE = "MainDatabaseTable"
        utils_mod.dynamodb = mock_dynamodb
        utils_mod.s3_client = mock_s3

        yield {
            "bulk_mod": bulk_mod,
            "refresh_mod": refresh_mod,
            "utils_mod": utils_mod,
            "main_table": mock_main_table,
            "s3_client": mock_s3,
            "dynamodb": mock_dynamodb,
            "batch_writer": mock_batch_writer,
        }


# ---------------------------------------------------------------------------
# Requirement 14.3 — CSV row validation rejects invalid rows with error details
# ---------------------------------------------------------------------------


class TestCSVRowValidation:
    """validate_csv_row should reject rows missing required fields or with
    invalid budget_effort, returning row number and error details."""

    def test_missing_type_rejected(self, _mock_boto):
        """A row with empty 'type' is rejected with error detail.

        Validates: Requirements 14.3, 14.4
        """
        utils = _mock_boto["utils_mod"]
        row = {"type": "", "value": "V1", "project_name": "P", "budget_effort": "10", "project_status": "Active"}
        item, errors = utils.validate_csv_row(row, 1)
        assert item is None
        assert any("type" in e for e in errors)

    def test_missing_value_rejected(self, _mock_boto):
        """A row with empty 'value' is rejected.

        Validates: Requirements 14.3, 14.4
        """
        utils = _mock_boto["utils_mod"]
        row = {"type": "T", "value": "", "project_name": "P", "budget_effort": "10", "project_status": "Active"}
        item, errors = utils.validate_csv_row(row, 2)
        assert item is None
        assert any("value" in e for e in errors)

    def test_missing_project_name_rejected(self, _mock_boto):
        """A row with empty 'project_name' is rejected.

        Validates: Requirements 14.3, 14.4
        """
        utils = _mock_boto["utils_mod"]
        row = {"type": "T", "value": "V", "project_name": "", "budget_effort": "10", "project_status": "Active"}
        item, errors = utils.validate_csv_row(row, 3)
        assert item is None
        assert any("project_name" in e for e in errors)

    def test_missing_budget_effort_rejected(self, _mock_boto):
        """A row with empty 'budget_effort' is rejected.

        Validates: Requirements 14.3, 14.4
        """
        utils = _mock_boto["utils_mod"]
        row = {"type": "T", "value": "V", "project_name": "P", "budget_effort": "", "project_status": "Active"}
        item, errors = utils.validate_csv_row(row, 4)
        assert item is None
        assert any("budget_effort" in e for e in errors)

    def test_invalid_budget_effort_rejected(self, _mock_boto):
        """A row with non-numeric 'budget_effort' is rejected with detail.

        Validates: Requirements 14.3, 14.4
        """
        utils = _mock_boto["utils_mod"]
        row = {"type": "T", "value": "V", "project_name": "P", "budget_effort": "abc", "project_status": "Active"}
        item, errors = utils.validate_csv_row(row, 5)
        assert item is None
        assert any("budget_effort" in e and "abc" in e for e in errors)

    def test_negative_budget_effort_rejected(self, _mock_boto):
        """A row with negative 'budget_effort' is rejected.

        Validates: Requirements 14.3, 14.4
        """
        utils = _mock_boto["utils_mod"]
        row = {"type": "T", "value": "V", "project_name": "P", "budget_effort": "-5", "project_status": "Active"}
        item, errors = utils.validate_csv_row(row, 6)
        assert item is None
        assert any("budget_effort" in e for e in errors)

    def test_missing_project_status_rejected(self, _mock_boto):
        """A row with empty 'project_status' is rejected.

        Validates: Requirements 14.3, 14.4
        """
        utils = _mock_boto["utils_mod"]
        row = {"type": "T", "value": "V", "project_name": "P", "budget_effort": "10", "project_status": ""}
        item, errors = utils.validate_csv_row(row, 7)
        assert item is None
        assert any("project_status" in e for e in errors)

    def test_multiple_missing_fields_all_reported(self, _mock_boto):
        """A row missing multiple fields reports all errors at once.

        Validates: Requirements 14.3, 14.4
        """
        utils = _mock_boto["utils_mod"]
        row = {"type": "", "value": "", "project_name": "", "budget_effort": "", "project_status": ""}
        item, errors = utils.validate_csv_row(row, 1)
        assert item is None
        assert len(errors) == 5

    def test_valid_row_returns_item(self, _mock_boto):
        """A fully valid row returns a well-formed item with no errors.

        Validates: Requirements 14.3
        """
        utils = _mock_boto["utils_mod"]
        row = {"type": "Chargeable", "value": "PROJ-001", "project_name": "Alpha", "budget_effort": "100.5", "project_status": "Active"}
        item, errors = utils.validate_csv_row(row, 1)
        assert errors == []
        assert item is not None
        assert item["type"] == "Chargeable"
        assert item["chargeCode"] == "PROJ-001"
        assert item["projectName"] == "Alpha"
        assert item["budgetEffort"] == Decimal("100.5")
        assert item["projectStatus"] == "Active"
        assert "recordId" in item
        assert "createdAt" in item


# ---------------------------------------------------------------------------
# Requirement 14.4 — Valid rows persisted, invalid rows skipped
# ---------------------------------------------------------------------------


class TestBulkImportCSV:
    """BulkImportCSV should persist valid rows and skip invalid ones,
    returning row numbers and error details for rejected rows."""

    def test_all_valid_rows_persisted(self, _mock_boto):
        """All valid CSV rows are written to DynamoDB.

        Validates: Requirements 14.3, 14.4
        """
        mod = _mock_boto["bulk_mod"]
        s3 = _mock_boto["s3_client"]

        csv_content = _make_csv_content([
            _valid_csv_row("Chargeable", "P1", "Project 1", "100", "Active"),
            _valid_csv_row("Non-Chargeable", "P2", "Project 2", "200", "Inactive"),
        ])
        s3.get_object.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=csv_content.encode("utf-8")))
        }

        event = _superadmin_event({"file": {"key": "imports/test.csv"}})
        result = mod.bulk_import_csv(event)

        assert result["importedCount"] == 2
        assert result["rejectedCount"] == 0
        assert result["rejectedRows"] == []

    def test_invalid_rows_skipped_valid_persisted(self, _mock_boto):
        """Invalid rows are skipped with error details; valid rows are persisted.

        Validates: Requirements 14.3, 14.4
        """
        mod = _mock_boto["bulk_mod"]
        s3 = _mock_boto["s3_client"]

        csv_content = _make_csv_content([
            _valid_csv_row("Chargeable", "P1", "Project 1", "100", "Active"),
            {"type": "", "value": "", "project_name": "", "budget_effort": "abc", "project_status": ""},
            _valid_csv_row("Non-Chargeable", "P3", "Project 3", "300", "Active"),
        ])
        s3.get_object.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=csv_content.encode("utf-8")))
        }

        event = _superadmin_event({"file": {"key": "imports/test.csv"}})
        result = mod.bulk_import_csv(event)

        assert result["importedCount"] == 2
        assert result["rejectedCount"] == 1
        assert len(result["rejectedRows"]) == 1
        rejected = result["rejectedRows"][0]
        assert rejected["row"] == 2
        assert len(rejected["errors"]) > 0

    def test_all_invalid_rows_none_persisted(self, _mock_boto):
        """When all rows are invalid, nothing is persisted.

        Validates: Requirements 14.3, 14.4
        """
        mod = _mock_boto["bulk_mod"]
        s3 = _mock_boto["s3_client"]
        table = _mock_boto["main_table"]

        csv_content = _make_csv_content([
            {"type": "", "value": "", "project_name": "", "budget_effort": "", "project_status": ""},
            {"type": "T", "value": "V", "project_name": "P", "budget_effort": "bad", "project_status": "Active"},
        ])
        s3.get_object.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=csv_content.encode("utf-8")))
        }

        event = _superadmin_event({"file": {"key": "imports/test.csv"}})
        result = mod.bulk_import_csv(event)

        assert result["importedCount"] == 0
        assert result["rejectedCount"] == 2
        # batch_writer should not be called when no valid items
        table.batch_writer.assert_not_called()

    def test_rejected_rows_include_row_number_and_errors(self, _mock_boto):
        """Each rejected row includes the 1-based row number and error list.

        Validates: Requirements 14.4
        """
        mod = _mock_boto["bulk_mod"]
        s3 = _mock_boto["s3_client"]

        csv_content = _make_csv_content([
            _valid_csv_row(),
            {"type": "", "value": "V", "project_name": "P", "budget_effort": "10", "project_status": "Active"},
            _valid_csv_row("T", "V2", "P2", "20", "Active"),
            {"type": "T", "value": "", "project_name": "", "budget_effort": "-1", "project_status": ""},
        ])
        s3.get_object.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=csv_content.encode("utf-8")))
        }

        event = _superadmin_event({"file": {"key": "imports/test.csv"}})
        result = mod.bulk_import_csv(event)

        assert result["importedCount"] == 2
        assert result["rejectedCount"] == 2
        row_numbers = [r["row"] for r in result["rejectedRows"]]
        assert row_numbers == [2, 4]
        # Row 2 has 1 error (missing type), row 4 has multiple errors
        assert len(result["rejectedRows"][0]["errors"]) >= 1
        assert len(result["rejectedRows"][1]["errors"]) >= 1


# ---------------------------------------------------------------------------
# Requirement 14.5 — Refresh replaces all existing records
# ---------------------------------------------------------------------------


class TestRefreshDatabase:
    """RefreshDatabase should delete all existing records and replace them
    with imported CSV data, logging the operation."""

    def test_refresh_deletes_existing_and_imports_new(self, _mock_boto):
        """Refresh clears the table then writes new records.

        Validates: Requirements 14.5
        """
        mod = _mock_boto["refresh_mod"]
        s3 = _mock_boto["s3_client"]

        csv_content = _make_csv_content([
            _valid_csv_row("Chargeable", "P1", "Project 1", "100", "Active"),
            _valid_csv_row("Non-Chargeable", "P2", "Project 2", "200", "Inactive"),
        ])
        s3.get_object.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=csv_content.encode("utf-8")))
        }

        with patch.object(mod, "delete_all_records") as mock_delete, \
             patch.object(mod, "batch_write_items") as mock_write:
            event = _superadmin_event({"file": {"key": "imports/refresh.csv"}})
            result = mod.refresh_database(event)

        mock_delete.assert_called_once()
        mock_write.assert_called_once()
        written_items = mock_write.call_args[0][1]
        assert len(written_items) == 2
        assert result["importedCount"] == 2
        assert result["rejectedCount"] == 0

    def test_refresh_returns_timestamp_and_user(self, _mock_boto):
        """Refresh result includes refreshedAt and refreshedBy.

        Validates: Requirements 14.5
        """
        mod = _mock_boto["refresh_mod"]
        s3 = _mock_boto["s3_client"]

        csv_content = _make_csv_content([_valid_csv_row()])
        s3.get_object.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=csv_content.encode("utf-8")))
        }

        with patch.object(mod, "delete_all_records"), \
             patch.object(mod, "batch_write_items"):
            event = _superadmin_event({"file": {"key": "imports/refresh.csv"}})
            result = mod.refresh_database(event)

        assert "refreshedAt" in result
        assert result["refreshedBy"] == "superadmin-001"

    def test_refresh_deletes_even_when_all_rows_invalid(self, _mock_boto):
        """Refresh still clears existing records even if all CSV rows are invalid.

        Validates: Requirements 14.5
        """
        mod = _mock_boto["refresh_mod"]
        s3 = _mock_boto["s3_client"]

        csv_content = _make_csv_content([
            {"type": "", "value": "", "project_name": "", "budget_effort": "", "project_status": ""},
        ])
        s3.get_object.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=csv_content.encode("utf-8")))
        }

        with patch.object(mod, "delete_all_records") as mock_delete, \
             patch.object(mod, "batch_write_items") as mock_write:
            event = _superadmin_event({"file": {"key": "imports/refresh.csv"}})
            result = mod.refresh_database(event)

        # Table is still cleared
        mock_delete.assert_called_once()
        # No valid items to write
        mock_write.assert_not_called()
        assert result["importedCount"] == 0
        assert result["rejectedCount"] == 1

    def test_refresh_with_mixed_rows(self, _mock_boto):
        """Refresh with mix of valid/invalid rows: deletes all, writes only valid.

        Validates: Requirements 14.4, 14.5
        """
        mod = _mock_boto["refresh_mod"]
        s3 = _mock_boto["s3_client"]

        csv_content = _make_csv_content([
            _valid_csv_row("Chargeable", "P1", "Project 1", "100", "Active"),
            {"type": "", "value": "", "project_name": "", "budget_effort": "bad", "project_status": ""},
            _valid_csv_row("Non-Chargeable", "P3", "Project 3", "300", "Active"),
        ])
        s3.get_object.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=csv_content.encode("utf-8")))
        }

        with patch.object(mod, "delete_all_records") as mock_delete, \
             patch.object(mod, "batch_write_items") as mock_write:
            event = _superadmin_event({"file": {"key": "imports/refresh.csv"}})
            result = mod.refresh_database(event)

        mock_delete.assert_called_once()
        mock_write.assert_called_once()
        written_items = mock_write.call_args[0][1]
        assert len(written_items) == 2
        assert result["importedCount"] == 2
        assert result["rejectedCount"] == 1
        assert result["rejectedRows"][0]["row"] == 2
