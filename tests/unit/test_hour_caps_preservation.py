"""Preservation property tests for hour caps.

Property 2: Preservation — Valid Entries Within Caps Unchanged

Tests that existing behavior is preserved on UNFIXED code:
- Entries with ≤8h per day and ≤40h weekly total pass validation
- Negative hours are rejected with validation error
- 28th entry to a submission is rejected with max entries error

These tests MUST PASS on the current UNFIXED code.

**Validates: Requirements 2.5, 2.5b, 3.4, 3.5**
"""

import os
import sys
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

# Ensure shared_utils is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lambdas", "entries"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lambdas"))

# Set required env vars before importing
os.environ.setdefault("ENTRIES_TABLE", "EntriesTable")
os.environ.setdefault("SUBMISSIONS_TABLE", "SubmissionsTable")
os.environ.setdefault("PROJECTS_TABLE", "ProjectsTable")

from shared_utils import (
    validate_daily_totals,
    validate_daily_hours,
    validate_max_entries,
    parse_and_validate_daily_hours,
    DAY_FIELDS,
    MAX_ENTRIES_PER_SUBMISSION,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Valid daily hours: 0.00 to 8.00 with 2 decimal places
valid_daily_hours = st.decimals(
    min_value=Decimal("0.00"),
    max_value=Decimal("8.00"),
    places=2,
)

# Generate a full week of valid hours where each day ≤8h and weekly total ≤40h
@st.composite
def valid_weekly_hours(draw):
    """Generate daily hours dict where each day ≤8h and weekly total ≤40h."""
    remaining = Decimal("40.00")
    hours = {}
    for i, day in enumerate(DAY_FIELDS):
        if i == len(DAY_FIELDS) - 1:
            # Last day: cap at remaining budget and 8h
            max_val = min(remaining, Decimal("8.00"))
        else:
            max_val = min(remaining, Decimal("8.00"))
        val = draw(st.decimals(
            min_value=Decimal("0.00"),
            max_value=max_val,
            places=2,
        ))
        hours[day] = val
        remaining -= val
    return hours

# Negative hours for a random day
negative_hours = st.decimals(
    min_value=Decimal("-100.00"),
    max_value=Decimal("-0.01"),
    places=2,
)

day_strategy = st.sampled_from(list(DAY_FIELDS))


# ---------------------------------------------------------------------------
# Property 2a: Valid entries within caps are accepted
# ---------------------------------------------------------------------------

class TestValidEntriesPreservation:
    """Preservation: entries with ≤8h/day and ≤40h weekly total pass
    validation on unfixed code. Since the current daily cap is 24h,
    any entry ≤8h/day trivially passes. No weekly cap exists yet,
    so entries ≤40h weekly also pass.

    **Validates: Requirements 2.5, 2.5b**
    """

    @given(hours=valid_weekly_hours())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_valid_hours_accepted_by_daily_totals(self, hours):
        """For any entry where each day ≤8h and weekly total ≤40h,
        validate_daily_totals() accepts the entry (no ValueError raised).

        **Validates: Requirements 2.5, 2.5b**
        """
        # Confirm preconditions
        weekly_total = sum(hours[day] for day in DAY_FIELDS)
        assert all(hours[day] <= Decimal("8.00") for day in DAY_FIELDS)
        assert weekly_total <= Decimal("40.00")

        # No existing entries — just the new entry
        existing_entries = []

        # Should NOT raise — these are valid entries
        validate_daily_totals(existing_entries, hours)

    @given(hours=valid_weekly_hours())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_valid_hours_with_existing_entries_accepted(self, hours):
        """For any new entry where each day ≤8h, when combined with existing
        entries the daily totals still pass validation (existing entries have
        0h so combined totals equal new entry totals).

        **Validates: Requirements 2.5, 2.5b**
        """
        # Existing entry with 0 hours on all days
        existing_entries = [
            {
                "entryId": "existing-001",
                **{day: Decimal("0.00") for day in DAY_FIELDS},
                "totalHours": Decimal("0.00"),
            }
        ]

        # Should NOT raise
        validate_daily_totals(existing_entries, hours)

    @given(hours=valid_weekly_hours())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_parse_and_validate_accepts_valid_hours(self, hours):
        """parse_and_validate_daily_hours() accepts valid hour values
        and returns correct totals.

        **Validates: Requirements 2.5, 2.5b**
        """
        # Convert Decimal to float for input (simulating GraphQL input)
        input_data = {day: float(hours[day]) for day in DAY_FIELDS}

        result = parse_and_validate_daily_hours(input_data)

        # All days should be parsed correctly
        for day in DAY_FIELDS:
            assert result[day] == hours[day]

        # Total should match sum
        expected_total = sum(hours[day] for day in DAY_FIELDS)
        assert result["totalHours"] == expected_total


# ---------------------------------------------------------------------------
# Property 2b: Negative hours rejected (existing behavior preserved)
# ---------------------------------------------------------------------------

class TestNegativeHoursPreservation:
    """Preservation: negative daily hour values are rejected with
    validation error. This existing behavior must be preserved.

    **Validates: Requirements 3.4**
    """

    @given(neg_value=negative_hours, target_day=day_strategy)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_negative_hours_rejected(self, neg_value, target_day):
        """For any negative hour value on any day, validate_daily_hours()
        raises ValueError with 'non-negative' message.

        **Validates: Requirements 3.4**
        """
        with pytest.raises(ValueError, match="non-negative"):
            validate_daily_hours(neg_value, target_day)

    @given(neg_value=negative_hours, target_day=day_strategy)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_negative_hours_in_parse_rejected(self, neg_value, target_day):
        """For any negative hour value in input data, parse_and_validate_daily_hours()
        raises ValueError.

        **Validates: Requirements 3.4**
        """
        input_data = {day: 0.0 for day in DAY_FIELDS}
        input_data[target_day] = float(neg_value)

        with pytest.raises(ValueError, match="non-negative"):
            parse_and_validate_daily_hours(input_data)


# ---------------------------------------------------------------------------
# Property 2c: Max entries limit preserved (existing behavior)
# ---------------------------------------------------------------------------

class TestMaxEntriesPreservation:
    """Preservation: adding a 28th entry to a submission is rejected
    with max entries validation error. This existing behavior must
    be preserved.

    **Validates: Requirements 3.5**
    """

    @given(entry_count=st.integers(min_value=MAX_ENTRIES_PER_SUBMISSION, max_value=50))
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_exceeding_max_entries_rejected(self, entry_count):
        """For any submission with ≥27 entries, adding another entry
        raises ValueError with 'Maximum allowed' message.

        **Validates: Requirements 3.5**
        """
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": [], "Count": entry_count}

        with patch("shared_utils.get_entries_table", return_value=mock_table):
            with pytest.raises(ValueError, match="Maximum allowed"):
                validate_max_entries("submission-001")

    def test_at_limit_minus_one_allowed(self):
        """A submission with 26 entries can accept one more (27th).

        **Validates: Requirements 3.5**
        """
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": [], "Count": 26}

        with patch("shared_utils.get_entries_table", return_value=mock_table):
            # Should NOT raise — 26 < 27
            validate_max_entries("submission-001")
