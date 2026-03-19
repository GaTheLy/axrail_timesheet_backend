"""Preservation property tests for project edit permissions.

Property 2: Preservation — Existing Project Edit Permissions Unchanged

Tests that existing behavior for project editing is preserved on UNFIXED code:
- Admin editing a project with approval_status "Pending_Approval" succeeds
- Admin editing a project with approval_status "Rejected" succeeds
- Superadmin editing a project with any approval_status succeeds
- Regular user editing any project raises permissions error
- projectCode uniqueness, plannedHours positivity, and status enum validation enforced

These tests MUST PASS on the current UNFIXED code.

**Validates: Requirements 2.12, 2.13, 3.10, 3.11**
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

# Ensure the handler can resolve its shared imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lambdas"))

# Set required env vars before importing the handler
os.environ.setdefault("PROJECTS_TABLE", "ProjectsTable")


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

non_approved_status_st = st.sampled_from(["Pending_Approval", "Rejected"])
any_approval_status_st = st.sampled_from(["Pending_Approval", "Approved", "Rejected"])
project_name_st = st.from_regex(r"[A-Z][a-zA-Z0-9 ]{2,30}", fullmatch=True)
valid_status_st = st.sampled_from(["Active", "Inactive", "Completed"])

# Simple update inputs for preservation tests
update_input_st = st.fixed_dictionaries({
    "projectName": project_name_st,
})

# Positive planned hours for valid updates
positive_hours_st = st.decimals(min_value=0.1, max_value=10000, places=2, allow_nan=False, allow_infinity=False)

# Invalid planned hours
invalid_hours_st = st.one_of(
    st.decimals(max_value=0, places=2, allow_nan=False, allow_infinity=False),
    st.just(0),
    st.just(-1),
    st.just(-100),
)

invalid_status_st = st.from_regex(r"[A-Z][a-z]{3,10}", fullmatch=True).filter(
    lambda s: s not in {"Active", "Inactive", "Completed"}
)

regular_user_types_st = st.sampled_from(["user", "employee", "manager"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event(user_type, project_id, update_input):
    """Build a minimal AppSync event for updateProject."""
    return {
        "info": {"fieldName": "updateProject"},
        "identity": {
            "claims": {
                "sub": "caller-001",
                "custom:userType": user_type,
                "custom:role": "Tech_Lead",
                "email": "caller@axrail.com",
                "custom:departmentId": "dept-1",
                "custom:positionId": "pos-1",
            }
        },
        "arguments": {
            "projectId": project_id,
            "input": update_input,
        },
    }


def _make_project(project_id="proj-200", approval_status="Pending_Approval"):
    """Return a DynamoDB item representing a project with given approval status."""
    return {
        "projectId": project_id,
        "projectCode": "PRJ-200",
        "projectName": "Test Project",
        "approval_status": approval_status,
        "startDate": "2025-01-01",
        "plannedHours": 100,
        "projectManagerId": "pm-001",
        "status": "Active",
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _mock_boto(monkeypatch):
    """Patch boto3.resource so DynamoDB calls hit mocks."""
    project = _make_project()

    mock_table = MagicMock()
    mock_table.query.return_value = {"Items": []}  # no duplicate project codes
    mock_table.get_item.return_value = {"Item": {**project}}
    mock_table.update_item.return_value = {"Attributes": {**project}}

    mock_dynamodb = MagicMock()
    mock_dynamodb.Table.return_value = mock_table

    with patch("boto3.resource", return_value=mock_dynamodb):
        mod_key = "lambdas.projects.UpdateProject.handler"
        if mod_key in sys.modules:
            del sys.modules[mod_key]
        from lambdas.projects.UpdateProject import handler as mod

        mod.dynamodb = mock_dynamodb

        yield {
            "table": mock_table,
            "dynamodb": mock_dynamodb,
            "handler_mod": mod,
        }


# ---------------------------------------------------------------------------
# Property 2: Preservation — Existing Project Edit Permissions Unchanged
# ---------------------------------------------------------------------------

class TestAdminEditsNonApprovedProjects:
    """Admin editing projects with Pending_Approval or Rejected status succeeds."""

    @given(
        approval_status=non_approved_status_st,
        update_input=update_input_st,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_admin_can_edit_non_approved_project(self, approval_status, update_input, _mock_boto):
        """For any non-Approved approval_status, an admin can edit the project.

        **Validates: Requirements 2.12**
        """
        mod = _mock_boto["handler_mod"]
        table = _mock_boto["table"]

        project = _make_project(approval_status=approval_status)
        table.get_item.return_value = {"Item": {**project}}
        table.update_item.return_value = {"Attributes": {**project}}

        event = _make_event("admin", "proj-200", update_input)
        result = mod.update_project(event)

        # Should succeed — update_item was called
        table.update_item.assert_called()
        assert result is not None


class TestSuperadminEditsAnyProject:
    """Superadmin editing projects with any approval_status succeeds."""

    @given(
        approval_status=any_approval_status_st,
        update_input=update_input_st,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_superadmin_can_edit_any_project(self, approval_status, update_input, _mock_boto):
        """For any approval_status, a superadmin can edit the project.

        **Validates: Requirements 2.13**
        """
        mod = _mock_boto["handler_mod"]
        table = _mock_boto["table"]

        project = _make_project(approval_status=approval_status)
        table.get_item.return_value = {"Item": {**project}}
        table.update_item.return_value = {"Attributes": {**project}}

        event = _make_event("superadmin", "proj-200", update_input)
        result = mod.update_project(event)

        table.update_item.assert_called()
        assert result is not None


class TestRegularUserRejected:
    """Regular user editing any project raises permissions error."""

    @given(
        user_type=regular_user_types_st,
        approval_status=any_approval_status_st,
        update_input=update_input_st,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_regular_user_cannot_edit_any_project(self, user_type, approval_status, update_input, _mock_boto):
        """For any regular user type and any approval_status, editing raises ForbiddenError.

        **Validates: Requirements 3.10**
        """
        from shared.auth import ForbiddenError

        mod = _mock_boto["handler_mod"]
        table = _mock_boto["table"]

        project = _make_project(approval_status=approval_status)
        table.get_item.return_value = {"Item": {**project}}

        event = _make_event(user_type, "proj-200", update_input)

        with pytest.raises(ForbiddenError):
            mod.update_project(event)


class TestValidationStillEnforced:
    """projectCode uniqueness, plannedHours positivity, and status enum validation enforced."""

    @given(update_input=update_input_st)
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_duplicate_project_code_rejected(self, update_input, _mock_boto):
        """Duplicate projectCode is rejected for admin edits.

        **Validates: Requirements 3.11**
        """
        mod = _mock_boto["handler_mod"]
        table = _mock_boto["table"]

        project = _make_project(approval_status="Pending_Approval")
        table.get_item.return_value = {"Item": {**project}}
        # Simulate a different project with the same code
        table.query.return_value = {"Items": [{"projectId": "proj-other", "projectCode": "NEW-CODE"}]}

        input_with_code = {**update_input, "projectCode": "NEW-CODE"}
        event = _make_event("admin", "proj-200", input_with_code)

        with pytest.raises(ValueError, match="already in use"):
            mod.update_project(event)

    @given(bad_hours=invalid_hours_st)
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_invalid_planned_hours_rejected(self, bad_hours, _mock_boto):
        """Non-positive plannedHours is rejected.

        **Validates: Requirements 3.11**
        """
        mod = _mock_boto["handler_mod"]
        table = _mock_boto["table"]

        project = _make_project(approval_status="Pending_Approval")
        table.get_item.return_value = {"Item": {**project}}
        table.query.return_value = {"Items": []}

        input_with_hours = {"plannedHours": bad_hours}
        event = _make_event("admin", "proj-200", input_with_hours)

        with pytest.raises(ValueError, match="Must be a positive number"):
            mod.update_project(event)

    @given(bad_status=invalid_status_st)
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_invalid_status_rejected(self, bad_status, _mock_boto):
        """Invalid status enum value is rejected.

        **Validates: Requirements 3.11**
        """
        mod = _mock_boto["handler_mod"]
        table = _mock_boto["table"]

        project = _make_project(approval_status="Pending_Approval")
        table.get_item.return_value = {"Item": {**project}}
        table.query.return_value = {"Items": []}

        input_with_status = {"status": bad_status}
        event = _make_event("admin", "proj-200", input_with_status)

        with pytest.raises(ValueError, match="Invalid status"):
            mod.update_project(event)
