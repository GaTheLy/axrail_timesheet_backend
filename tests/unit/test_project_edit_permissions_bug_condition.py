"""Bug condition exploration test for project edit permissions.

Property 1: Bug Condition — Admin Can Edit Approved Projects

Tests that update_project() raises ForbiddenError when an admin attempts
to edit a project with approval_status == "Approved".
This test encodes the EXPECTED behavior from the design document.

On UNFIXED code, this test MUST FAIL — confirming the bug exists
(the system currently allows admins to edit approved projects).

**Validates: Requirements 1.8, 1.9, 2.11**
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
# Strategies — generate project update inputs for admin editing approved projects
# ---------------------------------------------------------------------------

project_name_st = st.from_regex(r"[A-Z][a-zA-Z0-9 ]{2,30}", fullmatch=True)

update_input_st = st.fixed_dictionaries({
    "projectName": project_name_st,
})


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


def _make_approved_project(project_id="proj-100"):
    """Return a DynamoDB item representing an approved project."""
    return {
        "projectId": project_id,
        "projectCode": "PRJ-100",
        "projectName": "Approved Project",
        "approval_status": "Approved",
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
    approved_project = _make_approved_project()

    mock_table = MagicMock()
    mock_table.query.return_value = {"Items": []}  # no duplicate project codes
    mock_table.get_item.return_value = {"Item": {**approved_project}}
    mock_table.update_item.return_value = {"Attributes": {**approved_project}}

    mock_dynamodb = MagicMock()
    mock_dynamodb.Table.return_value = mock_table

    with patch("boto3.resource", return_value=mock_dynamodb):
        # Force re-import so module-level globals pick up the mocks
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
# Property 1: Bug Condition — Admin Editing Approved Project Should Be Rejected
# ---------------------------------------------------------------------------

class TestProjectEditPermissionsBugCondition:
    """Bug condition: update_project() with admin caller and approval_status
    == 'Approved' should raise ForbiddenError. On unfixed code this test
    FAILS, confirming the bug exists."""

    @given(update_input=update_input_st)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_admin_cannot_edit_approved_project(self, update_input, _mock_boto):
        """For any update input, an admin editing an approved project must
        raise ForbiddenError.

        **Validates: Requirements 1.8, 1.9, 2.11**
        """
        from shared.auth import ForbiddenError

        mod = _mock_boto["handler_mod"]
        event = _make_event("admin", "proj-100", update_input)

        with pytest.raises(ForbiddenError, match="Only superadmins can edit"):
            mod.update_project(event)
