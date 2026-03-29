"""Property-based tests for feedback toast behavior on master data pages.

These tests model the client-side JavaScript showToast() function and CRUD
operation feedback logic as pure Python and verify universal properties
across generated inputs.

Feature: admin-ui-revisions

Property 4: CRUD operations produce feedback toast
Property 5: Toast styling matches message type

Validates: Requirements 2.1–2.12, 2.14
"""

from hypothesis import given, settings
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Model of the Feedback Toast (mirrors showToast() JS behaviour)
# ---------------------------------------------------------------------------

MASTER_DATA_PAGES = ["departments", "positions", "projects", "users"]
CRUD_OPERATIONS = ["create", "update", "delete"]


class FeedbackToast:
    """Models the Feedback_Toast element created by showToast() in Blade templates."""

    def __init__(self, message: str, toast_type: str):
        self.message = message
        self.toast_type = toast_type  # "success" or "error"
        self.visible = True

        # Styling mirrors the inline CSS from showToast()
        if toast_type == "error":
            self.background_color = "#fef2f2"
            self.text_color = "#991b1b"
            self.border_color = "#fecaca"
        else:
            self.background_color = "#f0fdf4"
            self.text_color = "#166534"
            self.border_color = "#bbf7d0"


class CrudOperationResult:
    """Models the result of a CRUD API call from a master data page."""

    def __init__(self, success: bool, error_message: str = ""):
        self.success = success
        self.error_message = error_message


def perform_crud_operation(
    page: str, operation: str, api_result: CrudOperationResult
) -> FeedbackToast:
    """Models the CRUD operation feedback flow from the Blade templates.

    After a CRUD operation completes, the JS calls showToast() with the
    appropriate message and type, then schedules a page reload after 1500ms.
    """
    entity_label = page.rstrip("s")  # "departments" -> "department"

    if api_result.success:
        past_tense = {
            "create": "created",
            "update": "updated",
            "delete": "deleted",
        }
        message = f"{entity_label.capitalize()} {past_tense[operation]} successfully."
        return FeedbackToast(message, "success")
    else:
        default_messages = {
            "create": f"Failed to create {entity_label}.",
            "update": f"Failed to update {entity_label}.",
            "delete": f"Failed to delete {entity_label}.",
        }
        message = api_result.error_message or default_messages[operation]
        return FeedbackToast(message, "error")



# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

page_strategy = st.sampled_from(MASTER_DATA_PAGES)
operation_strategy = st.sampled_from(CRUD_OPERATIONS)

error_message_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Z", "P")),
    min_size=1,
    max_size=200,
).filter(lambda s: s.strip())

toast_type_strategy = st.sampled_from(["success", "error"])


# ---------------------------------------------------------------------------
# Property 4: CRUD operations produce feedback toast
# ---------------------------------------------------------------------------

class TestCrudOperationsProduceFeedbackToast:
    """Property 4: For any CRUD operation (create, update, delete) on any
    master data page (departments, positions, projects, users), the operation
    shall result in a visible Feedback_Toast element in the DOM — with a
    success message when the API returns success, or an error message
    containing the failure reason when the API returns an error.

    **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10, 2.11, 2.12**
    """

    @given(
        page=page_strategy,
        operation=operation_strategy,
    )
    @settings(max_examples=200)
    def test_successful_crud_produces_success_toast(self, page, operation):
        """A successful CRUD operation produces a visible success toast.

        **Validates: Requirements 2.1, 2.3, 2.5, 2.7, 2.9, 2.11**
        """
        api_result = CrudOperationResult(success=True)
        toast = perform_crud_operation(page, operation, api_result)

        assert toast.visible is True, (
            f"Toast must be visible after {operation} on {page}"
        )
        assert toast.toast_type == "success", (
            f"Toast type must be 'success' for successful {operation} on {page}"
        )
        assert "successfully" in toast.message.lower(), (
            f"Success toast message must contain 'successfully', got: '{toast.message}'"
        )

    @given(
        page=page_strategy,
        operation=operation_strategy,
        error_msg=error_message_strategy,
    )
    @settings(max_examples=200)
    def test_failed_crud_produces_error_toast_with_reason(
        self, page, operation, error_msg
    ):
        """A failed CRUD operation produces a visible error toast containing
        the failure reason from the API response.

        **Validates: Requirements 2.2, 2.4, 2.6, 2.8, 2.10, 2.12**
        """
        api_result = CrudOperationResult(success=False, error_message=error_msg)
        toast = perform_crud_operation(page, operation, api_result)

        assert toast.visible is True, (
            f"Toast must be visible after failed {operation} on {page}"
        )
        assert toast.toast_type == "error", (
            f"Toast type must be 'error' for failed {operation} on {page}"
        )
        assert toast.message == error_msg, (
            f"Error toast must contain the API failure reason '{error_msg}', "
            f"got: '{toast.message}'"
        )

    @given(
        page=page_strategy,
        operation=operation_strategy,
    )
    @settings(max_examples=200)
    def test_failed_crud_without_reason_shows_default_message(
        self, page, operation
    ):
        """A failed CRUD operation with no error message falls back to a
        default failure message mentioning the operation.

        **Validates: Requirements 2.2, 2.4, 2.6, 2.8, 2.10, 2.12**
        """
        api_result = CrudOperationResult(success=False, error_message="")
        toast = perform_crud_operation(page, operation, api_result)

        assert toast.visible is True, (
            f"Toast must be visible after failed {operation} on {page}"
        )
        assert toast.toast_type == "error", (
            f"Toast type must be 'error' for failed {operation} on {page}"
        )
        assert "failed" in toast.message.lower(), (
            f"Default error message must contain 'failed', got: '{toast.message}'"
        )


# ---------------------------------------------------------------------------
# Property 5: Toast styling matches message type
# ---------------------------------------------------------------------------

class TestToastStylingMatchesMessageType:
    """Property 5: For any Feedback_Toast, if the type is "success" then the
    toast background color shall be green-tinted (#f0fdf4) and text color
    shall be green (#166534); if the type is "error" then the background
    shall be red-tinted (#fef2f2) and text color shall be red (#991b1b).

    **Validates: Requirements 2.14**
    """

    @given(
        message=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N", "Z")),
            min_size=1,
            max_size=200,
        ).filter(lambda s: s.strip()),
    )
    @settings(max_examples=200)
    def test_success_toast_has_green_styling(self, message):
        """A success toast uses green background (#f0fdf4) and green text (#166534).

        **Validates: Requirements 2.14**
        """
        toast = FeedbackToast(message, "success")

        assert toast.background_color == "#f0fdf4", (
            f"Success toast background must be #f0fdf4, got: {toast.background_color}"
        )
        assert toast.text_color == "#166534", (
            f"Success toast text color must be #166534, got: {toast.text_color}"
        )

    @given(
        message=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N", "Z")),
            min_size=1,
            max_size=200,
        ).filter(lambda s: s.strip()),
    )
    @settings(max_examples=200)
    def test_error_toast_has_red_styling(self, message):
        """An error toast uses red background (#fef2f2) and red text (#991b1b).

        **Validates: Requirements 2.14**
        """
        toast = FeedbackToast(message, "error")

        assert toast.background_color == "#fef2f2", (
            f"Error toast background must be #fef2f2, got: {toast.background_color}"
        )
        assert toast.text_color == "#991b1b", (
            f"Error toast text color must be #991b1b, got: {toast.text_color}"
        )

    @given(
        toast_type=toast_type_strategy,
        message=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N", "Z")),
            min_size=1,
            max_size=200,
        ).filter(lambda s: s.strip()),
    )
    @settings(max_examples=200)
    def test_toast_styling_is_consistent_for_type(self, toast_type, message):
        """Two toasts with the same type always get the same styling.

        **Validates: Requirements 2.14**
        """
        toast_a = FeedbackToast(message, toast_type)
        toast_b = FeedbackToast("different message", toast_type)

        assert toast_a.background_color == toast_b.background_color, (
            "Toasts of the same type must have identical background colors"
        )
        assert toast_a.text_color == toast_b.text_color, (
            "Toasts of the same type must have identical text colors"
        )
