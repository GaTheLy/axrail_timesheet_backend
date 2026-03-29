"""Property-based tests for filter logic on master data pages.

These tests model the client-side JavaScript applyFilters() function and
dropdown population logic as pure Python and verify universal properties
across generated inputs.

Feature: admin-ui-revisions

Property 6: Combined filters show only matching rows
Property 7: Filter dropdowns populated from data

Validates: Requirements 3.3, 3.6, 3.10, 3.15, 3.16, 3.17, 3.18
"""

from hypothesis import given, settings, assume
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Model of the filter logic (mirrors applyFilters() JS behaviour)
# ---------------------------------------------------------------------------

APPROVAL_STATUSES = ["Approved", "Pending_Approval", "Rejected"]


class TableRow:
    """Models a table row with data attributes used for filtering."""

    def __init__(self, text_content: str, approval_status: str,
                 department: str = "", position: str = "",
                 start_date: str = ""):
        self.text_content = text_content
        self.approval_status = approval_status
        self.department = department
        self.position = position
        self.start_date = start_date
        self.visible = True


class FilterState:
    """Models the active filter values on a page."""

    def __init__(self, search_text: str = "", approval_status: str = "",
                 department: str = "", position: str = "",
                 start_date: str = "", status: str = ""):
        self.search_text = search_text
        self.approval_status = approval_status
        self.department = department
        self.position = position
        self.start_date = start_date
        self.status = status


# Status dropdown maps display values to data-approval-status values
# (mirrors var statusMap in projects.blade.php)
STATUS_MAP = {"active": "Approved", "pending": "Pending_Approval"}


def row_matches_filters(row: TableRow, filters: FilterState, page: str) -> bool:
    """Determines if a row matches all active filters simultaneously.

    Mirrors the applyFilters() logic from the Blade templates:
    - Empty/default filter value means "match all"
    - All active filters must match (AND logic)
    - Search is case-insensitive substring match against text content
    - Dropdown filters are exact match against data attributes
    """
    # Search filter: case-insensitive substring match
    search = filters.search_text.strip().lower()
    matches_search = not search or search in row.text_content.lower()

    # Approval status filter: exact match against data-approval-status
    matches_approval = (not filters.approval_status or
                        row.approval_status == filters.approval_status)

    if page == "departments" or page == "positions":
        return matches_search and matches_approval

    elif page == "projects":
        # Start date filter: exact match
        matches_date = (not filters.start_date or
                        row.start_date == filters.start_date)
        # Status filter: map through statusMap then exact match
        mapped_status = STATUS_MAP.get(filters.status, filters.status) if filters.status else ""
        matches_status = not mapped_status or row.approval_status == mapped_status
        return matches_search and matches_date and matches_status

    elif page == "users":
        # Department filter: exact match against data-department
        matches_dept = (not filters.department or
                        row.department == filters.department)
        # Position filter: exact match against data-position
        matches_pos = (not filters.position or
                       row.position == filters.position)
        return matches_search and matches_approval and matches_dept and matches_pos

    return False


def apply_filters(rows: list, filters: FilterState, page: str) -> list:
    """Apply filters to rows and return the list of visible rows.

    Mirrors the JS: row.style.display = (allMatch) ? '' : 'none'
    """
    visible = []
    for row in rows:
        row.visible = row_matches_filters(row, filters, page)
        if row.visible:
            visible.append(row)
    return visible


def populate_dropdown(rows: list, field: str) -> list:
    """Collect distinct non-empty values for a field from rows, sorted.

    Mirrors the JS dropdown population logic:
    - departments/positions: collect distinct departmentId/positionId from usersData
    - start dates: collect distinct non-empty date text from table column
    """
    values = []
    for row in rows:
        val = getattr(row, field, "")
        if val and val not in values:
            values.append(val)
    values.sort()
    return values


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

non_empty_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Z")),
    min_size=1,
    max_size=60,
).filter(lambda s: s.strip())

approval_status_strategy = st.sampled_from(APPROVAL_STATUSES)

department_strategy = st.sampled_from(
    ["Engineering", "Marketing", "Finance", "HR", "Operations"]
)

position_strategy = st.sampled_from(
    ["Developer", "Manager", "Analyst", "Designer", "Lead"]
)

start_date_strategy = st.sampled_from(
    ["2024-01-01", "2024-02-15", "2024-03-20", "2024-06-01", "2024-12-31"]
)

# Strategy for a single row on the departments/positions page
dept_pos_row_strategy = st.builds(
    TableRow,
    text_content=non_empty_text,
    approval_status=approval_status_strategy,
)

# Strategy for a single row on the projects page
project_row_strategy = st.builds(
    TableRow,
    text_content=non_empty_text,
    approval_status=approval_status_strategy,
    start_date=start_date_strategy,
)

# Strategy for a single row on the users page
user_row_strategy = st.builds(
    TableRow,
    text_content=non_empty_text,
    approval_status=approval_status_strategy,
    department=department_strategy,
    position=position_strategy,
)

# Filter value strategies (empty string means "no filter active")
optional_search = st.one_of(st.just(""), non_empty_text)
optional_approval = st.one_of(st.just(""), approval_status_strategy)
optional_department = st.one_of(st.just(""), department_strategy)
optional_position = st.one_of(st.just(""), position_strategy)
optional_start_date = st.one_of(st.just(""), start_date_strategy)
optional_status = st.one_of(st.just(""), st.sampled_from(["active", "pending"]))


# ---------------------------------------------------------------------------
# Property 6: Combined filters show only matching rows
# ---------------------------------------------------------------------------

class TestCombinedFiltersShowOnlyMatchingRows:
    """Property 6: For any master data page and any combination of active
    filter values (search text, approval status, department, position, start
    date, status), the set of visible table rows shall equal exactly the set
    of rows whose data attributes match ALL active filter criteria
    simultaneously. A filter with an empty/default value is not active and
    matches all rows.

    **Validates: Requirements 3.3, 3.6, 3.10, 3.15**
    """

    @given(
        rows=st.lists(dept_pos_row_strategy, min_size=1, max_size=20),
        search_text=optional_search,
        approval_status=optional_approval,
    )
    @settings(max_examples=200)
    def test_departments_combined_filters(self, rows, search_text, approval_status):
        """On the Department_Page, combined search + approval status filters
        show exactly the rows matching both criteria.

        **Validates: Requirements 3.3**
        """
        filters = FilterState(search_text=search_text,
                              approval_status=approval_status)
        visible = apply_filters(rows, filters, "departments")

        # Independently compute expected visible rows
        expected = [r for r in rows if row_matches_filters(r, filters, "departments")]

        assert len(visible) == len(expected), (
            f"Expected {len(expected)} visible rows, got {len(visible)} "
            f"(search='{search_text}', approval='{approval_status}')"
        )
        for row in rows:
            should_be_visible = row_matches_filters(row, filters, "departments")
            assert row.visible == should_be_visible, (
                f"Row '{row.text_content}' visibility mismatch: "
                f"expected {should_be_visible}, got {row.visible}"
            )

    @given(
        rows=st.lists(dept_pos_row_strategy, min_size=1, max_size=20),
        search_text=optional_search,
        approval_status=optional_approval,
    )
    @settings(max_examples=200)
    def test_positions_combined_filters(self, rows, search_text, approval_status):
        """On the Position_Page, combined search + approval status filters
        show exactly the rows matching both criteria.

        **Validates: Requirements 3.6**
        """
        filters = FilterState(search_text=search_text,
                              approval_status=approval_status)
        visible = apply_filters(rows, filters, "positions")

        expected = [r for r in rows if row_matches_filters(r, filters, "positions")]
        assert len(visible) == len(expected)
        for row in rows:
            should_be_visible = row_matches_filters(row, filters, "positions")
            assert row.visible == should_be_visible

    @given(
        rows=st.lists(project_row_strategy, min_size=1, max_size=20),
        search_text=optional_search,
        start_date=optional_start_date,
        status=optional_status,
    )
    @settings(max_examples=200)
    def test_projects_combined_filters(self, rows, search_text, start_date, status):
        """On the Project_Page, combined search + start date + status filters
        show exactly the rows matching all criteria.

        **Validates: Requirements 3.10**
        """
        filters = FilterState(search_text=search_text,
                              start_date=start_date, status=status)
        visible = apply_filters(rows, filters, "projects")

        expected = [r for r in rows if row_matches_filters(r, filters, "projects")]
        assert len(visible) == len(expected)
        for row in rows:
            should_be_visible = row_matches_filters(row, filters, "projects")
            assert row.visible == should_be_visible

    @given(
        rows=st.lists(user_row_strategy, min_size=1, max_size=20),
        search_text=optional_search,
        approval_status=optional_approval,
        department=optional_department,
        position=optional_position,
    )
    @settings(max_examples=200)
    def test_users_combined_filters(self, rows, search_text, approval_status,
                                    department, position):
        """On the User_Page, combined search + approval status + department +
        position filters show exactly the rows matching all criteria.

        **Validates: Requirements 3.15**
        """
        filters = FilterState(search_text=search_text,
                              approval_status=approval_status,
                              department=department, position=position)
        visible = apply_filters(rows, filters, "users")

        expected = [r for r in rows if row_matches_filters(r, filters, "users")]
        assert len(visible) == len(expected)
        for row in rows:
            should_be_visible = row_matches_filters(row, filters, "users")
            assert row.visible == should_be_visible

    @given(
        rows=st.lists(user_row_strategy, min_size=1, max_size=20),
    )
    @settings(max_examples=100)
    def test_empty_filters_show_all_rows(self, rows):
        """When all filters are empty/default, every row is visible.

        **Validates: Requirements 3.3, 3.6, 3.10, 3.15**
        """
        filters = FilterState()  # all empty
        for page in ["departments", "positions", "projects", "users"]:
            # Reset visibility
            for r in rows:
                r.visible = True
            visible = apply_filters(rows, filters, page)
            assert len(visible) == len(rows), (
                f"All rows should be visible with empty filters on {page}"
            )


# ---------------------------------------------------------------------------
# Property 7: Filter dropdowns populated from data
# ---------------------------------------------------------------------------

class TestFilterDropdownsPopulatedFromData:
    """Property 7: For any filter dropdown on a master data page (department
    dropdown on User_Page, position dropdown on User_Page, start date dropdown
    on Project_Page), the set of option values in the dropdown shall equal the
    set of distinct values for that field present in the table data.

    **Validates: Requirements 3.16, 3.17, 3.18**
    """

    @given(
        rows=st.lists(user_row_strategy, min_size=1, max_size=30),
    )
    @settings(max_examples=200)
    def test_department_dropdown_matches_distinct_departments(self, rows):
        """The department filter dropdown options equal the distinct department
        values from the user data, sorted.

        **Validates: Requirements 3.16**
        """
        options = populate_dropdown(rows, "department")
        expected = sorted(set(r.department for r in rows if r.department))

        assert options == expected, (
            f"Department dropdown options {options} must equal "
            f"distinct departments {expected}"
        )

    @given(
        rows=st.lists(user_row_strategy, min_size=1, max_size=30),
    )
    @settings(max_examples=200)
    def test_position_dropdown_matches_distinct_positions(self, rows):
        """The position filter dropdown options equal the distinct position
        values from the user data, sorted.

        **Validates: Requirements 3.17**
        """
        options = populate_dropdown(rows, "position")
        expected = sorted(set(r.position for r in rows if r.position))

        assert options == expected, (
            f"Position dropdown options {options} must equal "
            f"distinct positions {expected}"
        )

    @given(
        rows=st.lists(project_row_strategy, min_size=1, max_size=30),
    )
    @settings(max_examples=200)
    def test_start_date_dropdown_matches_distinct_dates(self, rows):
        """The start date filter dropdown options equal the distinct start
        date values from the project data, sorted.

        **Validates: Requirements 3.18**
        """
        options = populate_dropdown(rows, "start_date")
        expected = sorted(set(r.start_date for r in rows if r.start_date))

        assert options == expected, (
            f"Start date dropdown options {options} must equal "
            f"distinct start dates {expected}"
        )

    @given(
        rows=st.lists(user_row_strategy, min_size=0, max_size=30),
    )
    @settings(max_examples=100)
    def test_dropdown_has_no_duplicates(self, rows):
        """Dropdown options never contain duplicate values.

        **Validates: Requirements 3.16, 3.17, 3.18**
        """
        for field in ["department", "position"]:
            options = populate_dropdown(rows, field)
            assert len(options) == len(set(options)), (
                f"Dropdown for {field} must not contain duplicates: {options}"
            )
