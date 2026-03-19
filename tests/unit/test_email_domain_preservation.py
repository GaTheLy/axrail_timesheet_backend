"""Preservation property tests for email domain restriction.

Property 2: Preservation — Valid axrail.com Email Creation Unchanged

Tests that existing behavior for valid @axrail.com emails is preserved:
- Uniqueness check rejects duplicate emails
- Valid enum values are accepted and user is created
- Admin creating superadmin/admin accounts raises permissions error

These tests MUST PASS on the current UNFIXED code.

**Validates: Requirements 3.1, 3.2, 3.3**
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

# Ensure the handler can resolve its shared imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lambdas"))

# Set required env vars before importing the handler
os.environ.setdefault("USERS_TABLE", "UsersTable")
os.environ.setdefault("USER_POOL_ID", "us-east-1_TestPool")


# ---------------------------------------------------------------------------
# Strategies — generate valid @axrail.com emails
# ---------------------------------------------------------------------------

email_local_part = st.from_regex(r"[a-z][a-z0-9_.]{1,20}", fullmatch=True)

axrail_email = st.builds(
    lambda local: f"{local}@axrail.com",
    email_local_part,
)

valid_roles = st.sampled_from(["Project_Manager", "Tech_Lead", "Employee"])
valid_user_types_for_user = st.just("user")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event(email, caller_type="superadmin", target_user_type="user", role="Employee"):
    """Build a minimal AppSync event for createUser."""
    return {
        "info": {"fieldName": "createUser"},
        "identity": {
            "claims": {
                "sub": "caller-001",
                "custom:userType": caller_type,
                "custom:role": "Tech_Lead",
                "email": "caller@axrail.com",
                "custom:departmentId": "dept-1",
                "custom:positionId": "pos-1",
            }
        },
        "arguments": {
            "input": {
                "email": email,
                "fullName": "Test User",
                "userType": target_user_type,
                "role": role,
                "positionId": "pos-1",
                "departmentId": "dept-1",
            }
        },
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _mock_boto(monkeypatch):
    """Patch boto3.resource and boto3.client used at module level in handler."""
    mock_table = MagicMock()
    mock_table.query.return_value = {"Items": []}  # no duplicate emails by default
    mock_table.put_item.return_value = {}

    mock_dynamodb = MagicMock()
    mock_dynamodb.Table.return_value = mock_table

    mock_cognito = MagicMock()

    with patch("boto3.resource", return_value=mock_dynamodb), \
         patch("boto3.client", return_value=mock_cognito):
        # Force re-import so module-level globals pick up the mocks
        mod_key = "lambdas.users.CreateUser.handler"
        if mod_key in sys.modules:
            del sys.modules[mod_key]
        from lambdas.users.CreateUser import handler as mod

        mod.dynamodb = mock_dynamodb
        mod.cognito = mock_cognito

        yield {
            "table": mock_table,
            "dynamodb": mock_dynamodb,
            "cognito": mock_cognito,
            "handler_mod": mod,
        }


# ---------------------------------------------------------------------------
# Property 2: Preservation — Valid @axrail.com Email Creation Unchanged
# ---------------------------------------------------------------------------

class TestEmailDomainPreservation:
    """Preservation: existing behavior for valid @axrail.com emails is unchanged."""

    @given(email=axrail_email, role=valid_roles)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_valid_axrail_email_creation_succeeds(self, email, role, _mock_boto):
        """For any valid @axrail.com email with valid enums, create_user()
        proceeds through uniqueness check and creates the user.

        **Validates: Requirements 3.2**
        """
        assert email.lower().endswith("@axrail.com")

        mod = _mock_boto["handler_mod"]
        table = _mock_boto["table"]
        cognito_mock = _mock_boto["cognito"]

        # Reset mocks for each hypothesis example
        table.query.return_value = {"Items": []}
        table.put_item.reset_mock()
        cognito_mock.admin_create_user.reset_mock()
        cognito_mock.admin_add_user_to_group.reset_mock()

        event = _make_event(email, caller_type="superadmin", target_user_type="user", role=role)
        result = mod.create_user(event)

        # User was created — DynamoDB put_item and Cognito calls were made
        assert result["email"] == email
        assert result["role"] == role
        assert result["userType"] == "user"
        table.put_item.assert_called_once()
        cognito_mock.admin_create_user.assert_called_once()
        cognito_mock.admin_add_user_to_group.assert_called_once()

    @given(email=axrail_email)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_duplicate_axrail_email_rejected(self, email, _mock_boto):
        """For any valid @axrail.com email that already exists, create_user()
        raises ValueError with 'already in use' message.

        **Validates: Requirements 3.1**
        """
        assert email.lower().endswith("@axrail.com")

        mod = _mock_boto["handler_mod"]
        table = _mock_boto["table"]

        # Simulate existing user with same email
        table.query.return_value = {"Items": [{"email": email, "userId": "existing-user"}]}

        event = _make_event(email, caller_type="superadmin")

        with pytest.raises(ValueError, match="already in use"):
            mod.create_user(event)

    @given(email=axrail_email, target_type=st.sampled_from(["superadmin", "admin"]))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_admin_creating_privileged_account_rejected(self, email, target_type, _mock_boto):
        """For any valid @axrail.com email, an admin creating a superadmin or
        admin account raises ForbiddenError (permissions error).

        **Validates: Requirements 3.3**
        """
        assert email.lower().endswith("@axrail.com")

        mod = _mock_boto["handler_mod"]

        event = _make_event(email, caller_type="admin", target_user_type=target_type)

        # Admin cannot create superadmin or admin accounts — raises Exception
        # (handler wraps ForbiddenError into Exception in the handler() entry point,
        #  but create_user() raises ForbiddenError directly)
        from shared.auth import ForbiddenError
        with pytest.raises(ForbiddenError):
            mod.create_user(event)
