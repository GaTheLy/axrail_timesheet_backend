"""Unit tests for lambdas/shared/auth.py utilities."""

import pytest

from lambdas.shared.auth import ForbiddenError, get_caller_identity, require_role, require_user_type


def _make_event(
    user_id="user-123",
    user_type="admin",
    role="Tech_Lead",
    email="user@example.com",
    department_id="dept-1",
    position_id="pos-1",
):
    """Build a minimal AppSync event with Cognito claims."""
    return {
        "identity": {
            "claims": {
                "sub": user_id,
                "custom:userType": user_type,
                "custom:role": role,
                "email": email,
                "custom:departmentId": department_id,
                "custom:positionId": position_id,
            }
        }
    }


# --- get_caller_identity ---


class TestGetCallerIdentity:
    def test_extracts_all_claims(self):
        event = _make_event()
        identity = get_caller_identity(event)

        assert identity["userId"] == "user-123"
        assert identity["userType"] == "admin"
        assert identity["role"] == "Tech_Lead"
        assert identity["email"] == "user@example.com"
        assert identity["departmentId"] == "dept-1"
        assert identity["positionId"] == "pos-1"

    def test_missing_claims_returns_empty_strings(self):
        event = {"identity": {"claims": {"sub": "u1"}}}
        identity = get_caller_identity(event)

        assert identity["userId"] == "u1"
        assert identity["userType"] == ""
        assert identity["role"] == ""
        assert identity["email"] == ""

    def test_raises_on_missing_identity_key(self):
        with pytest.raises(ValueError, match="missing identity claims"):
            get_caller_identity({})

    def test_raises_on_none_identity(self):
        with pytest.raises(ValueError, match="missing identity claims"):
            get_caller_identity({"identity": None})


# --- require_role ---


class TestRequireRole:
    def test_returns_identity_when_role_allowed(self):
        event = _make_event(role="Tech_Lead")
        identity = require_role(event, ["Tech_Lead", "Project_Manager"])

        assert identity["role"] == "Tech_Lead"

    def test_raises_forbidden_when_role_not_allowed(self):
        event = _make_event(role="Employee")
        with pytest.raises(ForbiddenError, match="Access denied"):
            require_role(event, ["Tech_Lead", "Project_Manager"])

    def test_single_allowed_role(self):
        event = _make_event(role="Project_Manager")
        identity = require_role(event, ["Project_Manager"])
        assert identity["role"] == "Project_Manager"

    def test_forbidden_message_is_generic(self):
        event = _make_event(role="Employee")
        with pytest.raises(ForbiddenError, match="Access denied") as exc_info:
            require_role(event, ["Tech_Lead"])
        assert "Employee" not in exc_info.value.message


# --- require_user_type ---


class TestRequireUserType:
    def test_returns_identity_when_type_allowed(self):
        event = _make_event(user_type="superadmin")
        identity = require_user_type(event, ["superadmin"])

        assert identity["userType"] == "superadmin"

    def test_raises_forbidden_when_type_not_allowed(self):
        event = _make_event(user_type="user")
        with pytest.raises(ForbiddenError, match="Access denied"):
            require_user_type(event, ["superadmin", "admin"])

    def test_multiple_allowed_types(self):
        event = _make_event(user_type="admin")
        identity = require_user_type(event, ["superadmin", "admin"])
        assert identity["userType"] == "admin"

    def test_forbidden_message_is_generic(self):
        event = _make_event(user_type="user")
        with pytest.raises(ForbiddenError, match="Access denied") as exc_info:
            require_user_type(event, ["superadmin"])
        assert "user" not in exc_info.value.message
