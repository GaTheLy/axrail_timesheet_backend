"""Property-based tests for timesheet entry row total computation.

Property 3: Row total equals sum of daily values
- For any timesheet entry, totalHours == saturday + sunday + monday +
  tuesday + wednesday + thursday + friday

Validates: Requirements 6.8, 15.5
"""

import os
import sys
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lambdas"))

from lambdas.entries.handler import _parse_and_validate_daily_hours, DAY_FIELDS


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Valid daily hours: non-negative, max 2 decimal places, 0.00–24.00
daily_hours_decimal = st.decimals(
    min_value=Decimal("0.00"),
    max_value=Decimal("24.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

# Input dict with string values (as they'd arrive from GraphQL)
entry_input = st.fixed_dictionaries(
    {day: daily_hours_decimal.map(str) for day in DAY_FIELDS}
)


# ---------------------------------------------------------------------------
# Property 3: Row total equals sum of daily values
# ---------------------------------------------------------------------------

class TestRowTotalProperty:
    """Property: for any timesheet entry, totalHours equals the sum of all
    seven daily Charged_Hours values."""

    @given(input_data=entry_input)
    @settings(max_examples=300)
    def test_total_hours_equals_sum_of_daily_values(self, input_data):
        """totalHours must always equal the arithmetic sum of the seven
        daily hour fields.

        **Validates: Requirements 6.8, 15.5**
        """
        result = _parse_and_validate_daily_hours(input_data)

        expected_total = sum(result[day] for day in DAY_FIELDS)
        assert result["totalHours"] == expected_total, (
            f"totalHours {result['totalHours']} != sum of daily values {expected_total}"
        )

    @given(input_data=entry_input)
    @settings(max_examples=300)
    def test_total_hours_is_non_negative(self, input_data):
        """Since all daily values are non-negative, the row total must also
        be non-negative.

        **Validates: Requirements 6.8, 15.5**
        """
        result = _parse_and_validate_daily_hours(input_data)
        assert result["totalHours"] >= Decimal("0"), (
            f"totalHours should be non-negative, got {result['totalHours']}"
        )

    @given(input_data=st.fixed_dictionaries(
        {day: st.just("0") for day in DAY_FIELDS}
    ))
    @settings(max_examples=1)
    def test_all_zeros_yields_zero_total(self, input_data):
        """When all daily values are zero, totalHours must be exactly 0.

        **Validates: Requirements 6.8, 15.5**
        """
        result = _parse_and_validate_daily_hours(input_data)
        assert result["totalHours"] == Decimal("0")

    @given(input_data=entry_input)
    @settings(max_examples=300)
    def test_total_has_at_most_two_decimal_places(self, input_data):
        """Since each daily value has at most 2 decimal places, the sum of
        7 such values has at most 2 decimal places.

        **Validates: Requirements 15.5**
        """
        result = _parse_and_validate_daily_hours(input_data)
        total = result["totalHours"]
        # Quantize to 2 places — should be identical
        assert total == total.quantize(Decimal("0.01")), (
            f"totalHours {total} has more than 2 decimal places"
        )
