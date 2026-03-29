"""Property-based tests for activate/deactivate toggle on the User_Page.

These tests model the client-side JavaScript toggle behavior as pure Python
and verify universal properties across generated inputs.

Feature: admin-ui-revisions

Property 8: Toggle state reflects user status
Property 9: Failed toggle reverts to previous state
Property 11: Pending users have disabled toggle

Validates: Requirements 4.1, 4.2, 4.9, 4.12
"""

from hypothesis import given, settings
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Model of the Activation Toggle (mirrors JS behaviour in user-management)
# ---------------------------------------------------------------------------

USER_STATUSES = ["active", "inactive"]
APPROVAL_STATUSES = ["Approved", "Pending_Approval", "Rejected"]


class ActivationToggle:
    """Models the Activation_Toggle control in each user row."""

    def __init__(self, checked: bool, disabled: bool):
        self.checked = checked
        self.disabled = disabled
        self.previous_checked = checked


class FeedbackToast:
    """Models the Feedback_Toast shown after toggle operations."""

    def __init__(self, message: str, toast_type: str):
        self.message = message
        self.toast_type = toast_type  # "success" or "error"
        self.visible = True


class UserRow:
    """Models a user row on the User_Page with toggle state."""

    def __init__(self, user_id: str, full_name: str, status: str,
                 approval_status: str):
        self.user_id = user_id
        self.full_name = full_name
        self.status = status
        self.approval_status = approval_status
        self.toggle = self._create_toggle()
        self.toast = None

    def _create_toggle(self) -> ActivationToggle:
        """Create toggle based on user status and approval status.

        Mirrors the Blade template logic:
        - checked = true iff status is "active"
        - disabled = true iff approval_status is "Pending_Approval"
        """
        checked = self.status == "active"
        disabled = self.approval_status == "Pending_Approval"
        return ActivationToggle(checked=checked, disabled=disabled)

    def attempt_toggle(self, api_success: bool, error_message: str = ""):
        """Simulate clicking the toggle and receiving an API response.

        Mirrors the JS click handler flow:
        1. Toggle is clicked (checked state flips optimistically or after confirm)
        2. Confirmation dialog shown -> user confirms
        3. API call made
        4. On success: keep new state, show success toast
        5. On failure: revert to previous state, show error toast
        """
        if self.toggle.disabled:
            # Pending users cannot toggle — click is a no-op
            return

        # Save previous state before the toggle attempt
        previous_checked = self.toggle.checked

        if api_success:
            # Flip the toggle state
            self.toggle.checked = not previous_checked
            self.toggle.previous_checked = self.toggle.checked
            new_status = "active" if self.toggle.checked else "inactive"
            action = "activated" if self.toggle.checked else "deactivated"
            self.status = new_status
            self.toast = FeedbackToast(
                f"User {action} successfully.", "success"
            )
        else:
            # Revert toggle to previous state
            self.toggle.checked = previous_checked
            self.toast = FeedbackToast(
                error_message or "Failed to update user status.", "error"
            )


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

user_id_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
    min_size=1,
    max_size=36,
)

full_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "Z")),
    min_size=1,
    max_size=80,
).filter(lambda s: s.strip())

user_status_strategy = st.sampled_from(USER_STATUSES)
approval_status_strategy = st.sampled_from(APPROVAL_STATUSES)

# Approval statuses that are NOT Pending_Approval (for Property 8)
non_pending_approval_strategy = st.sampled_from(["Approved", "Rejected"])

error_message_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Z", "P")),
    min_size=1,
    max_size=200,
).filter(lambda s: s.strip())

user_row_strategy = st.builds(
    UserRow,
    user_id=user_id_strategy,
    full_name=full_name_strategy,
    status=user_status_strategy,
    approval_status=approval_status_strategy,
)


# ---------------------------------------------------------------------------
# Property 8: Toggle state reflects user status
# ---------------------------------------------------------------------------

class TestToggleStateReflectsUserStatus:
    """Property 8: For any user row on the User_Page where approval_status is
    not "Pending_Approval", the Activation_Toggle checked state shall be
    `true` if and only if the user's status is "active".

    **Validates: Requirements 4.1, 4.2**
    """

    @given(
        user_id=user_id_strategy,
        full_name=full_name_strategy,
        status=user_status_strategy,
        approval_status=non_pending_approval_strategy,
    )
    @settings(max_examples=200)
    def test_toggle_checked_iff_active(self, user_id, full_name, status,
                                       approval_status):
        """Toggle is checked if and only if user status is "active".

        **Validates: Requirements 4.1, 4.2**
        """
        row = UserRow(user_id, full_name, status, approval_status)

        if status == "active":
            assert row.toggle.checked is True, (
                f"Toggle must be checked for active user '{full_name}', "
                f"approval_status='{approval_status}'"
            )
        else:
            assert row.toggle.checked is False, (
                f"Toggle must be unchecked for inactive user '{full_name}', "
                f"approval_status='{approval_status}'"
            )

    @given(
        user_id=user_id_strategy,
        full_name=full_name_strategy,
        status=user_status_strategy,
        approval_status=non_pending_approval_strategy,
    )
    @settings(max_examples=200)
    def test_toggle_checked_equals_status_active(self, user_id, full_name,
                                                  status, approval_status):
        """The biconditional: toggle.checked == (status == "active").

        **Validates: Requirements 4.1, 4.2**
        """
        row = UserRow(user_id, full_name, status, approval_status)

        assert row.toggle.checked == (status == "active"), (
            f"toggle.checked ({row.toggle.checked}) must equal "
            f"(status == 'active') ({status == 'active'}) "
            f"for user '{full_name}' with status '{status}'"
        )

    @given(
        user_id=user_id_strategy,
        full_name=full_name_strategy,
        approval_status=non_pending_approval_strategy,
    )
    @settings(max_examples=200)
    def test_toggle_not_disabled_for_non_pending(self, user_id, full_name,
                                                  approval_status):
        """Non-pending users have an enabled (not disabled) toggle.

        **Validates: Requirements 4.1, 4.2**
        """
        row = UserRow(user_id, full_name, "active", approval_status)

        assert row.toggle.disabled is False, (
            f"Toggle must not be disabled for non-pending user '{full_name}' "
            f"with approval_status='{approval_status}'"
        )


# ---------------------------------------------------------------------------
# Property 9: Failed toggle reverts to previous state
# ---------------------------------------------------------------------------

class TestFailedToggleRevertsToPreviousState:
    """Property 9: For any user on the User_Page, if an activate or deactivate
    API call fails, the Activation_Toggle shall revert to its state before the
    click, and an error Feedback_Toast shall be visible.

    **Validates: Requirements 4.9**
    """

    @given(
        user_id=user_id_strategy,
        full_name=full_name_strategy,
        status=user_status_strategy,
        approval_status=non_pending_approval_strategy,
        error_msg=error_message_strategy,
    )
    @settings(max_examples=200)
    def test_failed_toggle_reverts_checked_state(self, user_id, full_name,
                                                  status, approval_status,
                                                  error_msg):
        """After a failed API call, toggle.checked equals its value before
        the click.

        **Validates: Requirements 4.9**
        """
        row = UserRow(user_id, full_name, status, approval_status)
        original_checked = row.toggle.checked

        # Attempt toggle with API failure
        row.attempt_toggle(api_success=False, error_message=error_msg)

        assert row.toggle.checked == original_checked, (
            f"Toggle must revert to {original_checked} after failed API call, "
            f"got {row.toggle.checked} for user '{full_name}' "
            f"with status '{status}'"
        )

    @given(
        user_id=user_id_strategy,
        full_name=full_name_strategy,
        status=user_status_strategy,
        approval_status=non_pending_approval_strategy,
        error_msg=error_message_strategy,
    )
    @settings(max_examples=200)
    def test_failed_toggle_shows_error_toast(self, user_id, full_name,
                                              status, approval_status,
                                              error_msg):
        """After a failed API call, an error Feedback_Toast is visible with
        the failure reason.

        **Validates: Requirements 4.9**
        """
        row = UserRow(user_id, full_name, status, approval_status)
        row.attempt_toggle(api_success=False, error_message=error_msg)

        assert row.toast is not None, (
            "A Feedback_Toast must be shown after a failed toggle"
        )
        assert row.toast.visible is True, (
            "The error toast must be visible"
        )
        assert row.toast.toast_type == "error", (
            f"Toast type must be 'error' after failed toggle, "
            f"got '{row.toast.toast_type}'"
        )
        assert row.toast.message == error_msg, (
            f"Toast message must contain the failure reason '{error_msg}', "
            f"got '{row.toast.message}'"
        )

    @given(
        user_id=user_id_strategy,
        full_name=full_name_strategy,
        status=user_status_strategy,
        approval_status=non_pending_approval_strategy,
    )
    @settings(max_examples=200)
    def test_failed_toggle_preserves_user_status(self, user_id, full_name,
                                                  status, approval_status):
        """After a failed API call, the user's status field is unchanged.

        **Validates: Requirements 4.9**
        """
        row = UserRow(user_id, full_name, status, approval_status)
        original_status = row.status

        row.attempt_toggle(api_success=False)

        assert row.status == original_status, (
            f"User status must remain '{original_status}' after failed toggle, "
            f"got '{row.status}'"
        )


# ---------------------------------------------------------------------------
# Property 11: Pending users have disabled toggle
# ---------------------------------------------------------------------------

class TestPendingUsersHaveDisabledToggle:
    """Property 11: For any user row on the User_Page where approval_status is
    "Pending_Approval", the Activation_Toggle shall be disabled (not clickable).

    **Validates: Requirements 4.12**
    """

    @given(
        user_id=user_id_strategy,
        full_name=full_name_strategy,
        status=user_status_strategy,
    )
    @settings(max_examples=200)
    def test_pending_user_toggle_is_disabled(self, user_id, full_name, status):
        """A user with approval_status "Pending_Approval" has a disabled toggle.

        **Validates: Requirements 4.12**
        """
        row = UserRow(user_id, full_name, status, "Pending_Approval")

        assert row.toggle.disabled is True, (
            f"Toggle must be disabled for pending user '{full_name}' "
            f"with status '{status}'"
        )

    @given(
        user_id=user_id_strategy,
        full_name=full_name_strategy,
        status=user_status_strategy,
    )
    @settings(max_examples=200)
    def test_pending_user_toggle_click_is_noop(self, user_id, full_name, status):
        """Clicking the toggle on a pending user does nothing — no state change,
        no toast, no API call.

        **Validates: Requirements 4.12**
        """
        row = UserRow(user_id, full_name, status, "Pending_Approval")
        original_checked = row.toggle.checked

        # Attempt toggle — should be a no-op because toggle is disabled
        row.attempt_toggle(api_success=True)

        assert row.toggle.checked == original_checked, (
            f"Toggle must remain {original_checked} for pending user "
            f"'{full_name}' — click should be a no-op"
        )
        assert row.toast is None, (
            "No toast should appear when clicking a disabled toggle"
        )

    @given(
        user_id=user_id_strategy,
        full_name=full_name_strategy,
        status=user_status_strategy,
        approval_status=approval_status_strategy,
    )
    @settings(max_examples=200)
    def test_toggle_disabled_iff_pending_approval(self, user_id, full_name,
                                                   status, approval_status):
        """Toggle is disabled if and only if approval_status is
        "Pending_Approval".

        **Validates: Requirements 4.12**
        """
        row = UserRow(user_id, full_name, status, approval_status)

        expected_disabled = approval_status == "Pending_Approval"
        assert row.toggle.disabled == expected_disabled, (
            f"toggle.disabled ({row.toggle.disabled}) must equal "
            f"(approval_status == 'Pending_Approval') ({expected_disabled}) "
            f"for user '{full_name}' with approval_status '{approval_status}'"
        )
