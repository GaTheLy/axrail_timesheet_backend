"""Property-based tests for submission status transitions.

Property 4: Valid status transitions
- The only valid review transitions are Submitted → Approved and
  Submitted → Rejected. Any other source status must be rejected.

Validates: Requirements 7.1, 7.2, 7.5
"""

import os
import sys

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lambdas"))

from lambdas.reviews.handler import (
    _validate_review_transition,
    ALL_STATUSES,
    VALID_REVIEW_TRANSITIONS,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# All possible submission statuses
all_statuses = st.sampled_from(ALL_STATUSES)

# Only the valid review target statuses
review_targets = st.sampled_from(["Approved", "Rejected"])

# Non-Submitted statuses (should always be rejected as source)
non_submitted_statuses = st.sampled_from(
    [s for s in ALL_STATUSES if s != "Submitted"]
)


# ---------------------------------------------------------------------------
# Property 4: Valid status transitions
# ---------------------------------------------------------------------------

class TestSubmissionStatusTransitionProperty:
    """Property: the only valid review transitions are Submitted → Approved
    and Submitted → Rejected. All other source statuses must be rejected."""

    @given(target=review_targets)
    @settings(max_examples=200)
    def test_submitted_to_valid_target_always_accepted(self, target):
        """Transitioning from Submitted to Approved or Rejected must always
        succeed.

        **Validates: Requirements 7.1, 7.2**
        """
        # Should not raise
        _validate_review_transition("Submitted", target)

    @given(source=non_submitted_statuses, target=review_targets)
    @settings(max_examples=200)
    def test_non_submitted_source_always_rejected(self, source, target):
        """Any source status other than Submitted must always be rejected,
        regardless of the target status.

        **Validates: Requirements 7.5**
        """
        with pytest.raises(ValueError, match="Cannot transition"):
            _validate_review_transition(source, target)

    @given(source=all_statuses, target=all_statuses)
    @settings(max_examples=500)
    def test_only_valid_transitions_accepted(self, source, target):
        """For any arbitrary (source, target) pair, the transition is accepted
        if and only if it is in the set of valid review transitions.

        **Validates: Requirements 7.1, 7.2, 7.5**
        """
        if (source, target) in VALID_REVIEW_TRANSITIONS:
            # Must not raise
            _validate_review_transition(source, target)
        else:
            with pytest.raises(ValueError):
                _validate_review_transition(source, target)

    @given(source=non_submitted_statuses)
    @settings(max_examples=200)
    def test_approve_from_invalid_status_always_rejected(self, source):
        """Approving from any status other than Submitted must always fail.

        **Validates: Requirements 7.1, 7.5**
        """
        with pytest.raises(ValueError, match="Cannot transition"):
            _validate_review_transition(source, "Approved")

    @given(source=non_submitted_statuses)
    @settings(max_examples=200)
    def test_reject_from_invalid_status_always_rejected(self, source):
        """Rejecting from any status other than Submitted must always fail.

        **Validates: Requirements 7.2, 7.5**
        """
        with pytest.raises(ValueError, match="Cannot transition"):
            _validate_review_transition(source, "Rejected")
