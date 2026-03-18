"""Property-based tests for chargeability percentage calculation.

Property 5: Chargeability percentage consistency
- For any Employee_Performance record where ytdTotalHours > 0,
  ytdChargabilityPercentage == (ytdChargable_hours / ytdTotalHours) * 100

Validates: Requirements 11.2
"""

import os
import sys
from decimal import Decimal, ROUND_HALF_UP

from hypothesis import given, settings, assume
from hypothesis import strategies as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lambdas"))

from lambdas.performance.handler import calculate_chargeability_percentage


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# YTD hours: non-negative decimals with up to 2 decimal places,
# representing realistic yearly hour totals (0.00 to 9999.99)
ytd_hours = st.decimals(
    min_value=Decimal("0.00"),
    max_value=Decimal("9999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

# Positive total hours (> 0) for cases where percentage is meaningful
positive_total_hours = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("9999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)


# ---------------------------------------------------------------------------
# Property 5: Chargeability percentage consistency
# ---------------------------------------------------------------------------

class TestChargeabilityPercentageProperty:
    """Property: for any Employee_Performance record where ytdTotalHours > 0,
    ytdChargabilityPercentage == (ytdChargable_hours / ytdTotalHours) * 100."""

    @given(chargeable=ytd_hours, total=positive_total_hours)
    @settings(max_examples=300)
    def test_percentage_equals_formula(self, chargeable, total):
        """ytdChargabilityPercentage must always equal
        (ytdChargable_hours / ytdTotalHours) * 100, rounded to 2 decimal
        places with ROUND_HALF_UP.

        **Validates: Requirements 11.2**
        """
        result = calculate_chargeability_percentage(chargeable, total)

        expected = (chargeable / total * Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        assert result == expected, (
            f"chargeability {result} != expected {expected} "
            f"for chargeable={chargeable}, total={total}"
        )

    @given(chargeable=ytd_hours, total=positive_total_hours)
    @settings(max_examples=300)
    def test_percentage_is_non_negative(self, chargeable, total):
        """Since both chargeable and total hours are non-negative,
        the percentage must also be non-negative.

        **Validates: Requirements 11.2**
        """
        result = calculate_chargeability_percentage(chargeable, total)
        assert result >= Decimal("0"), (
            f"chargeability percentage should be non-negative, got {result}"
        )

    @given(total=positive_total_hours)
    @settings(max_examples=200)
    def test_zero_chargeable_yields_zero_percentage(self, total):
        """When chargeable hours are zero, the percentage must be exactly 0.

        **Validates: Requirements 11.2**
        """
        result = calculate_chargeability_percentage(Decimal("0"), total)
        assert result == Decimal("0"), (
            f"expected 0% for zero chargeable hours, got {result}"
        )

    @given(hours=positive_total_hours)
    @settings(max_examples=200)
    def test_equal_hours_yields_100_percent(self, hours):
        """When chargeable hours equal total hours, the percentage must
        be exactly 100.00.

        **Validates: Requirements 11.2**
        """
        result = calculate_chargeability_percentage(hours, hours)
        assert result == Decimal("100.00"), (
            f"expected 100.00% when chargeable == total, got {result}"
        )

    @given(chargeable=ytd_hours)
    @settings(max_examples=200)
    def test_zero_total_yields_zero_percentage(self, chargeable):
        """When total hours is zero, the percentage must be 0 (division
        by zero is handled gracefully).

        **Validates: Requirements 11.2**
        """
        result = calculate_chargeability_percentage(chargeable, Decimal("0"))
        assert result == Decimal("0"), (
            f"expected 0% for zero total hours, got {result}"
        )
