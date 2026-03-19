"""Bug condition exploration test for hour caps.

Property 1: Bug Condition — Exceeding 8h/day or 40h/week Accepted

Tests that:
- validate_daily_totals() rejects entries with any day >8h
- validate_weekly_total() rejects entries with weekly total >40h

On UNFIXED code, these tests MUST FAIL — confirming the bugs exist:
- Daily cap is 24h instead of 8h (Case A fails)
- Weekly cap function doesn't exist (Case B fails)

**Validates: Requirements 1.3, 1.4, 1.5a, 2.3, 2.4, 2.5a**
"""

import os
import sys
from decimal import Decimal

import pytest
from hypothesis import given, settings, HealthCheck
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
    DAY_FIELDS,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Case A: A single day with >8 hours but ≤24 hours (currently accepted, should be rejected)
daily_hours_exceeding_8 = st.decimals(
    min_value=Decimal("8.01"),
    max_value=Decimal("24.00"),
    places=2,
)

day_index = st.sampled_from(list(range(len(DAY_FIELDS))))


# Case B: Entries totaling >40 weekly hours where no single day exceeds 24 hours
# Distribute hours across 7 days so weekly total >40 but each day ≤24
def weekly_hours_exceeding_40():
    """Generate a dict of daily hours where weekly total >40 but each day ≤8.
    We use 6 days at exactly 7h each = 42h total, which exceeds 40h
    but no single day exceeds 8h (or 24h)."""
    return st.builds(
        lambda base_hours: {
            day: base_hours if i < 6 else Decimal("0.00")
            for i, day in enumerate(DAY_FIELDS)
        },
        st.just(Decimal("7.00")),
    ) | st.builds(
        _build_weekly_over_40,
        st.decimals(min_value=Decimal("5.72"), max_value=Decimal("8.00"), places=2),
    )


def _build_weekly_over_40(per_day):
    """Build hours dict with per_day on all 7 days. 
    If per_day >= 5.72, then 7 * 5.72 = 40.04 > 40."""
    return {day: per_day for day in DAY_FIELDS}


# ---------------------------------------------------------------------------
# Property 1 Case A: Daily cap should be 8h, not 24h
# ---------------------------------------------------------------------------

class TestDailyCapBugCondition:
    """Bug condition: validate_daily_totals() should reject entries where any
    single day exceeds 8 hours. On unfixed code this FAILS because the cap
    is 24h instead of 8h.

    **Validates: Requirements 1.5a, 2.5a**
    """

    @given(
        excess_hours=daily_hours_exceeding_8,
        target_day_idx=day_index,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_daily_hours_over_8_rejected(self, excess_hours, target_day_idx):
        """For any entry with a single day >8h (but ≤24h), validate_daily_totals()
        must raise ValueError. Currently fails because MAX_DAILY_HOURS is 24.

        **Validates: Requirements 1.5a, 2.5a**
        """
        target_day = DAY_FIELDS[target_day_idx]

        # Build new_hours with the excess on one day, 0 on others
        new_hours = {day: Decimal("0.00") for day in DAY_FIELDS}
        new_hours[target_day] = excess_hours

        # No existing entries — just the new entry alone exceeds 8h on one day
        existing_entries = []

        with pytest.raises(ValueError, match="exceeds the maximum"):
            validate_daily_totals(existing_entries, new_hours)


# ---------------------------------------------------------------------------
# Property 1 Case B: Weekly 40h cap doesn't exist
# ---------------------------------------------------------------------------

class TestWeeklyCapBugCondition:
    """Bug condition: validate_weekly_total() should exist and reject entries
    where weekly total exceeds 40 hours. On unfixed code this FAILS because
    the function doesn't exist yet.

    **Validates: Requirements 1.3, 1.4, 2.3, 2.4**
    """

    @given(per_day=st.decimals(min_value=Decimal("5.72"), max_value=Decimal("8.00"), places=2))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_weekly_hours_over_40_rejected(self, per_day):
        """For entries where weekly total >40h (but each day ≤8h),
        validate_weekly_total() must raise ValueError.
        Currently fails because the function doesn't exist.

        **Validates: Requirements 1.3, 1.4, 2.3, 2.4**
        """
        new_hours = {day: per_day for day in DAY_FIELDS}
        new_hours["totalHours"] = per_day * 7

        # Confirm bug condition: weekly total >40 but each day ≤24 (and ≤8)
        weekly_total = sum(new_hours[day] for day in DAY_FIELDS)
        assert weekly_total > Decimal("40.0"), f"Weekly total {weekly_total} should exceed 40"
        assert all(new_hours[day] <= Decimal("8.00") for day in DAY_FIELDS)

        # No existing entries
        existing_entries = []

        # Import validate_weekly_total — this will fail on unfixed code
        # because the function doesn't exist yet
        from shared_utils import validate_weekly_total

        with pytest.raises(ValueError, match="exceeds the maximum"):
            validate_weekly_total(existing_entries, new_hours)
