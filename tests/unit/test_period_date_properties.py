"""Property-based tests for timesheet period date validation.

Property 1: Period date constraints
- For any valid period, startDate is always Saturday, endDate is always Friday,
  and endDate == startDate + 6 days.

Validates: Requirements 5.2, 5.3
"""

import os
import sys
from datetime import date, timedelta

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lambdas"))

from lambdas.periods.handler import _validate_period_dates


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Generate arbitrary Saturdays between 2020 and 2035
saturdays = st.dates(
    min_value=date(2020, 1, 4),   # a known Saturday
    max_value=date(2035, 12, 27), # a known Saturday
).filter(lambda d: d.weekday() == 5)

# Generate arbitrary non-Saturday dates for negative testing
non_saturdays = st.dates(
    min_value=date(2020, 1, 1),
    max_value=date(2035, 12, 31),
).filter(lambda d: d.weekday() != 5)

# Deadline offset: 0 to 30 days after endDate
deadline_offset = st.integers(min_value=0, max_value=30)


# ---------------------------------------------------------------------------
# Property 1: Valid periods always have Saturday start, Friday end,
#             and endDate == startDate + 6 days
# ---------------------------------------------------------------------------

class TestPeriodDateConstraintsProperty:
    """Property: for any Saturday start date, constructing a valid period
    with endDate = startDate + 6 and deadline >= endDate always passes
    validation, and the resulting dates satisfy the constraints."""

    @given(start=saturdays, offset=deadline_offset)
    @settings(max_examples=200)
    def test_valid_period_always_accepted(self, start, offset):
        """A correctly constructed period (Sat start, Fri end, valid deadline)
        must never raise."""
        end = start + timedelta(days=6)
        deadline = end + timedelta(days=offset)

        # Should not raise
        _validate_period_dates(
            start.isoformat(),
            end.isoformat(),
            deadline.isoformat(),
        )

        # Verify the constraints hold
        assert start.weekday() == 5, "startDate must be Saturday"
        assert end.weekday() == 4, "endDate must be Friday"
        assert end == start + timedelta(days=6), "endDate must be startDate + 6"

    @given(start=non_saturdays)
    @settings(max_examples=200)
    def test_non_saturday_start_always_rejected(self, start):
        """Any startDate that is not a Saturday must be rejected."""
        end = start + timedelta(days=6)
        deadline = end + timedelta(days=1)

        with pytest.raises(ValueError, match="not a Saturday"):
            _validate_period_dates(
                start.isoformat(),
                end.isoformat(),
                deadline.isoformat(),
            )

    @given(start=saturdays, bad_offset=st.integers(min_value=1, max_value=30).filter(lambda x: x != 6))
    @settings(max_examples=200)
    def test_wrong_span_always_rejected(self, start, bad_offset):
        """If endDate != startDate + 6, validation must fail (either wrong
        weekday or wrong span)."""
        end = start + timedelta(days=bad_offset)
        deadline = end + timedelta(days=1)

        with pytest.raises(ValueError):
            _validate_period_dates(
                start.isoformat(),
                end.isoformat(),
                deadline.isoformat(),
            )

    @given(start=saturdays, early_days=st.integers(min_value=1, max_value=30))
    @settings(max_examples=200)
    def test_deadline_before_end_always_rejected(self, start, early_days):
        """A submission deadline before endDate must always be rejected."""
        end = start + timedelta(days=6)
        deadline = end - timedelta(days=early_days)

        with pytest.raises(ValueError, match="submissionDeadline"):
            _validate_period_dates(
                start.isoformat(),
                end.isoformat(),
                deadline.isoformat(),
            )
