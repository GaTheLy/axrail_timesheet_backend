"""
Property test for design token completeness and correctness.

**Validates: Requirements 1.1**

Property 1: Design token completeness and correctness —
for any design token specified in the requirements, the :root block
in app.css must define a CSS custom property with the specified value.
"""

import re
import os
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# All design tokens specified in the requirements with their exact values
REQUIRED_TOKENS = {
    "--color-primary": "#2563eb",
    "--color-primary-hover": "#1d4ed8",
    "--color-primary-light": "rgba(37, 99, 235, 0.1)",
    "--color-sidebar-bg": "#1e3a5f",
    "--color-sidebar-text": "#ffffff",
    "--color-sidebar-active-bg": "rgba(255, 255, 255, 0.12)",
    "--color-sidebar-hover-bg": "rgba(255, 255, 255, 0.06)",
    "--color-body-bg": "#f1f5f9",
    "--color-surface": "#ffffff",
    "--color-surface-hover": "#f8fafc",
    "--color-text-primary": "#1e293b",
    "--color-text-secondary": "#64748b",
    "--color-border": "#e2e8f0",
    "--color-danger": "#dc2626",
    "--color-danger-hover": "#b91c1c",
    "--radius-sm": "6px",
    "--radius-md": "8px",
    "--radius-lg": "12px",
    "--shadow-sm": "0 1px 2px rgba(0, 0, 0, 0.05)",
    "--shadow-md": "0 4px 12px rgba(0, 0, 0, 0.1)",
    "--font-family": "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    "--font-size-base": "14px",
    "--line-height-base": "1.5",
}

CSS_FILE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "frontend", "public", "css", "app.css"
)


def parse_root_block(css_content: str) -> dict:
    """Parse the :root block from CSS content and return a dict of token name -> value."""
    root_match = re.search(r":root\s*\{([^}]+)\}", css_content, re.DOTALL)
    if not root_match:
        return {}

    root_body = root_match.group(1)
    tokens = {}
    # Match lines like: --color-primary: #2563eb;
    for match in re.finditer(
        r"(--[\w-]+)\s*:\s*(.+?)\s*;", root_body
    ):
        token_name = match.group(1).strip()
        token_value = match.group(2).strip()
        tokens[token_name] = token_value
    return tokens


@pytest.fixture(scope="module")
def parsed_tokens():
    """Load and parse the :root tokens from app.css once per module."""
    with open(CSS_FILE_PATH, "r") as f:
        css_content = f.read()
    return parse_root_block(css_content)


# Strategy that samples from the required token list
token_strategy = st.sampled_from(list(REQUIRED_TOKENS.items()))


class TestDesignTokenCompleteness:
    """
    **Validates: Requirements 1.1**

    Property 1: Design token completeness and correctness —
    for any design token specified in the requirements, the :root block
    defines a CSS custom property with the specified value.
    """

    @given(token=token_strategy)
    @settings(max_examples=100)
    def test_all_required_tokens_exist_with_correct_values(self, parsed_tokens, token):
        """
        **Validates: Requirements 1.1**

        For any design token specified in the requirements, the :root block
        must define a CSS custom property with the specified value.
        """
        token_name, expected_value = token
        assert token_name in parsed_tokens, (
            f"Token '{token_name}' is missing from the :root block in app.css"
        )
        assert parsed_tokens[token_name] == expected_value, (
            f"Token '{token_name}' has value '{parsed_tokens[token_name]}' "
            f"but expected '{expected_value}'"
        )
