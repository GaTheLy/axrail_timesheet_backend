"""Shared utilities for period handlers."""

from datetime import date, timedelta


def parse_date(date_str):
    return date.fromisoformat(date_str)


def validate_period_dates(start_date_str, end_date_str, submission_deadline_str):
    start_date = parse_date(start_date_str)
    end_date = parse_date(end_date_str)
    deadline_date = parse_date(submission_deadline_str[:10])

    if start_date.weekday() != 5:
        raise ValueError(
            f"startDate '{start_date_str}' is not a Saturday. "
            f"Got weekday {start_date.strftime('%A')}"
        )
    if end_date.weekday() != 4:
        raise ValueError(
            f"endDate '{end_date_str}' is not a Friday. "
            f"Got weekday {end_date.strftime('%A')}"
        )
    expected_end = start_date + timedelta(days=6)
    if end_date != expected_end:
        raise ValueError(
            f"endDate '{end_date_str}' must be exactly 6 days after "
            f"startDate '{start_date_str}'. Expected '{expected_end.isoformat()}'"
        )
    if deadline_date < end_date:
        raise ValueError(
            f"submissionDeadline '{submission_deadline_str}' must be on or after "
            f"endDate '{end_date_str}'"
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
