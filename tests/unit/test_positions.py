"""Unit tests for lambdas/positions/handler.py — Position Management resolvers.

Validates: Requirements 3.4, 3.6
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lambdas"))

os.environ.setdefault("POSITIONS_TABLE", "PositionsTable")


def _make_event(
    field_name="createPosition",
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
    mock_table = MagicMock()
    mock_table.query.return_value = {"Items": []}
    mock_table.put_item.return_value = {}
    mock_table.get_item.return_value = {
        "Item": {
            "positionId": "pos-100",
            "positionName": "Senior Engineer",
            "description": "Senior level engineer",
            "createdAt": "2025-01-01T00:00:00+00:00",
            "createdBy": "caller-001",
        }
    }
    mock_table.delete_item.return_value = {}
    mock_table.update_item.return_value = {
        "Attributes": {
            "positionId": "pos-100",
            "positionName": "Senior Engineer",
            "updatedAt": "2025-06-01T00:00:00+00:00",
            "updatedBy": "caller-001",
        }
    }

    mock_dynamodb = MagicMock()
    mock_dynamodb.Table.return_value = mock_table

    with patch("boto3.resource", return_value=mock_dynamodb):
        if "lambdas.positions.handler" in sys.modules:
            del sys.modules["lambdas.positions.handler"]
        from lambdas.positions import handler as mod

        mod.dynamodb = mock_dynamodb

        yield {
            "table": mock_table,
            "handler_mod": mod,
        }


# ---------------------------------------------------------------------------
# Unique position name enforcement — Requirement 3.4
# ---------------------------------------------------------------------------


class TestPositionNameUniqueness:
    def test_duplicate_name_rejected_on_create(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        table = _mock_boto["table"]
        table.query.return_value = {
            "Items": [{"positionId": "pos-existing", "positionName": "Senior Engineer"}]
        }
        event = _make_event(
            arguments={"input": {"positionName": "Senior Engineer", "description": "desc"}},
        )
        with pytest.raises(ValueError, match="already in use"):
            mod.create_position(event)

    def test_unique_name_accepted_on_create(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        table = _mock_boto["table"]
        table.query.return_value = {"Items": []}
        event = _make_event(
            arguments={"input": {"positionName": "Junior Engineer", "description": "desc"}},
        )
        result = mod.create_position(event)
        assert result["positionName"] == "Junior Engineer"

    def test_duplicate_name_rejected_on_update(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        table = _mock_boto["table"]
        table.query.return_value = {
            "Items": [{"positionId": "pos-other", "positionName": "Manager"}]
        }
        event = _make_event(
            field_name="updatePosition",
            arguments={
                "positionId": "pos-100",
                "input": {"positionName": "Manager"},
            },
        )
        with pytest.raises(ValueError, match="already in use"):
            mod.update_position(event)

    def test_same_name_allowed_on_update_for_same_position(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        table = _mock_boto["table"]
        table.query.return_value = {
            "Items": [{"positionId": "pos-100", "positionName": "Senior Engineer"}]
        }
        event = _make_event(
            field_name="updatePosition",
            arguments={
                "positionId": "pos-100",
                "input": {"positionName": "Senior Engineer"},
            },
        )
        result = mod.update_position(event)
        assert result is not None


# ---------------------------------------------------------------------------
# Superadmin-only authorization — Requirement 3.6
# ---------------------------------------------------------------------------


class TestPositionAuthorization:
    def test_admin_forbidden_create(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        event = _make_event(
            user_type="admin",
            arguments={"input": {"positionName": "Intern", "description": "desc"}},
        )
        with pytest.raises(Exception, match="not authorized"):
            mod.handler(event, None)

    def test_user_forbidden_create(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        event = _make_event(
            user_type="user",
            arguments={"input": {"positionName": "Intern", "description": "desc"}},
        )
        with pytest.raises(Exception, match="not authorized"):
            mod.handler(event, None)

    def test_admin_forbidden_update(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        event = _make_event(
            field_name="updatePosition",
            user_type="admin",
            arguments={"positionId": "pos-100", "input": {"positionName": "Lead"}},
        )
        with pytest.raises(Exception, match="not authorized"):
            mod.handler(event, None)

    def test_admin_forbidden_delete(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        event = _make_event(
            field_name="deletePosition",
            user_type="admin",
            arguments={"positionId": "pos-100"},
        )
        with pytest.raises(Exception, match="not authorized"):
            mod.handler(event, None)

    def test_superadmin_allowed_create(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        event = _make_event(
            user_type="superadmin",
            arguments={"input": {"positionName": "Architect", "description": "desc"}},
        )
        result = mod.handler(event, None)
        assert result["positionName"] == "Architect"

    def test_superadmin_allowed_delete(self, _mock_boto):
        mod = _mock_boto["handler_mod"]
        event = _make_event(
            field_name="deletePosition",
            user_type="superadmin",
            arguments={"positionId": "pos-100"},
        )
        result = mod.handler(event, None)
        assert result is True
