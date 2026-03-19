"""Property-based tests for timesheet period date validation.

Property 1: Period date constraints
- For any valid period, startDate is always Monday, endDate is always Friday,
  and endDate == startDate + 4 days.

Validates: Requirements 5.2, 5.3
"""

import os
import sys
from datetime import date, timedelta

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lambdas"))

from lambdas.periods.shared_utils import validate_period_dates


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Generate arbitrary Mondays between 2020 and 2035
mondays = st.dates(
    min_value=date(2020, 1, 6),   # a known Monday
    max_value=date(2035, 12, 29), # a known Monday
).filter(lambda d: d.weekday() == 0)

# Generate arbitrary non-Monday dates for negative testing
non_mondays = st.dates(
    min_value=date(2020, 1, 1),
    max_value=date(2035, 12, 31),
).filter(lambda d: d.weekday() != 0)


# ---------------------------------------------------------------------------
# Property 1: Valid periods always have Monday start, Friday end,
#             and endDate == startDate + 4 days
# ---------------------------------------------------------------------------

class TestPeriodDateConstraintsProperty:
    """Property: for any Monday start date, constructing a valid period
    with endDate = startDate + 4 always passes validation, and the
    resulting dates satisfy the constraints."""

    @given(start=mondays)
    @settings(max_examples=200)
    def test_valid_period_always_accepted(self, start):
        """A correctly constructed period (Mon start, Fri end) must never raise."""
        end = start + timedelta(days=4)

        # Should not raise
        validate_period_dates(start.isoformat(), end.isoformat())

        # Verify the constraints hold
        assert start.weekday() == 0, "startDate must be Monday"
        assert end.weekday() == 4, "endDate must be Friday"
        assert end == start + timedelta(days=4), "endDate must be startDate + 4"

    @given(start=non_mondays)
    @settings(max_examples=200)
    def test_non_monday_start_always_rejected(self, start):
        """Any startDate that is not a Monday must be rejected."""
        end = start + timedelta(days=4)

        with pytest.raises(ValueError, match="not a Monday"):
            validate_period_dates(start.isoformat(), end.isoformat())

    @given(start=mondays, bad_offset=st.integers(min_value=1, max_value=30).filter(lambda x: x != 4))
    @settings(max_examples=200)
    def test_wrong_span_always_rejected(self, start, bad_offset):
        """If endDate != startDate + 4, validation must fail (either wrong
        weekday or wrong span)."""
        end = start + timedelta(days=bad_offset)

        with pytest.raises(ValueError):
            validate_period_dates(start.isoformat(), end.isoformat())
