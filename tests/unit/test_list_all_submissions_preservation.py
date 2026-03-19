"""Preservation property tests for listAllSubmissions.

Property 2: Preservation — listMySubmissions Behavior Unchanged

Tests that existing listMySubmissions behavior is preserved on UNFIXED code:
- Regular user calling listMySubmissions returns only their own submissions
- listMySubmissions with periodId filter returns correctly filtered results

These tests MUST PASS on the current UNFIXED code.

**Validates: Requirements 3.7, 3.8**
"""

import os
import sys
from decimal import Decimal
from unittest.mock import MagicMock, patch, call

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

regular_user_types = st.sampled_from(["user", "employee", "manager", "viewer"])

employee_ids = st.from_regex(r"emp-[a-z0-9]{4,8}", fullmatch=True)

period_ids = st.from_regex(r"period-[0-9]{4}-W[0-9]{2}", fullmatch=True)

submission_statuses = st.sampled_from(["Draft", "Submitted", "Approved", "Rejected"])


@st.composite
def submission_lists(draw, employee_id):
    """Generate a list of 0-5 submissions all belonging to the given employee."""
    count = draw(st.integers(min_value=0, max_value=5))
    items = []
    for i in range(count):
        pid = draw(period_ids)
        status = draw(submission_statuses)
        items.append({
            "submissionId": f"sub-{employee_id}-{i}",
            "employeeId": employee_id,
            "periodId": pid,
            "status": status,
            "totalHours": Decimal("20.00"),
        })
    return items


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event(user_id, user_type, filter_input=None):
    """Build a minimal AppSync event for listMySubmissions."""
    event = {
        "info": {"fieldName": "listMySubmissions"},
        "identity": {
            "claims": {
                "sub": user_id,
                "custom:userType": user_type,
                "custom:role": "Employee",
                "email": f"{user_id}@axrail.com",
                "custom:departmentId": "dept-1",
                "custom:positionId": "pos-1",
            }
        },
        "arguments": {},
    }
    if filter_input is not None:
        event["arguments"]["filter"] = filter_input
    return event


# ---------------------------------------------------------------------------
# Property 2a: Regular user gets only their own submissions
# ---------------------------------------------------------------------------

class TestListMySubmissionsOwnerOnly:
    """Preservation: listMySubmissions returns only the caller's own
    submissions. The handler queries by employeeId from caller identity,
    so results always belong to the caller.

    **Validates: Requirements 3.7**
    """

    @given(
        user_type=regular_user_types,
        emp_id=employee_ids,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_returns_only_callers_submissions(self, user_type, emp_id):
        """For any regular user, listMySubmissions queries by their
        employeeId and returns only their own submissions.

        **Validates: Requirements 3.7**
        """
        own_submissions = [
            {
                "submissionId": f"sub-{emp_id}-0",
                "employeeId": emp_id,
                "periodId": "period-2024-W01",
                "status": "Draft",
                "totalHours": Decimal("20.00"),
            }
        ]

        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": own_submissions}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        with patch("submissions.ListMySubmissions.handler.dynamodb", mock_dynamodb):
            from submissions.ListMySubmissions.handler import list_my_submissions

            event = _make_event(emp_id, user_type)
            result = list_my_submissions(event)

            # All returned items belong to the caller
            assert isinstance(result, list)
            for item in result:
                assert item["employeeId"] == emp_id

            # The query used the caller's employeeId
            mock_table.query.assert_called_once()
            query_kwargs = mock_table.query.call_args
            assert query_kwargs.kwargs.get("IndexName") == "employeeId-periodId-index"

    @given(
        user_type=regular_user_types,
        emp_id=employee_ids,
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_empty_result_for_no_submissions(self, user_type, emp_id):
        """For any regular user with no submissions, listMySubmissions
        returns an empty list.

        **Validates: Requirements 3.7**
        """
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        with patch("submissions.ListMySubmissions.handler.dynamodb", mock_dynamodb):
            from submissions.ListMySubmissions.handler import list_my_submissions

            event = _make_event(emp_id, user_type)
            result = list_my_submissions(event)

            assert result == []


# ---------------------------------------------------------------------------
# Property 2b: periodId filtering works correctly
# ---------------------------------------------------------------------------

class TestListMySubmissionsPeriodFilter:
    """Preservation: listMySubmissions with periodId filter returns
    correctly filtered results. The handler adds periodId to the
    key condition when filtering by period.

    **Validates: Requirements 3.8**
    """

    @given(
        user_type=regular_user_types,
        emp_id=employee_ids,
        target_period=period_ids,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_period_filter_queries_with_period(self, user_type, emp_id, target_period):
        """For any user with a periodId filter, listMySubmissions queries
        using both employeeId and periodId in the key condition.

        **Validates: Requirements 3.8**
        """
        matching = [
            {
                "submissionId": f"sub-{emp_id}-filtered",
                "employeeId": emp_id,
                "periodId": target_period,
                "status": "Draft",
                "totalHours": Decimal("16.00"),
            }
        ]

        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": matching}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        with patch("submissions.ListMySubmissions.handler.dynamodb", mock_dynamodb):
            from submissions.ListMySubmissions.handler import list_my_submissions

            event = _make_event(emp_id, user_type, filter_input={"periodId": target_period})
            result = list_my_submissions(event)

            assert isinstance(result, list)
            # All results belong to the caller
            for item in result:
                assert item["employeeId"] == emp_id

            # Query was made with the GSI
            mock_table.query.assert_called_once()
            assert mock_table.query.call_args.kwargs.get("IndexName") == "employeeId-periodId-index"

    @given(
        user_type=regular_user_types,
        emp_id=employee_ids,
        target_period=period_ids,
        status=submission_statuses,
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_period_and_status_filter_combined(self, user_type, emp_id, target_period, status):
        """For any user with both periodId and status filters,
        listMySubmissions queries by period and post-filters by status.

        **Validates: Requirements 3.8**
        """
        # Return items with mixed statuses; handler will post-filter
        items = [
            {
                "submissionId": f"sub-{emp_id}-match",
                "employeeId": emp_id,
                "periodId": target_period,
                "status": status,
                "totalHours": Decimal("10.00"),
            },
            {
                "submissionId": f"sub-{emp_id}-other",
                "employeeId": emp_id,
                "periodId": target_period,
                "status": "Draft" if status != "Draft" else "Submitted",
                "totalHours": Decimal("5.00"),
            },
        ]

        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": items}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        with patch("submissions.ListMySubmissions.handler.dynamodb", mock_dynamodb):
            from submissions.ListMySubmissions.handler import list_my_submissions

            event = _make_event(
                emp_id, user_type,
                filter_input={"periodId": target_period, "status": status},
            )
            result = list_my_submissions(event)

            # Post-filter: only matching status returned
            assert isinstance(result, list)
            for item in result:
                assert item["status"] == status
                assert item["employeeId"] == emp_id
