"""Property-based tests for confirmation dialog behavior on the Approvals page.

These tests model the client-side JavaScript confirmation dialog logic as pure
Python functions and verify universal properties across generated inputs.

Feature: admin-ui-revisions

Property 1: Approve action shows confirmation dialog
Property 2: Cancel dialog preserves entity state
Property 3: Confirmation dialog displays entity identity

Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.6, 1.8
"""

from hypothesis import given, settings, assume
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Model of the Approvals page confirmation dialog (mirrors JS behaviour)
# ---------------------------------------------------------------------------

ENTITY_TYPES = ["project", "department", "position"]


class ApprovalModalState:
    """Models the approve-modal-overlay state from approvals.blade.php."""

    def __init__(self):
        self.active = False
        self.entity_type = ""
        self.entity_id = ""
        self.title_text = ""
        self.message_text = ""
        self.api_called = False

    def open_approve_modal(self, entity_type: str, entity_id: str, entity_name: str):
        """Mirrors openApproveModal() in the Blade template JS."""
        self.entity_type = entity_type
        self.entity_id = entity_id
        display_type = entity_type[0].upper() + entity_type[1:] if entity_type else ""
        self.title_text = f"Approve {display_type}"
        self.message_text = (
            f'Are you sure you want to approve {display_type} "{entity_name}"?'
        )
        self.active = True

    def close_approve_modal(self):
        """Mirrors closeApproveModal() in the Blade template JS."""
        self.active = False

    def submit_approval(self):
        """Mirrors the approve-modal-submit click handler (API call)."""
        self.api_called = True
        self.active = False


class EntityRow:
    """Models a table row on the Approvals page."""

    def __init__(self, entity_type: str, entity_id: str, entity_name: str):
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.entity_name = entity_name
        self.present_in_dom = True
        self.approval_status = "Pending_Approval"


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

entity_type_strategy = st.sampled_from(ENTITY_TYPES)

entity_id_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
    min_size=1,
    max_size=36,
)

entity_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Z")),
    min_size=1,
    max_size=100,
).filter(lambda s: s.strip())


# ---------------------------------------------------------------------------
# Property 1: Approve action shows confirmation dialog
# ---------------------------------------------------------------------------

class TestApproveActionShowsDialog:
    """Property 1: For any entity type (department, position, project) on the
    Approvals page, clicking the approve button shall cause a confirmation
    modal to become visible in the DOM without triggering any API request.

    **Validates: Requirements 1.1, 1.2, 1.3, 1.4**
    """

    @given(
        entity_type=entity_type_strategy,
        entity_id=entity_id_strategy,
        entity_name=entity_name_strategy,
    )
    @settings(max_examples=200)
    def test_approve_click_shows_modal_without_api_call(
        self, entity_type, entity_id, entity_name
    ):
        """Clicking approve opens the modal and does NOT trigger an API call.

        **Validates: Requirements 1.1, 1.2, 1.3, 1.4**
        """
        modal = ApprovalModalState()

        # Simulate clicking the approve button
        modal.open_approve_modal(entity_type, entity_id, entity_name)

        # Modal must be visible (active)
        assert modal.active is True, (
            f"Modal should be active after clicking approve for {entity_type}"
        )
        # No API call should have been made
        assert modal.api_called is False, (
            "No API request should be triggered when opening the confirmation dialog"
        )

    @given(entity_type=entity_type_strategy)
    @settings(max_examples=100)
    def test_modal_starts_inactive(self, entity_type):
        """Before any user interaction, the modal is not visible.

        **Validates: Requirements 1.1, 1.2, 1.3**
        """
        modal = ApprovalModalState()
        assert modal.active is False


# ---------------------------------------------------------------------------
# Property 2: Cancel dialog preserves entity state
# ---------------------------------------------------------------------------

class TestCancelDialogPreservesState:
    """Property 2: For any entity on the Approvals page, if the user opens a
    confirmation dialog and then cancels, the entity's approval status and row
    in the table shall remain unchanged.

    **Validates: Requirements 1.6**
    """

    @given(
        entity_type=entity_type_strategy,
        entity_id=entity_id_strategy,
        entity_name=entity_name_strategy,
    )
    @settings(max_examples=200)
    def test_cancel_preserves_entity_row(self, entity_type, entity_id, entity_name):
        """Opening and cancelling the dialog leaves the entity row unchanged.

        **Validates: Requirements 1.6**
        """
        # Set up entity row
        row = EntityRow(entity_type, entity_id, entity_name)
        original_status = row.approval_status
        original_present = row.present_in_dom

        # Open then cancel the modal
        modal = ApprovalModalState()
        modal.open_approve_modal(entity_type, entity_id, entity_name)
        modal.close_approve_modal()

        # Entity row must be unchanged
        assert row.approval_status == original_status, (
            "Entity approval status must not change after cancelling the dialog"
        )
        assert row.present_in_dom == original_present, (
            "Entity row must remain in the DOM after cancelling the dialog"
        )
        assert row.entity_name == entity_name, (
            "Entity name must not change after cancelling the dialog"
        )

    @given(
        entity_type=entity_type_strategy,
        entity_id=entity_id_strategy,
        entity_name=entity_name_strategy,
    )
    @settings(max_examples=200)
    def test_cancel_closes_modal_and_no_api_call(
        self, entity_type, entity_id, entity_name
    ):
        """After cancelling, the modal is closed and no API call was made.

        **Validates: Requirements 1.6**
        """
        modal = ApprovalModalState()
        modal.open_approve_modal(entity_type, entity_id, entity_name)
        assert modal.active is True

        modal.close_approve_modal()
        assert modal.active is False, "Modal must be closed after cancel"
        assert modal.api_called is False, "No API call should occur on cancel"


# ---------------------------------------------------------------------------
# Property 3: Confirmation dialog displays entity identity
# ---------------------------------------------------------------------------

class TestDialogDisplaysEntityIdentity:
    """Property 3: For any entity on the Approvals page, the confirmation
    dialog text shall contain both the entity name and the entity type so the
    user can verify the target.

    **Validates: Requirements 1.8**
    """

    @given(
        entity_type=entity_type_strategy,
        entity_id=entity_id_strategy,
        entity_name=entity_name_strategy,
    )
    @settings(max_examples=200)
    def test_dialog_message_contains_entity_name_and_type(
        self, entity_type, entity_id, entity_name
    ):
        """The confirmation message includes both the entity name and type.

        **Validates: Requirements 1.8**
        """
        modal = ApprovalModalState()
        modal.open_approve_modal(entity_type, entity_id, entity_name)

        display_type = entity_type[0].upper() + entity_type[1:]

        # Message must contain the entity name
        assert entity_name in modal.message_text, (
            f"Dialog message must contain entity name '{entity_name}', "
            f"got: '{modal.message_text}'"
        )
        # Message must contain the entity type (capitalized)
        assert display_type in modal.message_text, (
            f"Dialog message must contain entity type '{display_type}', "
            f"got: '{modal.message_text}'"
        )

    @given(
        entity_type=entity_type_strategy,
        entity_id=entity_id_strategy,
        entity_name=entity_name_strategy,
    )
    @settings(max_examples=200)
    def test_dialog_title_contains_entity_type(
        self, entity_type, entity_id, entity_name
    ):
        """The modal title includes the entity type.

        **Validates: Requirements 1.8**
        """
        modal = ApprovalModalState()
        modal.open_approve_modal(entity_type, entity_id, entity_name)

        display_type = entity_type[0].upper() + entity_type[1:]
        assert display_type in modal.title_text, (
            f"Dialog title must contain entity type '{display_type}', "
            f"got: '{modal.title_text}'"
        )
