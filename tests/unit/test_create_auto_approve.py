"""Unit tests for auto-approve logic in Create handlers.

Verifies that superadmin-created entities get approval_status "Approved"
and admin-created entities get "Pending_Approval".

Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lambdas"))

os.environ.setdefault("DEPARTMENTS_TABLE", "DepartmentsTable")
os.environ.setdefault("POSITIONS_TABLE", "PositionsTable")
os.environ.setdefault("PROJECTS_TABLE", "ProjectsTable")


def _make_event(field_name, user_type="superadmin", user_id="caller-001", arguments=None):
    return {
        "info": {"fieldName": field_name},
        "identity": {
            "claims": {
                "sub": user_id,
                "custom:userType": user_type,
                "custom:role": "Tech_Lead",
                "email": "caller@example.com",
                "custom:departmentId": "dept-1",
                "custom:positionId": "pos-1",
            }
        },
        "arguments": arguments or {},
    }


# ---------------------------------------------------------------------------
# CreateDepartment auto-approve — Requirements 6.2, 6.5
# ---------------------------------------------------------------------------


class TestCreateDepartmentAutoApprove:
    @pytest.fixture(autouse=True)
    def _setup(self):
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        mock_table.put_item.return_value = {}

        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        with patch("boto3.resource", return_value=mock_dynamodb):
            # Clear cached module to pick up fresh mock
            for key in list(sys.modules.keys()):
                if "CreateDepartment" in key:
                    del sys.modules[key]
            from departments.CreateDepartment import handler as mod

            mod.dynamodb = mock_dynamodb
            self.mod = mod
            self.table = mock_table
            yield

    def test_superadmin_creates_department_with_approved_status(self):
        event = _make_event(
            "createDepartment",
            user_type="superadmin",
            arguments={"input": {"departmentName": "Engineering"}},
        )
        result = self.mod.create_department(event)
        assert result["approval_status"] == "Approved"

    def test_admin_creates_department_with_pending_status(self):
        event = _make_event(
            "createDepartment",
            user_type="admin",
            arguments={"input": {"departmentName": "Marketing"}},
        )
        result = self.mod.create_department(event)
        assert result["approval_status"] == "Pending_Approval"


# ---------------------------------------------------------------------------
# CreatePosition auto-approve — Requirements 6.3, 6.5
# ---------------------------------------------------------------------------


class TestCreatePositionAutoApprove:
    @pytest.fixture(autouse=True)
    def _setup(self):
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        mock_table.put_item.return_value = {}

        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        with patch("boto3.resource", return_value=mock_dynamodb):
            for key in list(sys.modules.keys()):
                if "CreatePosition" in key:
                    del sys.modules[key]
            from positions.CreatePosition import handler as mod

            mod.dynamodb = mock_dynamodb
            self.mod = mod
            self.table = mock_table
            yield

    def test_superadmin_creates_position_with_approved_status(self):
        event = _make_event(
            "createPosition",
            user_type="superadmin",
            arguments={"input": {"positionName": "Lead Engineer", "description": "desc"}},
        )
        result = self.mod.create_position(event)
        assert result["approval_status"] == "Approved"

    def test_admin_creates_position_with_pending_status(self):
        event = _make_event(
            "createPosition",
            user_type="admin",
            arguments={"input": {"positionName": "Junior Dev", "description": "desc"}},
        )
        result = self.mod.create_position(event)
        assert result["approval_status"] == "Pending_Approval"


# ---------------------------------------------------------------------------
# CreateProject auto-approve — Requirements 6.4, 6.5
# ---------------------------------------------------------------------------


_DEFAULT_PROJECT_INPUT = {
    "projectCode": "PRJ-001",
    "projectName": "Test Project",
    "startDate": "2025-01-01",
    "plannedHours": 100.0,
    "projectManagerId": "pm-001",
}


class TestCreateProjectAutoApprove:
    @pytest.fixture(autouse=True)
    def _setup(self):
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        mock_table.put_item.return_value = {}

        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        with patch("boto3.resource", return_value=mock_dynamodb):
            for key in list(sys.modules.keys()):
                if "CreateProject" in key:
                    del sys.modules[key]
            from projects.CreateProject import handler as mod

            mod.dynamodb = mock_dynamodb
            self.mod = mod
            self.table = mock_table
            yield

    def test_superadmin_creates_project_with_approved_status(self):
        event = _make_event(
            "createProject",
            user_type="superadmin",
            arguments={"input": {**_DEFAULT_PROJECT_INPUT}},
        )
        result = self.mod.create_project(event)
        assert result["approval_status"] == "Approved"

    def test_admin_creates_project_with_pending_status(self):
        event = _make_event(
            "createProject",
            user_type="admin",
            arguments={"input": {**_DEFAULT_PROJECT_INPUT}},
        )
        result = self.mod.create_project(event)
        assert result["approval_status"] == "Pending_Approval"
