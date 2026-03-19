"""Shared utilities for period handlers."""

from datetime import date, datetime, timedelta, timezone


# Malaysian Time is UTC+8
MYT_OFFSET_HOURS = 8
# Deadline: Friday 5PM MYT = Friday 09:00 UTC
DEADLINE_HOUR_UTC = 9
DEADLINE_MINUTE_UTC = 0


def parse_date(date_str):
    return date.fromisoformat(date_str)


def compute_submission_deadline(end_date_str):
    """Compute the submission deadline: endDate (Friday) at 5PM MYT (09:00 UTC).

    Args:
        end_date_str: The end date string in YYYY-MM-DD format (must be a Friday).

    Returns:
        ISO 8601 datetime string for the deadline.
    """
    end_date = parse_date(end_date_str)
    deadline = datetime(
        end_date.year, end_date.month, end_date.day,
        DEADLINE_HOUR_UTC, DEADLINE_MINUTE_UTC, 0,
        tzinfo=timezone.utc,
    )
    return deadline.isoformat()


def validate_period_dates(start_date_str, end_date_str):
    """Validate period dates: startDate must be Monday, endDate must be Friday,
    endDate must be exactly 4 days after startDate.

    Args:
        start_date_str: Start date in YYYY-MM-DD format.
        end_date_str: End date in YYYY-MM-DD format.

    Raises:
        ValueError: If any validation fails.
    """
    start_date = parse_date(start_date_str)
    end_date = parse_date(end_date_str)

    if start_date.weekday() != 0:
        raise ValueError(
            f"startDate '{start_date_str}' is not a Monday. "
            f"Got weekday {start_date.strftime('%A')}"
        )
    if end_date.weekday() != 4:
        raise ValueError(
            f"endDate '{end_date_str}' is not a Friday. "
            f"Got weekday {end_date.strftime('%A')}"
        )
    expected_end = start_date + timedelta(days=4)
    if end_date != expected_end:
        raise ValueError(
            f"endDate '{end_date_str}' must be exactly 4 days after "
            f"startDate '{start_date_str}'. Expected '{expected_end.isoformat()}'"
        )


def check_no_overlapping_periods(table, start_date_str, end_date_str, exclude_period_id=None):
    new_start = parse_date(start_date_str)
    new_end = parse_date(end_date_str)

    response = table.scan()
    items = response.get("Items", [])
    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response.get("Items", []))

    for item in items:
        if exclude_period_id and item["periodId"] == exclude_period_id:
            continue
        existing_start = parse_date(item["startDate"])
        existing_end = parse_date(item["endDate"])
        if new_start <= existing_end and new_end >= existing_start:
            raise ValueError(
                f"Period overlaps with existing period "
                f"'{item.get('periodString', item['periodId'])}' "
                f"({item['startDate']} to {item['endDate']})"
            )
