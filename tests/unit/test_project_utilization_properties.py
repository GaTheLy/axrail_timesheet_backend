"""Property-based tests for Project Summary utilization calculation.

Property 7: Project utilization calculation
- For any project row in Project Summary, utilization ==
  (charged hours / planned hours) * 100 when planned hours > 0

Validates: Requirements 10.3
"""

import os
import sys
from decimal import Decimal, ROUND_HALF_UP

from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lambdas"))

from lambdas.reports.handler import calculate_project_utilization


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Project hours: non-negative decimals with up to 2 decimal places,
# representing realistic project hour totals (0.00 to 99999.99)
project_hours = st.decimals(
    min_value=Decimal("0.00"),
    max_value=Decimal("99999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

# Positive planned hours (> 0) for cases where utilization is meaningful
positive_planned_hours = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("99999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)


# ---------------------------------------------------------------------------
# Property 7: Project utilization calculation
# ---------------------------------------------------------------------------

class TestProjectUtilizationProperty:
    """Property: for any project row in Project Summary, utilization ==
    (charged hours / planned hours) * 100 when planned hours > 0."""

    @given(charged=project_hours, planned=positive_planned_hours)
    @settings(max_examples=300)
    def test_utilization_equals_formula(self, charged, planned):
        """Utilization must always equal
        (charged_hours / planned_hours) * 100, rounded to 2 decimal
        places with ROUND_HALF_UP.

        **Validates: Requirements 10.3**
        """
        result = calculate_project_utilization(charged, planned)

        expected = (charged / planned * Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        assert result == expected, (
            f"utilization {result} != expected {expected} "
            f"for charged={charged}, planned={planned}"
        )

    @given(charged=project_hours, planned=positive_planned_hours)
    @settings(max_examples=300)
    def test_utilization_is_non_negative(self, charged, planned):
        """Since both charged and planned hours are non-negative,
        the utilization percentage must also be non-negative.

        **Validates: Requirements 10.3**
        """
        result = calculate_project_utilization(charged, planned)
        assert result >= Decimal("0"), (
            f"utilization should be non-negative, got {result}"
        )

    @given(planned=positive_planned_hours)
    @settings(max_examples=200)
    def test_zero_charged_yields_zero(self, planned):
        """When charged hours are zero, utilization must be exactly 0.

        **Validates: Requirements 10.3**
        """
        result = calculate_project_utilization(Decimal("0"), planned)
        assert result == Decimal("0"), (
            f"expected 0% for zero charged hours, got {result}"
        )

    @given(hours=positive_planned_hours)
    @settings(max_examples=200)
    def test_equal_hours_yields_100_percent(self, hours):
        """When charged hours equal planned hours, utilization must
        be exactly 100.00.

        **Validates: Requirements 10.3**
        """
        result = calculate_project_utilization(hours, hours)
        assert result == Decimal("100.00"), (
            f"expected 100.00% when charged == planned, got {result}"
        )

    @given(charged=project_hours)
    @settings(max_examples=200)
    def test_zero_planned_yields_zero(self, charged):
        """When planned hours is zero, utilization must be 0 (division
        by zero is handled gracefully).

        **Validates: Requirements 10.3**
        """
        result = calculate_project_utilization(charged, Decimal("0"))
        assert result == Decimal("0"), (
            f"expected 0% for zero planned hours, got {result}"
        )
