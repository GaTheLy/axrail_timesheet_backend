"""Unit tests for generate_next_user_code in lambdas/users/CreateUser/handler.py.

Validates: Requirements 3.2
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


@pytest.fixture()
def create_user_mod():
    """Import the CreateUser handler module with mocked boto3."""
    mock_dynamodb = MagicMock()
    mock_cognito = MagicMock()

    with patch("boto3.resource", return_value=mock_dynamodb), \
         patch("boto3.client", return_value=mock_cognito):
        mod_key = "lambdas.users.CreateUser.handler"
        if mod_key in sys.modules:
            del sys.modules[mod_key]
        from lambdas.users.CreateUser import handler as mod

        yield mod


def _mock_table(items):
    """Create a mock DynamoDB table that returns the given items from scan."""
    table = MagicMock()
    table.scan.return_value = {"Items": items}
    return table


class TestGenerateNextUserCode:
    """Tests for generate_next_user_code function."""

    def test_returns_usr_001_when_no_codes_exist(self, create_user_mod):
        table = _mock_table([])
        result = create_user_mod.generate_next_user_code(table)
        assert result == "USR-001"

    def test_increments_from_single_existing_code(self, create_user_mod):
        table = _mock_table([{"userCode": "USR-001"}])
        result = create_user_mod.generate_next_user_code(table)
        assert result == "USR-002"

    def test_finds_max_from_multiple_codes(self, create_user_mod):
        table = _mock_table([
            {"userCode": "USR-001"},
            {"userCode": "USR-003"},
            {"userCode": "USR-002"},
        ])
        result = create_user_mod.generate_next_user_code(table)
        assert result == "USR-004"

    def test_gap_in_sequence_uses_max(self, create_user_mod):
        """USR-001 and USR-003 exist — next should be USR-004, not USR-002."""
        table = _mock_table([
            {"userCode": "USR-001"},
            {"userCode": "USR-003"},
        ])
        result = create_user_mod.generate_next_user_code(table)
        assert result == "USR-004"

    def test_zero_padded_to_three_digits(self, create_user_mod):
        table = _mock_table([{"userCode": "USR-008"}])
        result = create_user_mod.generate_next_user_code(table)
        assert result == "USR-009"

    def test_extends_beyond_three_digits(self, create_user_mod):
        table = _mock_table([{"userCode": "USR-999"}])
        result = create_user_mod.generate_next_user_code(table)
        assert result == "USR-1000"

    def test_handles_pagination(self, create_user_mod):
        """Verify the function handles DynamoDB pagination correctly."""
        table = MagicMock()
        table.scan.side_effect = [
            {"Items": [{"userCode": "USR-001"}], "LastEvaluatedKey": {"userId": "x"}},
            {"Items": [{"userCode": "USR-005"}]},
        ]
        result = create_user_mod.generate_next_user_code(table)
        assert result == "USR-006"
        assert table.scan.call_count == 2
