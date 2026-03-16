"""Authentication and authorization utilities for AppSync Lambda resolvers.

Extracts caller identity from AppSync event context (Cognito claims)
and provides role/user-type authorization helpers.
"""


class ForbiddenError(Exception):
    """Raised when a caller lacks the required role or user type."""

    def __init__(self, message: str = "Access denied"):
        self.message = message
        super().__init__(self.message)


def get_caller_identity(event: dict) -> dict:
    """Extract caller identity from an AppSync event's Cognito claims.

    Args:
        event: The AppSync Lambda resolver event containing identity claims.

    Returns:
        A dict with keys: userId, userType, role, email, departmentId, positionId.

    Raises:
        ValueError: If the event is missing identity or claims data.
    """
    try:
        claims = event["identity"]["claims"]
    except (KeyError, TypeError) as exc:
        raise ValueError("Event is missing identity claims") from exc

    return {
        "userId": claims.get("sub", ""),
        "userType": claims.get("custom:userType", ""),
        "role": claims.get("custom:role", ""),
        "email": claims.get("email", ""),
        "departmentId": claims.get("custom:departmentId", ""),
        "positionId": claims.get("custom:positionId", ""),
    }


def require_role(event: dict, allowed_roles: list[str]) -> dict:
    """Verify the caller has one of the allowed roles.

    Args:
        event: The AppSync Lambda resolver event.
        allowed_roles: List of permitted role values
            (e.g. ["Project_Manager", "Tech_Lead"]).

    Returns:
        The caller identity dict if authorized.

    Raises:
        ForbiddenError: If the caller's role is not in allowed_roles.
    """
    identity = get_caller_identity(event)
    if identity["role"] not in allowed_roles:
        raise ForbiddenError(
            f"Role '{identity['role']}' is not authorized. "
            f"Allowed roles: {allowed_roles}"
        )
    return identity


def require_user_type(event: dict, allowed_types: list[str]) -> dict:
    """Verify the caller has one of the allowed user types.

    Args:
        event: The AppSync Lambda resolver event.
        allowed_types: List of permitted userType values
            (e.g. ["superadmin", "admin"]).

    Returns:
        The caller identity dict if authorized.

    Raises:
        ForbiddenError: If the caller's userType is not in allowed_types.
    """
    identity = get_caller_identity(event)
    if identity["userType"] not in allowed_types:
        raise ForbiddenError(
            f"User type '{identity['userType']}' is not authorized. "
            f"Allowed types: {allowed_types}"
        )
    return identity
