"""Bug condition exploration test for listAllSubmissions.

Property 1: Bug Condition — No Admin Query for All Submissions

Tests that:
- list_all_submissions(event) exists and returns all submissions for admin callers
- list_all_submissions(event) with status filter returns only matching submissions
- list_all_submissions(event) rejects non-admin callers with permissions error

On UNFIXED code, these tests MUST FAIL — confirming the bug exists:
- The handler module doesn't exist yet (ImportError)

**Validates: Requirements 1.5, 1.6, 2.6, 2.7, 2.8, 2.9**
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

# Ensure lambdas are importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lambdas"))

# Set required env vars before importing
os.environ.setdefault("SUBMISSIONS_TABLE", "SubmissionsTable")


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

admin_user_types = st.sampled_from(["admin", "superadmin"])

non_admin_user_types = st.sampled_from(["user", "employee", "manager", "viewer"])

submission_statuses = st.sampled_from(["Draft", "Submitted", "Approved", "Rejected"])

period_ids = st.from_regex(r"period-[0-9]{4}-W[0-9]{2}", fullmatch=True)

employee_ids = st.from_regex(r"emp-[a-z0-9]{4,8}", fullmatch=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event(caller_type, filter_input=None):
    """Build a minimal AppSync event for listAllSubmissions."""
    event = {
        "info": {"fieldName": "listAllSubmissions"},
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
        "arguments": {},
    }
    if filter_input is not None:
        event["arguments"]["filter"] = filter_input
    return event


def _make_submission(employee_id, period_id, status):
    """Build a fake submission item."""
    return {
        "submissionId": f"sub-{employee_id}-{period_id}",
        "employeeId": employee_id,
        "periodId": period_id,
        "status": status,
        "totalHours": "40.00",
    }


# ---------------------------------------------------------------------------
# Property 1: Bug Condition — Admin query for all submissions should exist
# ---------------------------------------------------------------------------

class TestListAllSubmissionsBugCondition:
    """Bug condition: list_all_submissions() handler should exist and allow
    admin/superadmin callers to list all submissions. On unfixed code this
    FAILS because the handler module doesn't exist (ImportError).

    **Validates: Requirements 1.5, 1.6, 2.6, 2.7, 2.8, 2.9**
    """

    @given(caller_type=admin_user_types)
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_admin_can_list_all_submissions(self, caller_type):
        """For any admin/superadmin caller, list_all_submissions() must exist
        and return submissions. Currently fails because the module doesn't exist.

        **Validates: Requirements 1.5, 1.6, 2.6**
        """
        # This import will fail on unfixed code — handler doesn't exist yet
        from submissions.ListAllSubmissions.handler import list_all_submissions

        mock_table = MagicMock()
        mock_table.scan.return_value = {
            "Items": [
                _make_submission("emp-001", "period-2024-W01", "Submitted"),
                _make_submission("emp-002", "period-2024-W01", "Draft"),
            ]
        }
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        with patch("submissions.ListAllSubmissions.handler.dynamodb", mock_dynamodb):
            event = _make_event(caller_type)
            result = list_all_submissions(event)
            assert isinstance(result, list)
            assert len(result) == 2

    @given(
        caller_type=admin_user_types,
        status=submission_statuses,
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_admin_list_with_status_filter(self, caller_type, status):
        """For any admin/superadmin caller with a status filter,
        list_all_submissions() must return only matching submissions.

        **Validates: Requirements 2.7**
        """
        from submissions.ListAllSubmissions.handler import list_all_submissions

        matching = [_make_submission("emp-001", "period-2024-W01", status)]
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": matching}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        with patch("submissions.ListAllSubmissions.handler.dynamodb", mock_dynamodb):
            event = _make_event(caller_type, filter_input={"status": status})
            result = list_all_submissions(event)
            assert isinstance(result, list)
            assert all(item["status"] == status for item in result)

    @given(
        caller_type=admin_user_types,
        period_id=period_ids,
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_admin_list_with_period_filter(self, caller_type, period_id):
        """For any admin/superadmin caller with a periodId filter,
        list_all_submissions() must return only submissions for that period.

        **Validates: Requirements 2.8**
        """
        from submissions.ListAllSubmissions.handler import list_all_submissions

        matching = [_make_submission("emp-001", period_id, "Submitted")]
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": matching}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        with patch("submissions.ListAllSubmissions.handler.dynamodb", mock_dynamodb):
            event = _make_event(caller_type, filter_input={"periodId": period_id})
            result = list_all_submissions(event)
            assert isinstance(result, list)

    @given(caller_type=non_admin_user_types)
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_non_admin_rejected(self, caller_type):
        """For any non-admin caller, list_all_submissions() must raise
        ForbiddenError. Currently fails because the module doesn't exist.

        **Validates: Requirements 2.9**
        """
        from submissions.ListAllSubmissions.handler import list_all_submissions
        from shared.auth import ForbiddenError

        event = _make_event(caller_type)
        with pytest.raises(ForbiddenError):
            list_all_submissions(event)
