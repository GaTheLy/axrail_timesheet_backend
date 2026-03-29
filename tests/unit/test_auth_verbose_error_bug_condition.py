"""Bug condition exploration tests for verbose authorization error messages.

These property-based tests encode the EXPECTED behavior: authorization failures
should return a generic "Access denied" message without leaking the caller's
identity or the list of allowed types/roles.

**EXPECTED TO FAIL on unfixed code** — failure confirms the bug exists.
The verbose f-string messages in require_user_type(), require_role(), and
list_all_submissions() currently leak internal role hierarchy information.

Validates: Requirements 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4, 2.5
"""

import os
import sys

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from unittest.mock import patch, MagicMock

# Ensure both project root and lambdas/ are on sys.path so that:
# - `lambdas.shared.auth` resolves (project root)
# - `from shared.auth import ...` inside lambdas/shared/__init__.py resolves (lambdas/)
_project_root = os.path.join(os.path.dirname(__file__), "..", "..")
_lambdas_dir = os.path.join(_project_root, "lambdas")
for _p in (_project_root, _lambdas_dir):
    _p = os.path.abspath(_p)
    if _p not in sys.path:
        sys.path.insert(0, _p)

from lambdas.shared.auth import ForbiddenError, require_user_type, require_role

# The ListAllSubmissions handler uses boto3.resource("dynamodb") at module level,
# and imports from shared.project_assignments which also uses boto3.
# We mock boto3.resource before importing so the module loads without AWS credentials.
with patch("boto3.resource"):
    from lambdas.submissions.ListAllSubmissions.handler import (
        list_all_submissions as _list_all_submissions_orig,
    )

# Ensure lambdas package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from lambdas.shared.auth import ForbiddenError, require_user_type, require_role

# The ListAllSubmissions handler uses boto3.resource("dynamodb") at module level.
# We mock boto3 before importing so the module loads without AWS credentials.
with patch("boto3.resource"):
    from lambdas.submissions.ListAllSubmissions.handler import (
        list_all_submissions as _list_all_submissions_orig,
    )


def _list_all_submissions(event):
    """Wrapper that patches the module-level dynamodb resource before calling."""
    with patch(
        "lambdas.submissions.ListAllSubmissions.handler.dynamodb"
    ):
        return _list_all_submissions_orig(event)


# The handler imports ForbiddenError via `from shared.auth import ForbiddenError`
# (using its own sys.path), which creates a different class identity than
# `lambdas.shared.auth.ForbiddenError`. We grab the handler's reference so
# pytest.raises can match it.
_HandlerForbiddenError = (
    _list_all_submissions_orig.__globals__
    .get("ForbiddenError", ForbiddenError)
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SUPERADMIN_ONLY = ["superadmin"]
ADMIN_TYPES = ["superadmin", "admin"]
PM_TL_ROLES = ["Tech_Lead", "Project_Manager"]

# All values that would be authorized in listAllSubmissions
LIST_ALL_AUTHORIZED_USER_TYPES = {"superadmin", "admin"}
LIST_ALL_AUTHORIZED_ROLES = {"Tech_Lead", "Project_Manager"}


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


def _assert_generic_error(err, caller_user_type=None, caller_role=None,
                          forbidden_strings=None):
    """Assert the error message is generic and leaks no internal info.

    Short substrings (len < 3) that happen to appear in "Access denied" are
    not considered leaks — they are coincidental matches, not information
    disclosure.  The bug we are detecting produces messages like
    "User type 'admin' is not authorized. Allowed types: ['superadmin']"
    where the leaked values are always meaningful identifiers.
    """
    msg = err.message
    GENERIC_MSG = "Access denied"

    # Must be exactly "Access denied"
    assert msg == GENERIC_MSG, (
        f"Expected {GENERIC_MSG!r}, got: {msg!r}"
    )

    # Must not contain the caller's userType (skip if trivially in generic msg)
    if caller_user_type and caller_user_type not in GENERIC_MSG:
        assert caller_user_type not in msg, (
            f"Message leaks caller userType {caller_user_type!r}: {msg!r}"
        )

    # Must not contain the caller's role (skip if trivially in generic msg)
    if caller_role and caller_role not in GENERIC_MSG:
        assert caller_role not in msg, (
            f"Message leaks caller role {caller_role!r}: {msg!r}"
        )

    # Must not contain "allowed" (case-insensitive)
    assert "allowed" not in msg.lower(), (
        f"Message contains 'allowed': {msg!r}"
    )

    # Must not contain any explicitly forbidden strings
    if forbidden_strings:
        for s in forbidden_strings:
            if s not in GENERIC_MSG:
                assert s not in msg, (
                    f"Message leaks forbidden string {s!r}: {msg!r}"
                )


# ---------------------------------------------------------------------------
# Property 1a: require_user_type() — generic error on unauthorized userType
# ---------------------------------------------------------------------------

class TestRequireUserTypeVerboseError:
    """Validates: Requirements 1.2, 2.2"""

    @given(user_type=st.text(min_size=1))
    @settings(max_examples=50)
    def test_unauthorized_user_type_gets_generic_error(self, user_type):
        """For any userType NOT in allowed_types, the error message must be
        exactly 'Access denied' and must not leak the caller's type or the
        allowed list."""
        allowed_types = SUPERADMIN_ONLY
        assume(user_type not in allowed_types)

        event = _make_event(user_type=user_type, role="Employee")

        with pytest.raises(ForbiddenError) as exc_info:
            require_user_type(event, allowed_types)

        _assert_generic_error(
            exc_info.value,
            caller_user_type=user_type,
            forbidden_strings=allowed_types,
        )

    @given(user_type=st.text(min_size=1))
    @settings(max_examples=50)
    def test_unauthorized_user_type_admin_list_gets_generic_error(self, user_type):
        """Same check against the broader admin types list."""
        allowed_types = ADMIN_TYPES
        assume(user_type not in allowed_types)

        event = _make_event(user_type=user_type, role="Employee")

        with pytest.raises(ForbiddenError) as exc_info:
            require_user_type(event, allowed_types)

        _assert_generic_error(
            exc_info.value,
            caller_user_type=user_type,
            forbidden_strings=allowed_types,
        )


# ---------------------------------------------------------------------------
# Property 1b: require_role() — generic error on unauthorized role
# ---------------------------------------------------------------------------

class TestRequireRoleVerboseError:
    """Validates: Requirements 1.3, 2.3"""

    @given(role=st.text(min_size=1))
    @settings(max_examples=50)
    def test_unauthorized_role_gets_generic_error(self, role):
        """For any role NOT in allowed_roles, the error message must be
        exactly 'Access denied' and must not leak the caller's role or the
        allowed list."""
        allowed_roles = PM_TL_ROLES
        assume(role not in allowed_roles)

        event = _make_event(user_type="user", role=role)

        with pytest.raises(ForbiddenError) as exc_info:
            require_role(event, allowed_roles)

        _assert_generic_error(
            exc_info.value,
            caller_role=role,
            forbidden_strings=allowed_roles,
        )


# ---------------------------------------------------------------------------
# Property 1c: list_all_submissions() inline auth — generic error
# ---------------------------------------------------------------------------

class TestListAllSubmissionsVerboseError:
    """Validates: Requirements 1.4, 2.4"""

    @given(
        user_type=st.text(min_size=1),
        role=st.text(min_size=1),
    )
    @settings(max_examples=50)
    def test_unauthorized_caller_gets_generic_error(self, user_type, role):
        """For any caller who is neither admin/superadmin nor a user with
        Tech_Lead/Project_Manager role, the error must be exactly
        'Access denied' and must not leak any authorization details."""
        # Exclude all authorized combinations
        assume(user_type not in LIST_ALL_AUTHORIZED_USER_TYPES)
        assume(role not in LIST_ALL_AUTHORIZED_ROLES)

        event = _make_event(user_type=user_type, role=role)

        with pytest.raises((ForbiddenError, _HandlerForbiddenError)) as exc_info:
            _list_all_submissions(event)

        _assert_generic_error(
            exc_info.value,
            caller_user_type=user_type,
            caller_role=role,
            forbidden_strings=[
                "admin", "superadmin",
                "Tech_Lead", "Project_Manager",
            ],
        )
