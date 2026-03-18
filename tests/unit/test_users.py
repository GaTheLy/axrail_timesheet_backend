"""Unit tests for lambdas/users/handler.py — User Management resolvers.

Validates: Requirements 2.7, 2.8, 2.9, 2.10
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Ensure the handler can resolve its shared imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lambdas"))

# Set required env vars before importing the handler
os.environ.setdefault("USERS_TABLE", "UsersTable")
os.environ.setdefault("USER_POOL_ID", "us-east-1_TestPool")


def _make_event(
    field_name="createUser",
    user_type="superadmin",
    role="Tech_Lead",
    user_id="caller-001",
    arguments=None,
):
    """Build a minimal AppSync event with Cognito claims and arguments."""
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


def _create_user_input(
    email="new@example.com",
    full_name="New User",
    user_type_val="user",
    role_val="Employee",
):
    """Build a standard CreateUserInput dict."""
    return {
        "input": {
            "email": email,
            "fullName": full_name,
            "userType": user_type_val,
            "role": role_val,
            "positionId": "pos-1",
            "departmentId": "dept-1",
        }
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _mock_boto(monkeypatch):
    """Patch boto3.resource and boto3.client used at module level in handler."""
    mock_table = MagicMock()
    mock_table.query.return_value = {"Items": []}
    mock_table.put_item.return_value = {}

    mock_dynamodb = MagicMock()
    mock_dynamodb.Table.return_value = mock_table

    mock_cognito = MagicMock()

    with patch("boto3.resource", return_value=mock_dynamodb), \
         patch("boto3.client", return_value=mock_cognito):
        # Force re-import so module-level globals pick up the mocks
        if "lambdas.users.handler" in sys.modules:
            del sys.modules["lambdas.users.handler"]
        from lambdas.users import handler as mod

        mod.dynamodb = mock_dynamodb
        mod.cognito = mock_cognito

        yield {
            "table": mock_table,
            "dynamodb": mock_dynamodb,
            "cognito": mock_cognito,
            "handler_mod": mod,
        }


# ---------------------------------------------------------------------------
# Authorization — Requirement 2.7
# ---------------------------------------------------------------------------


class TestAuthorizeMutation:
    """Superadmin can create admin+user; Admin can only create user."""

    def test_superadmin_creates_admin(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        event = _make_event(
            user_type="superadmin",
            arguments=_create_user_input(user_type_val="admin", role_val="Tech_Lead"),
        )
        result = mod.create_user(event)
        assert result["userType"] == "admin"

    def test_superadmin_creates_user(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        event = _make_event(
            user_type="superadmin",
            arguments=_create_user_input(user_type_val="user", role_val="Employee"),
        )
        result = mod.create_user(event)
        assert result["userType"] == "user"

    def test_admin_creates_user(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        event = _make_event(
            user_type="admin",
            arguments=_create_user_input(user_type_val="user", role_val="Employee"),
        )
        result = mod.create_user(event)
        assert result["userType"] == "user"

    def test_admin_forbidden_create_admin(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        event = _make_event(
            user_type="admin",
            arguments=_create_user_input(user_type_val="admin", role_val="Tech_Lead"),
        )
        with pytest.raises(Exception, match="Admin can only manage user accounts"):
            mod.create_user(event)

    def test_admin_forbidden_create_superadmin(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        event = _make_event(
            user_type="admin",
            arguments=_create_user_input(user_type_val="superadmin", role_val="Tech_Lead"),
        )
        with pytest.raises(Exception, match="Admin can only manage user accounts"):
            mod.create_user(event)

    def test_user_forbidden_create_any(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        event = _make_event(
            user_type="user",
            arguments=_create_user_input(),
        )
        with pytest.raises(Exception, match="not authorized"):
            mod.handler(event, None)


# ---------------------------------------------------------------------------
# Email uniqueness — Requirement 2.8
# ---------------------------------------------------------------------------


class TestEmailUniqueness:
    """Email must be unique across all user records."""

    def test_duplicate_email_rejected(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        table = _mock_boto["table"]
        # Simulate existing user with same email
        table.query.return_value = {
            "Items": [{"userId": "existing-user", "email": "dup@example.com"}]
        }
        event = _make_event(
            user_type="superadmin",
            arguments=_create_user_input(email="dup@example.com"),
        )
        with pytest.raises(ValueError, match="already in use"):
            mod.create_user(event)

    def test_unique_email_accepted(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        table = _mock_boto["table"]
        table.query.return_value = {"Items": []}
        event = _make_event(
            user_type="superadmin",
            arguments=_create_user_input(email="unique@example.com"),
        )
        result = mod.create_user(event)
        assert result["email"] == "unique@example.com"


# ---------------------------------------------------------------------------
# Role validation — Requirement 2.9
# ---------------------------------------------------------------------------


class TestRoleValidation:
    """Role must be one of Project_Manager, Tech_Lead, or Employee."""

    @pytest.mark.parametrize("valid_role", ["Project_Manager", "Tech_Lead", "Employee"])
    def test_valid_roles_accepted(self, _mock_boto, valid_role):
        mod = _mock_boto["handler_mod"]
        event = _make_event(
            user_type="superadmin",
            arguments=_create_user_input(role_val=valid_role),
        )
        result = mod.create_user(event)
        assert result["role"] == valid_role

    def test_invalid_role_rejected(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        event = _make_event(
            user_type="superadmin",
            arguments=_create_user_input(role_val="InvalidRole"),
        )
        with pytest.raises(ValueError, match="Invalid role"):
            mod.create_user(event)


# ---------------------------------------------------------------------------
# UserType validation — Requirement 2.10
# ---------------------------------------------------------------------------


class TestUserTypeValidation:
    """userType must be one of superadmin, admin, or user."""

    @pytest.mark.parametrize("valid_type", ["admin", "user"])
    def test_valid_user_types_accepted_by_superadmin(self, _mock_boto, valid_type):
        mod = _mock_boto["handler_mod"]
        event = _make_event(
            user_type="superadmin",
            arguments=_create_user_input(user_type_val=valid_type),
        )
        result = mod.create_user(event)
        assert result["userType"] == valid_type

    def test_invalid_user_type_rejected(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        event = _make_event(
            user_type="superadmin",
            arguments=_create_user_input(user_type_val="manager"),
        )
        with pytest.raises(ValueError, match="Invalid userType"):
            mod.create_user(event)
