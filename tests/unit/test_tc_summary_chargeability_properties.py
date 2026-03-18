"""Property-based tests for TC Summary chargeability calculation.

Property 6: TC Summary chargeability calculation
- For any employee row in TC Summary, current period chargeability ==
  (chargeable hours / total hours) * 100 when total hours > 0

Validates: Requirements 9.3
"""

import os
import sys
from decimal import Decimal, ROUND_HALF_UP

from hypothesis import given, settings, assume
from hypothesis import strategies as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lambdas"))

from lambdas.reports.handler import calculate_current_period_chargeability


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Period hours: non-negative decimals with up to 2 decimal places,
# representing realistic weekly hour totals (0.00 to 168.00 — max hours in a week)
period_hours = st.decimals(
    min_value=Decimal("0.00"),
    max_value=Decimal("168.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

# Positive total hours (> 0) for cases where chargeability is meaningful
positive_total_hours = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("168.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)


# ---------------------------------------------------------------------------
# Property 6: TC Summary chargeability calculation
# ---------------------------------------------------------------------------

class TestTCSummaryChargeabilityProperty:
    """Property: for any employee row in TC Summary, current period
    chargeability == (chargeable hours / total hours) * 100 when
    total hours > 0."""

    @given(chargeable=period_hours, total=positive_total_hours)
    @settings(max_examples=300)
    def test_chargeability_equals_formula(self, chargeable, total):
        """Current period chargeability must always equal
        (chargeable_hours / total_hours) * 100, rounded to 2 decimal
        places with ROUND_HALF_UP.

        **Validates: Requirements 9.3**
        """
        result = calculate_current_period_chargeability(chargeable, total)

        expected = (chargeable / total * Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        assert result == expected, (
            f"chargeability {result} != expected {expected} "
            f"for chargeable={chargeable}, total={total}"
        )

    @given(chargeable=period_hours, total=positive_total_hours)
    @settings(max_examples=300)
    def test_chargeability_is_non_negative(self, chargeable, total):
        """Since both chargeable and total hours are non-negative,
        the chargeability percentage must also be non-negative.

        **Validates: Requirements 9.3**
        """
        result = calculate_current_period_chargeability(chargeable, total)
        assert result >= Decimal("0"), (
            f"chargeability should be non-negative, got {result}"
        )

    @given(total=positive_total_hours)
    @settings(max_examples=200)
    def test_zero_chargeable_yields_zero(self, total):
        """When chargeable hours are zero, chargeability must be exactly 0.

        **Validates: Requirements 9.3**
        """
        result = calculate_current_period_chargeability(Decimal("0"), total)
        assert result == Decimal("0"), (
            f"expected 0% for zero chargeable hours, got {result}"
        )

    @given(hours=positive_total_hours)
    @settings(max_examples=200)
    def test_equal_hours_yields_100_percent(self, hours):
        """When chargeable hours equal total hours, chargeability must
        be exactly 100.00.

        **Validates: Requirements 9.3**
        """
        result = calculate_current_period_chargeability(hours, hours)
        assert result == Decimal("100.00"), (
            f"expected 100.00% when chargeable == total, got {result}"
        )

    @given(chargeable=period_hours)
    @settings(max_examples=200)
    def test_zero_total_yields_zero(self, chargeable):
        """When total hours is zero, chargeability must be 0 (division
        by zero is handled gracefully).

        **Validates: Requirements 9.3**
        """
        result = calculate_current_period_chargeability(chargeable, Decimal("0"))
        assert result == Decimal("0"), (
            f"expected 0% for zero total hours, got {result}"
        )
