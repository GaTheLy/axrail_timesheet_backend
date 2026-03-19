"""Property-based tests for timesheet entry daily hours validation.

Property 2: Daily hours constraint
- For any set of entries in a submission, the sum of hours for any single day
  across all entries never exceeds 24.0.

Validates: Requirements 15.2
"""

import os
import sys
from decimal import Decimal

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lambdas"))

from lambdas.entries.shared_utils import validate_daily_totals, DAY_FIELDS, MAX_DAILY_HOURS



# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Generate a valid daily hours Decimal: non-negative, max 2 decimal places,
# range 0.00 to MAX_DAILY_HOURS (8.00 after bugfix)
daily_hours_decimal = st.decimals(
    min_value=Decimal("0.00"),
    max_value=MAX_DAILY_HOURS,
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

# Generate a dict representing one entry's daily hours (all 7 day fields)
entry_hours = st.fixed_dictionaries(
    {day: daily_hours_decimal for day in DAY_FIELDS}
)


# ---------------------------------------------------------------------------
# Property 2: Daily hours constraint — total per day across entries <= 24.0
# ---------------------------------------------------------------------------

class TestDailyHoursConstraintProperty:
    """Property: for any set of entries in a submission, the sum of hours for
    any single day across all entries never exceeds 24.0."""

    @given(
        existing=st.lists(entry_hours, min_size=0, max_size=26),
        new=entry_hours,
    )
    @settings(max_examples=200)
    def test_valid_daily_totals_always_accepted(self, existing, new):
        """When every day's total across existing entries + new entry is <= 24.0,
        validation must pass.

        **Validates: Requirements 15.2**
        """
        for day in DAY_FIELDS:
            day_total = new[day] + sum(e[day] for e in existing)
            assume(day_total <= MAX_DAILY_HOURS)

        validate_daily_totals(existing, new)

    @given(
        existing=st.lists(entry_hours, min_size=0, max_size=26),
        new=entry_hours,
    )
    @settings(max_examples=200)
    def test_exceeding_daily_totals_always_rejected(self, existing, new):
        """When at least one day's total across existing entries + new entry
        exceeds 24.0, validation must raise ValueError.

        **Validates: Requirements 15.2**
        """
        any_exceeds = False
        for day in DAY_FIELDS:
            day_total = new[day] + sum(e[day] for e in existing)
            if day_total > MAX_DAILY_HOURS:
                any_exceeds = True
                break
        assume(any_exceeds)

        with pytest.raises(ValueError, match="exceeds the maximum"):
            validate_daily_totals(existing, new)

    @given(
        base_hours=st.lists(
            daily_hours_decimal,
            min_size=1,
            max_size=26,
        ),
    )
    @settings(max_examples=200)
    def test_exact_boundary_always_accepted(self, base_hours):
        """When every day's total is exactly 24.0, validation must pass
        (boundary condition).

        **Validates: Requirements 15.2**
        """
        n = len(base_hours)
        per_entry_value = base_hours[0]
        total_existing = per_entry_value * n
        assume(total_existing <= MAX_DAILY_HOURS)

        remainder = MAX_DAILY_HOURS - total_existing

        existing = [
            {day: per_entry_value for day in DAY_FIELDS}
            for _ in range(n)
        ]

        new_hours = {day: remainder for day in DAY_FIELDS}

        validate_daily_totals(existing, new_hours)
