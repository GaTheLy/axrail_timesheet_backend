"""Preservation property tests for authorization behavior.

These tests capture the BASELINE behavior of the authorization functions
on UNFIXED code. They verify that:
- Authorized callers get the correct identity dict returned
- Unauthorized callers are denied (ForbiddenError raised)
- Authorization DECISIONS are preserved regardless of error message content

All tests must PASS on unfixed code — they confirm behavior to preserve.

Validates: Requirements 3.1, 3.2, 3.3, 3.4
"""

import os
import sys

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from unittest.mock import patch, MagicMock

# Ensure project root and lambdas/ are on sys.path
_project_root = os.path.join(os.path.dirname(__file__), "..", "..")
_lambdas_dir = os.path.join(_project_root, "lambdas")
for _p in (_project_root, _lambdas_dir):
    _p = os.path.abspath(_p)
    if _p not in sys.path:
        sys.path.insert(0, _p)

from lambdas.shared.auth import ForbiddenError, require_user_type, require_role

# Mock boto3.resource before importing the handler (it uses it at module level)
with patch("boto3.resource"):
    from lambdas.submissions.ListAllSubmissions.handler import (
        list_all_submissions,
    )

# The handler imports ForbiddenError via its own sys.path manipulation,
# so it may be a different class than lambdas.shared.auth.ForbiddenError.
_HandlerForbiddenError = (
    list_all_submissions.__globals__.get("ForbiddenError", ForbiddenError)
)

IDENTITY_KEYS = {"userId", "userType", "role", "email", "departmentId", "positionId"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event(user_type, role, user_id="user-123", email="user@example.com"):
    return {
        "identity": {
            "claims": {
                "sub": user_id,
                "custom:userType": user_type,
                "custom:role": role,
                "email": email,
                "custom:departmentId": "dept-1",
                "custom:positionId": "pos-1",
            }
        }
    }


# ---------------------------------------------------------------------------
# Observation tests — verify current behavior on UNFIXED code
# ---------------------------------------------------------------------------

class TestObservationRequireUserType:
    """Observe that require_user_type returns identity for authorized callers
    and raises ForbiddenError for unauthorized callers.

    Validates: Requirements 3.1, 3.2
    """

    def test_admin_authorized_for_admin_types(self):
        """require_user_type with admin in allowed list returns identity dict."""
        event = _make_event(user_type="admin", role="Employee")
        identity = require_user_type(event, ["superadmin", "admin"])

        assert set(identity.keys()) == IDENTITY_KEYS
        assert identity["userId"] == "user-123"
        assert identity["userType"] == "admin"
        assert identity["role"] == "Employee"
        assert identity["email"] == "user@example.com"
        assert identity["departmentId"] == "dept-1"
        assert identity["positionId"] == "pos-1"

    def test_admin_denied_for_superadmin_only(self):
        """require_user_type with admin NOT in allowed list raises ForbiddenError."""
        event = _make_event(user_type="admin", role="Employee")
        with pytest.raises(ForbiddenError):
            require_user_type(event, ["superadmin"])


class TestObservationRequireRole:
    """Observe that require_role returns identity for authorized callers
    and raises ForbiddenError for unauthorized callers.

    Validates: Requirements 3.3, 3.4
    """

    def test_tech_lead_authorized(self):
        """require_role with Tech_Lead in allowed list returns identity dict."""
        event = _make_event(user_type="user", role="Tech_Lead")
        identity = require_role(event, ["Project_Manager", "Tech_Lead"])

        assert set(identity.keys()) == IDENTITY_KEYS
        assert identity["role"] == "Tech_Lead"
        assert identity["userType"] == "user"

    def test_employee_denied_for_pm_only(self):
        """require_role with Employee NOT in allowed list raises ForbiddenError."""
        event = _make_event(user_type="user", role="Employee")
        with pytest.raises(ForbiddenError):
            require_role(event, ["Project_Manager"])


# ---------------------------------------------------------------------------
# Property-based tests — authorized callers
# ---------------------------------------------------------------------------

class TestPropertyAuthorizedUserType:
    """For all authorized userType values, require_user_type returns identity.

    Validates: Requirements 3.1, 3.2
    """

    @given(user_type=st.sampled_from(["superadmin", "admin"]))
    @settings(max_examples=20)
    def test_authorized_user_type_returns_identity(self, user_type):
        """For any userType in allowed_types, no exception is raised and
        the returned identity dict has the correct userType."""
        allowed_types = ["superadmin", "admin"]
        event = _make_event(user_type=user_type, role="Employee")

        identity = require_user_type(event, allowed_types)

        assert isinstance(identity, dict)
        assert set(identity.keys()) == IDENTITY_KEYS
        assert identity["userType"] == user_type

    @given(user_type=st.sampled_from(["superadmin"]))
    @settings(max_examples=10)
    def test_superadmin_only_endpoint_allows_superadmin(self, user_type):
        """Superadmin-only endpoints allow superadmin callers."""
        event = _make_event(user_type=user_type, role="Employee")

        identity = require_user_type(event, ["superadmin"])

        assert identity["userType"] == "superadmin"


class TestPropertyAuthorizedRole:
    """For all authorized role values, require_role returns identity.

    Validates: Requirements 3.3
    """

    @given(role=st.sampled_from(["Tech_Lead", "Project_Manager"]))
    @settings(max_examples=20)
    def test_authorized_role_returns_identity(self, role):
        """For any role in allowed_roles, no exception is raised and
        the returned identity dict has the correct role."""
        allowed_roles = ["Project_Manager", "Tech_Lead"]
        event = _make_event(user_type="user", role=role)

        identity = require_role(event, allowed_roles)

        assert isinstance(identity, dict)
        assert set(identity.keys()) == IDENTITY_KEYS
        assert identity["role"] == role


# ---------------------------------------------------------------------------
# Property-based tests — unauthorized callers (decision preserved)
# ---------------------------------------------------------------------------

class TestPropertyUnauthorizedUserType:
    """For all unauthorized userType values, require_user_type raises ForbiddenError.
    We do NOT check the message — only that the denial decision is preserved.

    Validates: Requirements 3.4
    """

    @given(user_type=st.text(min_size=1))
    @settings(max_examples=50)
    def test_unauthorized_user_type_is_denied(self, user_type):
        """For any userType NOT in allowed_types, ForbiddenError is raised."""
        allowed_types = ["superadmin", "admin"]
        assume(user_type not in allowed_types)

        event = _make_event(user_type=user_type, role="Employee")

        with pytest.raises(ForbiddenError):
            require_user_type(event, allowed_types)

    @given(user_type=st.text(min_size=1))
    @settings(max_examples=50)
    def test_unauthorized_user_type_superadmin_only_is_denied(self, user_type):
        """For any userType NOT in superadmin-only list, ForbiddenError is raised."""
        allowed_types = ["superadmin"]
        assume(user_type not in allowed_types)

        event = _make_event(user_type=user_type, role="Employee")

        with pytest.raises(ForbiddenError):
            require_user_type(event, allowed_types)


class TestPropertyUnauthorizedRole:
    """For all unauthorized role values, require_role raises ForbiddenError.
    We do NOT check the message — only that the denial decision is preserved.

    Validates: Requirements 3.4
    """

    @given(role=st.text(min_size=1))
    @settings(max_examples=50)
    def test_unauthorized_role_is_denied(self, role):
        """For any role NOT in allowed_roles, ForbiddenError is raised."""
        allowed_roles = ["Project_Manager", "Tech_Lead"]
        assume(role not in allowed_roles)

        event = _make_event(user_type="user", role=role)

        with pytest.raises(ForbiddenError):
            require_role(event, allowed_roles)


# ---------------------------------------------------------------------------
# Property-based test — list_all_submissions authorized callers preserved
# ---------------------------------------------------------------------------

class TestPropertyListAllSubmissionsAuthorized:
    """For admin/superadmin and user+Tech_Lead/Project_Manager callers,
    list_all_submissions does NOT raise ForbiddenError.
    We mock DynamoDB to return empty results — the key assertion is that
    no authorization error is raised for authorized callers.

    Validates: Requirements 3.1, 3.2, 3.3
    """

    def _mock_dynamodb_table(self):
        """Create a mock DynamoDB table that returns empty scan/query results."""
        mock_table = MagicMock()
        mock_table.scan.return_value = {"Items": []}
        mock_table.query.return_value = {"Items": []}
        return mock_table

    @given(user_type=st.sampled_from(["superadmin", "admin"]))
    @settings(max_examples=10)
    def test_admin_superadmin_not_denied(self, user_type):
        """Admin and superadmin callers are NOT denied by list_all_submissions."""
        event = _make_event(user_type=user_type, role="Employee")

        mock_table = self._mock_dynamodb_table()
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        with patch(
            "lambdas.submissions.ListAllSubmissions.handler.dynamodb",
            mock_dynamodb,
        ):
            # Should NOT raise ForbiddenError
            result = list_all_submissions(event)
            assert isinstance(result, list)

    @given(role=st.sampled_from(["Tech_Lead", "Project_Manager"]))
    @settings(max_examples=10)
    def test_pm_tech_lead_not_denied(self, role):
        """User callers with Tech_Lead or Project_Manager role are NOT denied."""
        event = _make_event(user_type="user", role=role)

        mock_table = self._mock_dynamodb_table()
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        with patch(
            "lambdas.submissions.ListAllSubmissions.handler.dynamodb",
            mock_dynamodb,
        ):
            with patch(
                "lambdas.submissions.ListAllSubmissions.handler.get_supervised_employee_ids",
                return_value=[],
            ):
                # Should NOT raise ForbiddenError
                result = list_all_submissions(event)
                assert isinstance(result, list)
