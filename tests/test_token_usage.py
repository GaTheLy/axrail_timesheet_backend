"""
Property test for design token usage across all component selectors.

**Validates: Requirements 1.1, 1.4**

Property 2: All component color references use design tokens —
for any CSS rule in app.css that sets a color, background, background-color,
border-color, border, or box-shadow property on a component selector
(excluding specific allowed exceptions), the value must reference a var(--)
custom property rather than a hardcoded hex or rgba value.
"""

import re
import os
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st


CSS_FILE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "frontend", "public", "css", "app.css"
)

# Color-related properties to check
COLOR_PROPERTIES = {
    "color",
    "background",
    "background-color",
    "border-color",
    "border",
    "box-shadow",
}

# Selectors that are allowed to use hardcoded color values
ALLOWED_SELECTOR_PATTERNS = [
    r":root",
    r"\.alert-success",
    r"\.alert-error",
    r"\.alert-warning",
    r"\.alert-info",
    r"\.badge-success",
    r"\.badge-warning",
    r"\.badge-info",
    r"\.badge-danger",
    r"\.progress-green\s+\.progress-bar-fill",
    r"\.progress-yellow\s+\.progress-bar-fill",
    r"\.progress-red\s+\.progress-bar-fill",
    r"\.hamburger-line",
    r"\.sidebar-brand\s+\.logo-icon",
    r"\.user-avatar",
    r"\.form-group\s+input::placeholder",
    r"\.form-group\s+textarea::placeholder",
    r"\.filter-bar\s+\.search-input::placeholder",
    r"\.sidebar-logout\s+button:hover",
    r"\.btn-action-danger:hover",
    r"\.skeleton",
    r"\.header-user-avatar",
]

# Values that are always allowed (not considered hardcoded colors)
ALLOWED_VALUES = [
    "transparent",
    "none",
    "inherit",
    "currentcolor",
    "#fff",
    "#ffffff",
    "white",
]


def strip_css_comments(css_text: str) -> str:
    """Remove CSS comments from the text."""
    return re.sub(r"/\*.*?\*/", "", css_text, flags=re.DOTALL)


def extract_keyframe_blocks(css_text: str) -> list:
    """Return list of (start, end) positions for @keyframes blocks."""
    blocks = []
    for m in re.finditer(r"@keyframes\s+[\w-]+\s*\{", css_text):
        start = m.start()
        depth = 0
        i = m.end() - 1
        while i < len(css_text):
            if css_text[i] == "{":
                depth += 1
            elif css_text[i] == "}":
                depth -= 1
                if depth == 0:
                    blocks.append((start, i + 1))
                    break
            i += 1
    return blocks


def extract_media_inner(css_text: str) -> list:
    """Extract inner CSS from @media blocks, returning (inner_css, block_start) pairs."""
    results = []
    for m in re.finditer(r"@media\s*\([^)]+\)\s*\{", css_text):
        start = m.end()
        depth = 1
        i = start
        while i < len(css_text) and depth > 0:
            if css_text[i] == "{":
                depth += 1
            elif css_text[i] == "}":
                depth -= 1
            i += 1
        inner = css_text[start : i - 1]
        results.append((inner, m.start()))
    return results


def is_inside_keyframes(pos: int, keyframe_blocks: list) -> bool:
    """Check if a position is inside a @keyframes block."""
    for start, end in keyframe_blocks:
        if start <= pos < end:
            return True
    return False


def parse_css_rules(css_text: str) -> list:
    """
    Parse CSS rules from text, returning list of (selector, declarations_str).
    Skips @keyframes and @media wrappers (but parses rules inside @media).
    """
    css_text = strip_css_comments(css_text)
    keyframe_blocks = extract_keyframe_blocks(css_text)
    rules = []

    # Extract rules from @media blocks
    media_blocks = extract_media_inner(css_text)
    media_ranges = []
    for inner_css, block_start in media_blocks:
        # Find the end of this media block
        depth = 1
        i = block_start + len(re.match(r"@media\s*\([^)]+\)\s*\{", css_text[block_start:]).group())
        while i < len(css_text) and depth > 0:
            if css_text[i] == "{":
                depth += 1
            elif css_text[i] == "}":
                depth -= 1
            i += 1
        media_ranges.append((block_start, i))

        # Parse rules inside the media block
        for m in re.finditer(r"([^{}]+?)\{([^{}]*)\}", inner_css):
            selector = m.group(1).strip()
            declarations = m.group(2).strip()
            if selector and not selector.startswith("@"):
                rules.append((selector, declarations))

    # Parse top-level rules (not inside @media or @keyframes)
    for m in re.finditer(r"([^{}@]+?)\{([^{}]*)\}", css_text):
        pos = m.start()
        if is_inside_keyframes(pos, keyframe_blocks):
            continue
        inside_media = False
        for ms, me in media_ranges:
            if ms < pos < me:
                inside_media = True
                break
        if inside_media:
            continue
        selector = m.group(1).strip()
        declarations = m.group(2).strip()
        if selector and not selector.startswith("@"):
            rules.append((selector, declarations))

    return rules


def is_selector_allowed(selector: str) -> bool:
    """Check if a selector is in the allowed exceptions list."""
    for pattern in ALLOWED_SELECTOR_PATTERNS:
        if re.search(pattern, selector):
            return True
    return False


def has_hardcoded_color(value: str) -> bool:
    """
    Check if a CSS value contains a hardcoded hex or rgba color
    that is not wrapped in var(--...).
    """
    val_lower = value.lower().strip()

    # Check allowed literal values
    for allowed in ALLOWED_VALUES:
        if val_lower == allowed:
            return False

    # If the entire value is a var() reference, it's fine
    if re.match(r"^var\(--[\w-]+\)$", val_lower):
        return False

    # Check for hardcoded hex colors (#xxx or #xxxxxx)
    # But not inside var() calls
    val_without_vars = re.sub(r"var\(--[\w-]+\)", "", val_lower)

    # Check for hex colors
    if re.search(r"#[0-9a-f]{3,8}\b", val_without_vars):
        # Allow #fff and #ffffff (white)
        hex_matches = re.findall(r"#([0-9a-f]{3,8})\b", val_without_vars)
        for h in hex_matches:
            if h not in ("fff", "ffffff"):
                return True

    # Check for rgba/rgb with numeric values (not inside var())
    if re.search(r"rgba?\s*\(", val_without_vars):
        # Allow sidebar white-based rgba patterns: rgba(255, 255, 255, ...)
        rgba_matches = re.findall(r"rgba?\s*\([^)]+\)", val_without_vars)
        for rgba in rgba_matches:
            # Allow rgba(255, 255, 255, ...) - white-based
            if re.match(r"rgba?\s*\(\s*255\s*,\s*255\s*,\s*255", rgba):
                continue
            # Allow rgba(0, 0, 0, ...) - black-based (used in overlays/shadows)
            if re.match(r"rgba?\s*\(\s*0\s*,\s*0\s*,\s*0", rgba):
                continue
            return True

    return False


def parse_declarations(decl_str: str) -> list:
    """Parse CSS declarations string into list of (property, value) tuples."""
    results = []
    for decl in decl_str.split(";"):
        decl = decl.strip()
        if ":" not in decl:
            continue
        prop, _, val = decl.partition(":")
        prop = prop.strip().lower()
        val = val.strip()
        if prop and val:
            results.append((prop, val))
    return results


def collect_violating_rules(css_text: str) -> list:
    """
    Collect all CSS rules that violate the token usage property.
    Returns list of (selector, property, value) tuples.
    """
    rules = parse_css_rules(css_text)
    violations = []

    for selector, decl_str in rules:
        if is_selector_allowed(selector):
            continue

        declarations = parse_declarations(decl_str)
        for prop, value in declarations:
            if prop not in COLOR_PROPERTIES:
                continue

            # For border shorthand, skip if it's just a size/style (no color)
            if prop == "border":
                # Allow "none", "transparent", etc.
                if value.lower() in ("none", "transparent", "inherit"):
                    continue

            if has_hardcoded_color(value):
                violations.append((selector, prop, value))

    return violations


@pytest.fixture(scope="module")
def css_content():
    """Load app.css content once per module."""
    with open(CSS_FILE_PATH, "r") as f:
        return f.read()


@pytest.fixture(scope="module")
def non_excepted_rules(css_content):
    """Parse all non-excepted CSS rules with color properties."""
    rules = parse_css_rules(css_content)
    color_rules = []

    for selector, decl_str in rules:
        if is_selector_allowed(selector):
            continue
        declarations = parse_declarations(decl_str)
        for prop, value in declarations:
            if prop in COLOR_PROPERTIES:
                color_rules.append((selector, prop, value))

    return color_rules


class TestTokenUsage:
    """
    **Validates: Requirements 1.1, 1.4**

    Property 2: All component color references use design tokens —
    for any CSS rule setting color/background/border-color/box-shadow,
    the value must reference a var(--...) custom property rather than
    a hardcoded hex or rgba value.
    """

    def test_non_excepted_rules_exist(self, non_excepted_rules):
        """Sanity check: we should find color rules to test."""
        assert len(non_excepted_rules) > 0, (
            "No non-excepted CSS rules with color properties found. "
            "The CSS file may not have been parsed correctly."
        )

    @given(data=st.data())
    @settings(max_examples=100)
    def test_component_color_values_use_tokens(self, non_excepted_rules, data):
        """
        **Validates: Requirements 1.1, 1.4**

        For any CSS rule in app.css that sets a color-related property
        on a component selector (excluding allowed exceptions), the value
        must reference a var(--...) custom property rather than a hardcoded
        hex or rgba value.
        """
        rule = data.draw(st.sampled_from(non_excepted_rules))
        selector, prop, value = rule

        assert not has_hardcoded_color(value), (
            f"Hardcoded color found in '{selector}': "
            f"{prop}: {value} — should use a var(--...) design token"
        )

    def test_no_violations_comprehensive(self, css_content):
        """
        Comprehensive check: scan all rules and report all violations at once.
        This complements the property test by giving a full picture.
        """
        violations = collect_violating_rules(css_content)
        if violations:
            msg_lines = ["Found hardcoded color values that should use design tokens:"]
            for selector, prop, value in violations:
                msg_lines.append(f"  {selector} {{ {prop}: {value} }}")
            assert False, "\n".join(msg_lines)
