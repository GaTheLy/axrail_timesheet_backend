"""Unit tests for lambdas/projects/handler.py — Project Management resolvers.

Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.6
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lambdas"))

os.environ.setdefault("PROJECTS_TABLE", "ProjectsTable")


def _make_event(
    field_name="createProject",
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


_DEFAULT_INPUT = {
    "projectCode": "PRJ-001",
    "projectName": "Test Project",
    "startDate": "2025-01-01",
    "plannedHours": 100.0,
    "projectManagerId": "pm-001",
}

_PENDING_PROJECT = {
    "projectId": "proj-100",
    "projectCode": "PRJ-001",
    "projectName": "Test Project",
    "approval_status": "Pending_Approval",
}

_APPROVED_PROJECT = {
    **_PENDING_PROJECT,
    "approval_status": "Approved",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _mock_boto(monkeypatch):
    """Patch boto3.resource so DynamoDB calls hit mocks."""
    mock_table = MagicMock()
    mock_table.query.return_value = {"Items": []}
    mock_table.put_item.return_value = {}
    mock_table.get_item.return_value = {"Item": {**_PENDING_PROJECT}}
    mock_table.update_item.return_value = {"Attributes": {**_APPROVED_PROJECT}}
    mock_table.scan.return_value = {"Items": []}

    mock_dynamodb = MagicMock()
    mock_dynamodb.Table.return_value = mock_table

    with patch("boto3.resource", return_value=mock_dynamodb):
        if "lambdas.projects.handler" in sys.modules:
            del sys.modules["lambdas.projects.handler"]
        from lambdas.projects import handler as mod

        mod.dynamodb = mock_dynamodb

        yield {
            "table": mock_table,
            "handler_mod": mod,
        }


# ---------------------------------------------------------------------------
# Superadmin creates with Approved status — Requirement 4.1
# ---------------------------------------------------------------------------


class TestSuperadminCreatesApproved:
    def test_superadmin_creates_project_with_approved_status(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        event = _make_event(
            user_type="superadmin",
            arguments={"input": {**_DEFAULT_INPUT}},
        )
        result = mod.create_project(event)
        assert result["approval_status"] == "Approved"
        assert result["projectCode"] == "PRJ-001"

    def test_superadmin_create_persists_all_fields(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        event = _make_event(
            user_type="superadmin",
            arguments={"input": {**_DEFAULT_INPUT}},
        )
        result = mod.create_project(event)
        assert result["projectName"] == "Test Project"
        assert result["projectManagerId"] == "pm-001"
        assert "projectId" in result
        assert "createdAt" in result


# ---------------------------------------------------------------------------
# Admin creates with Pending_Approval status — Requirement 4.2
# ---------------------------------------------------------------------------


class TestAdminCreatesPendingApproval:
    def test_admin_creates_project_with_pending_status(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        event = _make_event(
            user_type="admin",
            arguments={"input": {**_DEFAULT_INPUT}},
        )
        result = mod.create_project(event)
        assert result["approval_status"] == "Pending_Approval"

    def test_regular_user_forbidden_from_creating(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        event = _make_event(
            user_type="user",
            arguments={"input": {**_DEFAULT_INPUT}},
        )
        with pytest.raises(Exception, match="not authorized"):
            mod.handler(event, None)


# ---------------------------------------------------------------------------
# Approval / Rejection state transitions — Requirements 4.3, 4.4
# ---------------------------------------------------------------------------


class TestApprovalTransitions:
    def test_approve_pending_project_succeeds(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        table = _mock_boto["table"]
        table.get_item.return_value = {"Item": {**_PENDING_PROJECT}}
        table.update_item.return_value = {
            "Attributes": {**_PENDING_PROJECT, "approval_status": "Approved"}
        }
        event = _make_event(
            field_name="approveProject",
            arguments={"projectId": "proj-100"},
        )
        result = mod.approve_project(event)
        assert result["approval_status"] == "Approved"

    def test_approve_already_approved_project_rejected(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        table = _mock_boto["table"]
        table.get_item.return_value = {"Item": {**_APPROVED_PROJECT}}
        event = _make_event(
            field_name="approveProject",
            arguments={"projectId": "proj-100"},
        )
        with pytest.raises(ValueError, match="Only Pending_Approval"):
            mod.approve_project(event)

    def test_approve_rejected_project_rejected(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        table = _mock_boto["table"]
        table.get_item.return_value = {
            "Item": {**_PENDING_PROJECT, "approval_status": "Rejected"}
        }
        event = _make_event(
            field_name="approveProject",
            arguments={"projectId": "proj-100"},
        )
        with pytest.raises(ValueError, match="Only Pending_Approval"):
            mod.approve_project(event)

    def test_approve_nonexistent_project_raises(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        table = _mock_boto["table"]
        table.get_item.return_value = {}
        event = _make_event(
            field_name="approveProject",
            arguments={"projectId": "proj-missing"},
        )
        with pytest.raises(ValueError, match="not found"):
            mod.approve_project(event)

    def test_reject_pending_project_succeeds(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        table = _mock_boto["table"]
        table.get_item.return_value = {"Item": {**_PENDING_PROJECT}}
        table.update_item.return_value = {
            "Attributes": {
                **_PENDING_PROJECT,
                "approval_status": "Rejected",
                "rejectionReason": "Budget exceeded",
            }
        }
        event = _make_event(
            field_name="rejectProject",
            arguments={"projectId": "proj-100", "reason": "Budget exceeded"},
        )
        result = mod.reject_project(event)
        assert result["approval_status"] == "Rejected"
        assert result["rejectionReason"] == "Budget exceeded"

    def test_reject_already_approved_project_rejected(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        table = _mock_boto["table"]
        table.get_item.return_value = {"Item": {**_APPROVED_PROJECT}}
        event = _make_event(
            field_name="rejectProject",
            arguments={"projectId": "proj-100", "reason": "Not needed"},
        )
        with pytest.raises(ValueError, match="Only Pending_Approval"):
            mod.reject_project(event)

    def test_reject_without_reason_raises(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        event = _make_event(
            field_name="rejectProject",
            arguments={"projectId": "proj-100", "reason": ""},
        )
        with pytest.raises(ValueError, match="Rejection reason is required"):
            mod.reject_project(event)

    def test_admin_forbidden_from_approving(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        event = _make_event(
            field_name="approveProject",
            user_type="admin",
            arguments={"projectId": "proj-100"},
        )
        with pytest.raises(Exception, match="not authorized"):
            mod.handler(event, None)

    def test_admin_forbidden_from_rejecting(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        event = _make_event(
            field_name="rejectProject",
            user_type="admin",
            arguments={"projectId": "proj-100", "reason": "No"},
        )
        with pytest.raises(Exception, match="not authorized"):
            mod.handler(event, None)


# ---------------------------------------------------------------------------
# projectCode uniqueness enforcement — Requirement 4.6
# ---------------------------------------------------------------------------


class TestProjectCodeUniqueness:
    def test_duplicate_code_rejected_on_create(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        table = _mock_boto["table"]
        table.query.return_value = {
            "Items": [{"projectId": "proj-existing", "projectCode": "PRJ-001"}]
        }
        event = _make_event(arguments={"input": {**_DEFAULT_INPUT}})
        with pytest.raises(ValueError, match="already in use"):
            mod.create_project(event)

    def test_unique_code_accepted_on_create(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        table = _mock_boto["table"]
        table.query.return_value = {"Items": []}
        event = _make_event(arguments={"input": {**_DEFAULT_INPUT}})
        result = mod.create_project(event)
        assert result["projectCode"] == "PRJ-001"

    def test_duplicate_code_rejected_on_update(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        table = _mock_boto["table"]
        table.get_item.return_value = {
            "Item": {**_PENDING_PROJECT, "projectCode": "PRJ-OLD"}
        }
        table.query.return_value = {
            "Items": [{"projectId": "proj-other", "projectCode": "PRJ-001"}]
        }
        event = _make_event(
            field_name="updateProject",
            arguments={
                "projectId": "proj-100",
                "input": {"projectCode": "PRJ-001"},
            },
        )
        with pytest.raises(ValueError, match="already in use"):
            mod.update_project(event)

    def test_same_code_allowed_on_update_for_same_project(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        table = _mock_boto["table"]
        table.get_item.return_value = {"Item": {**_PENDING_PROJECT}}
        # GSI returns the same project — should be excluded from uniqueness check
        table.query.return_value = {
            "Items": [{"projectId": "proj-100", "projectCode": "PRJ-001"}]
        }
        table.update_item.return_value = {"Attributes": {**_PENDING_PROJECT}}
        event = _make_event(
            field_name="updateProject",
            arguments={
                "projectId": "proj-100",
                "input": {"projectCode": "PRJ-001"},
            },
        )
        result = mod.update_project(event)
        assert result is not None

    def test_invalid_planned_hours_rejected(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        event = _make_event(
            arguments={"input": {**_DEFAULT_INPUT, "plannedHours": -5}},
        )
        with pytest.raises(ValueError, match="positive number"):
            mod.create_project(event)
