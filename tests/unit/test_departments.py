"""Unit tests for lambdas/departments/handler.py — Department Management resolvers.

Validates: Requirements 3.3, 3.5, 3.6
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lambdas"))

os.environ.setdefault("DEPARTMENTS_TABLE", "DepartmentsTable")
os.environ.setdefault("USERS_TABLE", "UsersTable")


def _make_event(
    field_name="createDepartment",
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _mock_boto(monkeypatch):
    """Patch boto3.resource so DynamoDB calls hit mocks."""
    mock_dept_table = MagicMock()
    mock_dept_table.query.return_value = {"Items": []}
    mock_dept_table.put_item.return_value = {}
    mock_dept_table.get_item.return_value = {
        "Item": {
            "departmentId": "dept-100",
            "departmentName": "Engineering",
            "createdAt": "2025-01-01T00:00:00+00:00",
            "createdBy": "caller-001",
        }
    }
    mock_dept_table.delete_item.return_value = {}
    mock_dept_table.update_item.return_value = {
        "Attributes": {
            "departmentId": "dept-100",
            "departmentName": "Engineering",
            "updatedAt": "2025-06-01T00:00:00+00:00",
            "updatedBy": "caller-001",
        }
    }

    mock_users_table = MagicMock()
    mock_users_table.query.return_value = {"Items": []}

    def table_router(name):
        if name == os.environ.get("USERS_TABLE"):
            return mock_users_table
        return mock_dept_table

    mock_dynamodb = MagicMock()
    mock_dynamodb.Table.side_effect = table_router

    with patch("boto3.resource", return_value=mock_dynamodb):
        if "lambdas.departments.handler" in sys.modules:
            del sys.modules["lambdas.departments.handler"]
        from lambdas.departments import handler as mod

        mod.dynamodb = mock_dynamodb

        yield {
            "dept_table": mock_dept_table,
            "users_table": mock_users_table,
            "handler_mod": mod,
        }


# ---------------------------------------------------------------------------
# Unique department name enforcement — Requirement 3.3
# ---------------------------------------------------------------------------


class TestDepartmentNameUniqueness:
    def test_duplicate_name_rejected_on_create(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        table = _mock_boto["dept_table"]
        table.query.return_value = {
            "Items": [{"departmentId": "dept-existing", "departmentName": "Engineering"}]
        }
        event = _make_event(arguments={"input": {"departmentName": "Engineering"}})
        with pytest.raises(ValueError, match="already in use"):
            mod.create_department(event)

    def test_unique_name_accepted_on_create(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        table = _mock_boto["dept_table"]
        table.query.return_value = {"Items": []}
        event = _make_event(arguments={"input": {"departmentName": "Marketing"}})
        result = mod.create_department(event)
        assert result["departmentName"] == "Marketing"

    def test_duplicate_name_rejected_on_update(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        table = _mock_boto["dept_table"]
        # First call: get_item returns existing dept; second query: name check finds conflict
        table.query.return_value = {
            "Items": [{"departmentId": "dept-other", "departmentName": "Finance"}]
        }
        event = _make_event(
            field_name="updateDepartment",
            arguments={
                "departmentId": "dept-100",
                "input": {"departmentName": "Finance"},
            },
        )
        with pytest.raises(ValueError, match="already in use"):
            mod.update_department(event)

    def test_same_name_allowed_on_update_for_same_dept(self, _mock_boto):
        """Updating a department without changing its name should succeed."""
        mod = _mock_boto["handler_mod"]
        table = _mock_boto["dept_table"]
        # GSI returns the same department — should be excluded from uniqueness check
        table.query.return_value = {
            "Items": [{"departmentId": "dept-100", "departmentName": "Engineering"}]
        }
        event = _make_event(
            field_name="updateDepartment",
            arguments={
                "departmentId": "dept-100",
                "input": {"departmentName": "Engineering"},
            },
        )
        # Should not raise — name belongs to the same department
        result = mod.update_department(event)
        assert result is not None


# ---------------------------------------------------------------------------
# Deletion rejection when associations exist — Requirement 3.5
# ---------------------------------------------------------------------------


class TestDepartmentDeletionAssociations:
    def test_delete_rejected_when_users_associated(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        users_table = _mock_boto["users_table"]
        users_table.query.return_value = {
            "Items": [{"userId": "user-1", "departmentId": "dept-100"}]
        }
        event = _make_event(
            field_name="deleteDepartment",
            arguments={"departmentId": "dept-100"},
        )
        with pytest.raises(ValueError, match="active user associations exist"):
            mod.delete_department(event)

    def test_delete_succeeds_when_no_users_associated(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        users_table = _mock_boto["users_table"]
        users_table.query.return_value = {"Items": []}
        event = _make_event(
            field_name="deleteDepartment",
            arguments={"departmentId": "dept-100"},
        )
        result = mod.delete_department(event)
        assert result is True

    def test_delete_nonexistent_department_raises(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        table = _mock_boto["dept_table"]
        table.get_item.return_value = {}
        event = _make_event(
            field_name="deleteDepartment",
            arguments={"departmentId": "dept-missing"},
        )
        with pytest.raises(ValueError, match="not found"):
            mod.delete_department(event)


# ---------------------------------------------------------------------------
# Superadmin-only authorization — Requirement 3.6
# ---------------------------------------------------------------------------


class TestDepartmentAuthorization:
    def test_admin_forbidden_create(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        event = _make_event(
            user_type="admin",
            arguments={"input": {"departmentName": "HR"}},
        )
        with pytest.raises(Exception, match="not authorized"):
            mod.handler(event, None)

    def test_user_forbidden_create(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        event = _make_event(
            user_type="user",
            arguments={"input": {"departmentName": "HR"}},
        )
        with pytest.raises(Exception, match="not authorized"):
            mod.handler(event, None)

    def test_admin_forbidden_update(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        event = _make_event(
            field_name="updateDepartment",
            user_type="admin",
            arguments={"departmentId": "dept-100", "input": {"departmentName": "HR"}},
        )
        with pytest.raises(Exception, match="not authorized"):
            mod.handler(event, None)

    def test_admin_forbidden_delete(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        event = _make_event(
            field_name="deleteDepartment",
            user_type="admin",
            arguments={"departmentId": "dept-100"},
        )
        with pytest.raises(Exception, match="not authorized"):
            mod.handler(event, None)

    def test_superadmin_allowed_create(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        event = _make_event(
            user_type="superadmin",
            arguments={"input": {"departmentName": "NewDept"}},
        )
        result = mod.handler(event, None)
        assert result["departmentName"] == "NewDept"


