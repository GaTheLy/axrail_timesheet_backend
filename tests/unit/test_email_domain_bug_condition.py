"""Bug condition exploration test for email domain restriction.

Property 1: Bug Condition — Non-axrail Email Accepted

Tests that create_user() with a non-@axrail.com email raises a ValueError.
This test encodes the EXPECTED behavior from the design document.

On UNFIXED code, this test MUST FAIL — confirming the bug exists
(the system currently accepts any email domain).

**Validates: Requirements 1.1, 1.2, 2.1**
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
# Strategies — generate emails that do NOT end with @axrail.com
# ---------------------------------------------------------------------------

non_axrail_domains = st.sampled_from([
    "gmail.com", "yahoo.com", "competitor.com", "outlook.com",
    "hotmail.com", "company.org", "test.net", "example.com",
])

email_local_part = st.from_regex(r"[a-z][a-z0-9_.]{1,20}", fullmatch=True)

non_axrail_email = st.builds(
    lambda local, domain: f"{local}@{domain}",
    email_local_part,
    non_axrail_domains,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event(email, caller_type="superadmin"):
    """Build a minimal AppSync event for createUser with the given email."""
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
                "userType": "user",
                "role": "Employee",
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
    mock_table.query.return_value = {"Items": []}  # no duplicate emails
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
# Property 1: Bug Condition — Non-axrail Email Should Be Rejected
# ---------------------------------------------------------------------------

class TestEmailDomainBugCondition:
    """Bug condition: create_user() with a non-@axrail.com email should raise
    ValueError. On unfixed code this test FAILS, confirming the bug exists."""

    @given(email=non_axrail_email)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_non_axrail_email_rejected(self, email, _mock_boto):
        """For any email not ending with @axrail.com, create_user() must raise
        ValueError with a message about domain restriction.

        **Validates: Requirements 1.1, 1.2, 2.1**
        """
        # Confirm the email is indeed non-axrail (bug condition)
        assert not email.lower().endswith("@axrail.com")

        mod = _mock_boto["handler_mod"]
        event = _make_event(email)

        with pytest.raises(ValueError, match="Only @axrail.com email addresses are allowed"):
            mod.create_user(event)
