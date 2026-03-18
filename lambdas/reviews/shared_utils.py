"""Shared utilities for review handlers."""

VALID_REVIEW_TRANSITIONS = {
    ("Submitted", "Approved"),
    ("Submitted", "Rejected"),
}


def validate_review_transition(current_status, target_status):
    if (current_status, target_status) not in VALID_REVIEW_TRANSITIONS:
        raise ValueError(
            f"Cannot transition from '{current_status}' to '{target_status}'. "
            f"Only timesheets with status 'Submitted' can be approved or rejected"
        )
