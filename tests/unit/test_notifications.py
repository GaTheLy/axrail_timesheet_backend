"""Unit tests for Notification Service and Notification Config Lambdas.

Validates: Requirements 12.1, 12.3, 12.6 (notification handler)
           Requirements 12.4, 12.5, 12.7 (config management)
"""

import csv
import io
import os
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch, call

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lambdas"))

os.environ.setdefault("SUBMISSIONS_TABLE", "SubmissionsTable")
os.environ.setdefault("ENTRIES_TABLE", "EntriesTable")
os.environ.setdefault("USERS_TABLE", "UsersTable")
os.environ.setdefault("PROJECTS_TABLE", "ProjectsTable")
os.environ.setdefault("EMPLOYEE_PERFORMANCE_TABLE", "PerformanceTable")
os.environ.setdefault("PERIODS_TABLE", "PeriodsTable")
os.environ.setdefault("REPORT_DISTRIBUTION_CONFIG_TABLE", "ConfigTable")
os.environ.setdefault("REPORT_BUCKET", "report-bucket")
os.environ.setdefault("SES_FROM_EMAIL", "noreply@example.com")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(enabled=True, recipient_emails=None, cron="cron(0 8 ? * MON *)"):
    return {
        "configId": "default",
        "schedule_cron_expression": cron,
        "recipient_emails": recipient_emails if recipient_emails is not None else ["pm@example.com"],
        "enabled": enabled,
    }


def _make_period(period_id="period-001", period_string="2025-01-04 to 2025-01-10"):
    return {
        "periodId": period_id,
        "startDate": "2025-01-04",
        "endDate": "2025-01-10",
        "submissionDeadline": "2025-01-10T23:59:59+00:00",
        "periodString": period_string,
    }


def _make_tech_lead(user_id="tl-001", email="tl@example.com", full_name="Tech Lead One"):
    return {
        "userId": user_id,
        "email": email,
        "fullName": full_name,
        "role": "Tech_Lead",
        "userType": "admin",
    }


def _make_superadmin_event(args=None):
    return {
        "identity": {
            "claims": {
                "sub": "superadmin-001",
                "custom:userType": "superadmin",
                "custom:role": "Superadmin",
                "email": "admin@example.com",
            }
        },
        "arguments": {"input": args or {}},
    }


def _make_admin_event(args=None):
    return {
        "identity": {
            "claims": {
                "sub": "admin-001",
                "custom:userType": "admin",
                "custom:role": "Project_Manager",
                "email": "pm@example.com",
            }
        },
        "arguments": {"input": args or {}},
    }


def _parse_csv(csv_content):
    reader = csv.DictReader(io.StringIO(csv_content))
    return list(reader)


# ---------------------------------------------------------------------------
# Fixtures — Notification Handler
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_notif():
    """Patch boto3 resources used at module level in the notifications handler."""
    mock_config_table = MagicMock()
    mock_periods_table = MagicMock()
    mock_submissions_table = MagicMock()
    mock_entries_table = MagicMock()
    mock_users_table = MagicMock()
    mock_projects_table = MagicMock()
    mock_performance_table = MagicMock()

    def _table_router(name):
        mapping = {
            "ConfigTable": mock_config_table,
            "PeriodsTable": mock_periods_table,
            "SubmissionsTable": mock_submissions_table,
            "EntriesTable": mock_entries_table,
            "UsersTable": mock_users_table,
            "ProjectsTable": mock_projects_table,
            "PerformanceTable": mock_performance_table,
        }
        return mapping.get(name, MagicMock())

    mock_dynamodb = MagicMock()
    mock_dynamodb.Table.side_effect = _table_router

    mock_ses = MagicMock()
    mock_ses.send_raw_email.return_value = {"MessageId": "msg-001"}

    mock_s3 = MagicMock()

    # Defaults
    mock_config_table.get_item.return_value = {}
    mock_periods_table.scan.return_value = {"Items": []}
    mock_submissions_table.query.return_value = {"Items": []}
    mock_entries_table.query.return_value = {"Items": []}
    mock_users_table.scan.return_value = {"Items": []}
    mock_users_table.query.return_value = {"Items": []}
    mock_projects_table.scan.return_value = {"Items": []}
    mock_performance_table.get_item.return_value = {}

    with patch("boto3.resource", return_value=mock_dynamodb), \
         patch("boto3.client") as mock_client_factory:

        def _client_router(service, **kwargs):
            if service == "ses":
                return mock_ses
            if service == "s3":
                return mock_s3
            return MagicMock()

        mock_client_factory.side_effect = _client_router

        # Clear cached module so module-level globals pick up mocks
        for mod_name in list(sys.modules):
            if "notifications" in mod_name and "handler" in mod_name:
                del sys.modules[mod_name]

        from lambdas.notifications import handler as notif_mod

        notif_mod.dynamodb = mock_dynamodb
        notif_mod.ses_client = mock_ses
        notif_mod.s3_client = mock_s3
        notif_mod.SES_FROM_EMAIL = "noreply@example.com"

        yield {
            "mod": notif_mod,
            "ses": mock_ses,
            "config_table": mock_config_table,
            "periods_table": mock_periods_table,
            "submissions_table": mock_submissions_table,
            "entries_table": mock_entries_table,
            "users_table": mock_users_table,
            "projects_table": mock_projects_table,
            "performance_table": mock_performance_table,
        }


# ---------------------------------------------------------------------------
# Fixtures — Notification Config Handlers
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_get_config():
    """Patch boto3 for GetReportDistributionConfig handler."""
    mock_config_table = MagicMock()

    def _table_router(name):
        if name == "ConfigTable":
            return mock_config_table
        return MagicMock()

    mock_dynamodb = MagicMock()
    mock_dynamodb.Table.side_effect = _table_router

    mock_config_table.get_item.return_value = {}

    with patch("boto3.resource", return_value=mock_dynamodb):
        for mod_name in list(sys.modules):
            if "GetReportDistributionConfig" in mod_name:
                del sys.modules[mod_name]

        from lambdas.notification_config.GetReportDistributionConfig import (
            handler as get_config_mod,
        )

        get_config_mod.dynamodb = mock_dynamodb

        yield {
            "mod": get_config_mod,
            "config_table": mock_config_table,
        }


@pytest.fixture()
def mock_update_config():
    """Patch boto3 for UpdateReportDistributionConfig handler."""
    mock_config_table = MagicMock()

    def _table_router(name):
        if name == "ConfigTable":
            return mock_config_table
        return MagicMock()

    mock_dynamodb = MagicMock()
    mock_dynamodb.Table.side_effect = _table_router

    mock_config_table.update_item.return_value = {"Attributes": {}}

    with patch("boto3.resource", return_value=mock_dynamodb):
        for mod_name in list(sys.modules):
            if "UpdateReportDistributionConfig" in mod_name:
                del sys.modules[mod_name]

        from lambdas.notification_config.UpdateReportDistributionConfig import (
            handler as update_config_mod,
        )

        update_config_mod.dynamodb = mock_dynamodb

        yield {
            "mod": update_config_mod,
            "config_table": mock_config_table,
        }


# ===========================================================================
# Notification Handler Tests
# ===========================================================================


# ---------------------------------------------------------------------------
# Requirement 12.1 — Email sending with CSV attachment (Project Summary)
# ---------------------------------------------------------------------------


class TestProjectSummaryEmailSending:
    """Project Summary CSV is generated and sent via SES to configured recipients."""

    def test_project_summary_sent_to_all_recipients(self, mock_notif):
        """Project Summary email is sent to each configured recipient.

        Validates: Requirements 12.1
        """
        mod = mock_notif["mod"]
        ses = mock_notif["ses"]

        config = _make_config(recipient_emails=["pm1@example.com", "pm2@example.com"])
        period = _make_period()

        with patch.object(mod, "_get_distribution_config", return_value=config), \
             patch.object(mod, "_get_current_period", return_value=period), \
             patch.object(mod, "_generate_project_summary_csv", return_value="col1,col2\nv1,v2\n"), \
             patch.object(mod, "_get_tech_leads", return_value=[]):
            result = mod.handler({}, None)

        assert result["sent"] == 2
        assert result["errors"] == 0
        assert ses.send_raw_email.call_count == 2

        # Verify both recipients received emails
        destinations = [
            c[1]["Destinations"][0]
            for c in ses.send_raw_email.call_args_list
        ]
        assert set(destinations) == {"pm1@example.com", "pm2@example.com"}

    def test_project_summary_email_contains_csv_attachment(self, mock_notif):
        """The SES raw email includes a CSV attachment.

        Validates: Requirements 12.1, 12.3
        """
        mod = mock_notif["mod"]
        ses = mock_notif["ses"]

        csv_content = "Project Charge Code,Project Name\nPROJ-001,Alpha\n"
        config = _make_config(recipient_emails=["pm@example.com"])
        period = _make_period()

        with patch.object(mod, "_get_distribution_config", return_value=config), \
             patch.object(mod, "_get_current_period", return_value=period), \
             patch.object(mod, "_generate_project_summary_csv", return_value=csv_content), \
             patch.object(mod, "_get_tech_leads", return_value=[]):
            mod.handler({}, None)

        raw_msg = ses.send_raw_email.call_args[1]["RawMessage"]["Data"]
        assert "project_summary_period-001.csv" in raw_msg
        assert "text/csv" in raw_msg
        assert "Project Summary Report" in raw_msg

    def test_skips_when_no_recipients_configured(self, mock_notif):
        """No emails sent when recipient_emails is empty.

        Validates: Requirements 12.1
        """
        mod = mock_notif["mod"]
        ses = mock_notif["ses"]

        config = _make_config(recipient_emails=[])
        period = _make_period()

        with patch.object(mod, "_get_distribution_config", return_value=config), \
             patch.object(mod, "_get_current_period", return_value=period), \
             patch.object(mod, "_generate_project_summary_csv") as mock_gen, \
             patch.object(mod, "_get_tech_leads", return_value=[]):
            result = mod.handler({}, None)

        mock_gen.assert_not_called()
        assert result["sent"] == 0

    def test_skips_when_csv_generation_returns_none(self, mock_notif):
        """No email sent when project summary CSV generation returns None.

        Validates: Requirements 12.1
        """
        mod = mock_notif["mod"]
        ses = mock_notif["ses"]

        config = _make_config(recipient_emails=["pm@example.com"])
        period = _make_period()

        with patch.object(mod, "_get_distribution_config", return_value=config), \
             patch.object(mod, "_get_current_period", return_value=period), \
             patch.object(mod, "_generate_project_summary_csv", return_value=None), \
             patch.object(mod, "_get_tech_leads", return_value=[]):
            result = mod.handler({}, None)

        ses.send_raw_email.assert_not_called()
        assert result["sent"] == 0


# ---------------------------------------------------------------------------
# Requirement 12.2 — TC Summary sent to each Tech Lead
# ---------------------------------------------------------------------------


class TestTCSummaryEmailSending:
    """TC Summary CSV is generated per Tech Lead and sent to their email."""

    def test_tc_summary_sent_to_tech_lead(self, mock_notif):
        """Each Tech Lead receives their TC Summary via email.

        Validates: Requirements 12.1, 12.3
        """
        mod = mock_notif["mod"]
        ses = mock_notif["ses"]

        config = _make_config(recipient_emails=[])
        period = _make_period()
        tl = _make_tech_lead("tl-001", "tl@example.com", "Tech Lead One")

        with patch.object(mod, "_get_distribution_config", return_value=config), \
             patch.object(mod, "_get_current_period", return_value=period), \
             patch.object(mod, "_generate_project_summary_csv", return_value=None), \
             patch.object(mod, "_get_tech_leads", return_value=[tl]), \
             patch.object(mod, "_generate_tc_summary_csv", return_value="Name,Hours\nAlice,40\n"):
            result = mod.handler({}, None)

        assert result["sent"] == 1
        ses.send_raw_email.assert_called_once()
        call_kwargs = ses.send_raw_email.call_args[1]
        assert call_kwargs["Destinations"] == ["tl@example.com"]
        raw_msg = call_kwargs["RawMessage"]["Data"]
        assert "TC Summary Report" in raw_msg
        assert "tc_summary_tl-001_period-001.csv" in raw_msg

    def test_multiple_tech_leads_each_get_email(self, mock_notif):
        """Multiple Tech Leads each receive their own TC Summary.

        Validates: Requirements 12.1
        """
        mod = mock_notif["mod"]
        ses = mock_notif["ses"]

        config = _make_config(recipient_emails=[])
        period = _make_period()
        tl1 = _make_tech_lead("tl-001", "tl1@example.com", "TL One")
        tl2 = _make_tech_lead("tl-002", "tl2@example.com", "TL Two")

        with patch.object(mod, "_get_distribution_config", return_value=config), \
             patch.object(mod, "_get_current_period", return_value=period), \
             patch.object(mod, "_generate_project_summary_csv", return_value=None), \
             patch.object(mod, "_get_tech_leads", return_value=[tl1, tl2]), \
             patch.object(mod, "_generate_tc_summary_csv", return_value="Name,Hours\nBob,20\n"):
            result = mod.handler({}, None)

        assert result["sent"] == 2
        assert ses.send_raw_email.call_count == 2

    def test_tech_lead_without_email_skipped(self, mock_notif):
        """Tech Lead with no email address is skipped.

        Validates: Requirements 12.1
        """
        mod = mock_notif["mod"]
        ses = mock_notif["ses"]

        config = _make_config(recipient_emails=[])
        period = _make_period()
        tl = _make_tech_lead("tl-001", "", "No Email TL")

        with patch.object(mod, "_get_distribution_config", return_value=config), \
             patch.object(mod, "_get_current_period", return_value=period), \
             patch.object(mod, "_generate_project_summary_csv", return_value=None), \
             patch.object(mod, "_get_tech_leads", return_value=[tl]), \
             patch.object(mod, "_generate_tc_summary_csv") as mock_gen:
            result = mod.handler({}, None)

        mock_gen.assert_not_called()
        ses.send_raw_email.assert_not_called()
        assert result["sent"] == 0

    def test_tc_summary_none_skips_email(self, mock_notif):
        """When TC Summary CSV is None (no data), no email is sent.

        Validates: Requirements 12.1
        """
        mod = mock_notif["mod"]
        ses = mock_notif["ses"]

        config = _make_config(recipient_emails=[])
        period = _make_period()
        tl = _make_tech_lead("tl-001", "tl@example.com")

        with patch.object(mod, "_get_distribution_config", return_value=config), \
             patch.object(mod, "_get_current_period", return_value=period), \
             patch.object(mod, "_generate_project_summary_csv", return_value=None), \
             patch.object(mod, "_get_tech_leads", return_value=[tl]), \
             patch.object(mod, "_generate_tc_summary_csv", return_value=None):
            result = mod.handler({}, None)

        ses.send_raw_email.assert_not_called()
        assert result["sent"] == 0


# ---------------------------------------------------------------------------
# Requirement 12.6 — Failure logging on SES errors
# ---------------------------------------------------------------------------


class TestSESFailureLogging:
    """On SES failure, log recipient, report type, and error details."""

    def test_ses_error_logged_and_counted(self, mock_notif):
        """SES send failure is logged and counted as an error.

        Validates: Requirements 12.6
        """
        mod = mock_notif["mod"]
        ses = mock_notif["ses"]
        ses.send_raw_email.side_effect = Exception("SES throttling error")

        config = _make_config(recipient_emails=["pm@example.com"])
        period = _make_period()

        with patch.object(mod, "_get_distribution_config", return_value=config), \
             patch.object(mod, "_get_current_period", return_value=period), \
             patch.object(mod, "_generate_project_summary_csv", return_value="a,b\n1,2\n"), \
             patch.object(mod, "_get_tech_leads", return_value=[]):
            result = mod.handler({}, None)

        assert result["errors"] == 1
        assert result["sent"] == 0

    def test_ses_error_does_not_crash_handler(self, mock_notif):
        """SES failure does not prevent processing remaining recipients.

        Validates: Requirements 12.6
        """
        mod = mock_notif["mod"]
        ses = mock_notif["ses"]

        # First call fails, second succeeds
        ses.send_raw_email.side_effect = [
            Exception("SES error"),
            {"MessageId": "msg-002"},
        ]

        config = _make_config(recipient_emails=["fail@example.com", "ok@example.com"])
        period = _make_period()

        with patch.object(mod, "_get_distribution_config", return_value=config), \
             patch.object(mod, "_get_current_period", return_value=period), \
             patch.object(mod, "_generate_project_summary_csv", return_value="a,b\n1,2\n"), \
             patch.object(mod, "_get_tech_leads", return_value=[]):
            result = mod.handler({}, None)

        assert result["sent"] == 1
        assert result["errors"] == 1
        assert ses.send_raw_email.call_count == 2

    def test_tc_summary_ses_error_logged(self, mock_notif):
        """SES failure for TC Summary email is logged and counted.

        Validates: Requirements 12.6
        """
        mod = mock_notif["mod"]
        ses = mock_notif["ses"]
        ses.send_raw_email.side_effect = Exception("SES bounce")

        config = _make_config(recipient_emails=[])
        period = _make_period()
        tl = _make_tech_lead("tl-001", "tl@example.com")

        with patch.object(mod, "_get_distribution_config", return_value=config), \
             patch.object(mod, "_get_current_period", return_value=period), \
             patch.object(mod, "_generate_project_summary_csv", return_value=None), \
             patch.object(mod, "_get_tech_leads", return_value=[tl]), \
             patch.object(mod, "_generate_tc_summary_csv", return_value="Name,Hours\nAlice,40\n"):
            result = mod.handler({}, None)

        assert result["errors"] == 1
        assert result["sent"] == 0


    def test_send_email_returns_false_on_failure(self, mock_notif):
        """_send_email_with_attachment returns False on SES exception.

        Validates: Requirements 12.6
        """
        mod = mock_notif["mod"]
        ses = mock_notif["ses"]
        ses.send_raw_email.side_effect = Exception("Connection refused")

        result = mod._send_email_with_attachment(
            recipient="fail@example.com",
            subject="Test",
            body_text="Body",
            attachment_content="col\nval\n",
            attachment_filename="test.csv",
            report_type="Project Summary",
        )

        assert result is False

    def test_send_email_returns_true_on_success(self, mock_notif):
        """_send_email_with_attachment returns True on successful send.

        Validates: Requirements 12.3
        """
        mod = mock_notif["mod"]

        result = mod._send_email_with_attachment(
            recipient="ok@example.com",
            subject="Test",
            body_text="Body",
            attachment_content="col\nval\n",
            attachment_filename="test.csv",
            report_type="TC Summary",
        )

        assert result is True


# ---------------------------------------------------------------------------
# Handler edge cases — disabled config, no period
# ---------------------------------------------------------------------------


class TestHandlerEdgeCases:
    """Handler should gracefully handle disabled config and missing periods."""

    def test_disabled_config_skips_all(self, mock_notif):
        """When enabled=False, no reports are generated or sent.

        Validates: Requirements 12.1
        """
        mod = mock_notif["mod"]
        ses = mock_notif["ses"]

        config = _make_config(enabled=False)

        with patch.object(mod, "_get_distribution_config", return_value=config):
            result = mod.handler({}, None)

        assert result == {"sent": 0, "errors": 0}
        ses.send_raw_email.assert_not_called()

    def test_no_config_skips_all(self, mock_notif):
        """When no config exists, handler returns zero counts.

        Validates: Requirements 12.1
        """
        mod = mock_notif["mod"]
        ses = mock_notif["ses"]

        with patch.object(mod, "_get_distribution_config", return_value=None):
            result = mod.handler({}, None)

        assert result == {"sent": 0, "errors": 0}
        ses.send_raw_email.assert_not_called()

    def test_no_active_period_skips_all(self, mock_notif):
        """When no active period found, handler returns zero counts.

        Validates: Requirements 12.1
        """
        mod = mock_notif["mod"]
        ses = mock_notif["ses"]

        config = _make_config()

        with patch.object(mod, "_get_distribution_config", return_value=config), \
             patch.object(mod, "_get_current_period", return_value=None):
            result = mod.handler({}, None)

        assert result == {"sent": 0, "errors": 0}
        ses.send_raw_email.assert_not_called()


# ===========================================================================
# Notification Config Handler Tests
# ===========================================================================


# ---------------------------------------------------------------------------
# Requirement 12.5 — Get config retrieves current configuration
# ---------------------------------------------------------------------------


class TestGetReportDistributionConfig:
    """get_report_distribution_config returns stored or default config."""

    def test_returns_existing_config(self, mock_get_config):
        """Returns the stored config when it exists.

        Validates: Requirements 12.5
        """
        mod = mock_get_config["mod"]
        table = mock_get_config["config_table"]

        stored = _make_config(enabled=True, recipient_emails=["a@b.com"])
        table.get_item.return_value = {"Item": stored}

        event = _make_superadmin_event()
        result = mod.get_report_distribution_config(event)

        assert result["enabled"] is True
        assert result["recipient_emails"] == ["a@b.com"]
        assert result["configId"] == "default"

    def test_returns_default_when_no_config(self, mock_get_config):
        """Returns a default config when none exists in DynamoDB.

        Validates: Requirements 12.5
        """
        mod = mock_get_config["mod"]
        table = mock_get_config["config_table"]
        table.get_item.return_value = {}

        event = _make_superadmin_event()
        result = mod.get_report_distribution_config(event)

        assert result["configId"] == "default"
        assert result["enabled"] is False
        assert result["recipient_emails"] == []
        assert result["schedule_cron_expression"] == ""


# ---------------------------------------------------------------------------
# Requirement 12.4, 12.5, 12.7 — Update config persists correctly
# ---------------------------------------------------------------------------


class TestUpdateReportDistributionConfig:
    """update_report_distribution_config persists schedule, emails, enabled."""

    def test_update_all_fields(self, mock_update_config):
        """Superadmin can update cron, emails, and enabled flag.

        Validates: Requirements 12.4, 12.5
        """
        mod = mock_update_config["mod"]
        table = mock_update_config["config_table"]

        updated_item = {
            "configId": "default",
            "schedule_cron_expression": "cron(0 9 ? * FRI *)",
            "recipient_emails": ["new@example.com"],
            "enabled": True,
            "updatedBy": "superadmin-001",
        }
        table.update_item.return_value = {"Attributes": updated_item}

        event = _make_superadmin_event({
            "schedule_cron_expression": "cron(0 9 ? * FRI *)",
            "recipient_emails": ["new@example.com"],
            "enabled": True,
        })
        result = mod.update_report_distribution_config(event)

        assert result["schedule_cron_expression"] == "cron(0 9 ? * FRI *)"
        assert result["recipient_emails"] == ["new@example.com"]
        assert result["enabled"] is True

        # Verify DynamoDB update_item was called with correct key
        table.update_item.assert_called_once()
        call_kwargs = table.update_item.call_args[1]
        assert call_kwargs["Key"] == {"configId": "default"}
        assert ":schedule_cron_expression" in call_kwargs["ExpressionAttributeValues"]
        assert ":recipient_emails" in call_kwargs["ExpressionAttributeValues"]
        assert ":enabled" in call_kwargs["ExpressionAttributeValues"]

    def test_update_enabled_flag_only(self, mock_update_config):
        """Superadmin can toggle enabled without changing other fields.

        Validates: Requirements 12.7
        """
        mod = mock_update_config["mod"]
        table = mock_update_config["config_table"]

        table.update_item.return_value = {"Attributes": {"enabled": False}}

        event = _make_superadmin_event({"enabled": False})
        mod.update_report_distribution_config(event)

        call_kwargs = table.update_item.call_args[1]
        assert call_kwargs["ExpressionAttributeValues"][":enabled"] is False
        # schedule_cron_expression and recipient_emails should NOT be in the update
        assert ":schedule_cron_expression" not in call_kwargs["ExpressionAttributeValues"]
        assert ":recipient_emails" not in call_kwargs["ExpressionAttributeValues"]

    def test_non_superadmin_rejected(self, mock_update_config):
        """Non-superadmin users are rejected with ForbiddenError.

        Validates: Requirements 12.4
        """
        mod = mock_update_config["mod"]

        event = _make_admin_event({"enabled": True})

        with pytest.raises(Exception, match="not authorized"):
            mod.handler(event, None)

    def test_update_records_updatedby(self, mock_update_config):
        """The update persists updatedBy with the caller's userId.

        Validates: Requirements 12.4
        """
        mod = mock_update_config["mod"]
        table = mock_update_config["config_table"]
        table.update_item.return_value = {"Attributes": {}}

        event = _make_superadmin_event({"enabled": True})
        mod.update_report_distribution_config(event)

        call_kwargs = table.update_item.call_args[1]
        assert call_kwargs["ExpressionAttributeValues"][":updatedBy"] == "superadmin-001"
        assert ":updatedAt" in call_kwargs["ExpressionAttributeValues"]
