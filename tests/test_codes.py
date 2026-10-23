from datetime import datetime, timezone

import pytest

from giftcode_finder.codes import parse_vn_time

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "text, expected",
    [
        # Vietnamese sites: no zone means Vietnam time, a bare date the whole day.
        ("2027-04-23 11:44:00", "2027-04-23T04:44:00Z"),
        ("23/04/2027", "2027-04-23T16:59:59Z"),
        ("23h59 31/12/2026", "2026-12-31T16:59:00Z"),
        ("2027-04-23T04:45:00Z", "2027-04-23T04:45:00Z"),
        # Kuro Games writes Pacific time, which follows daylight saving.
        ("2026-09-21 08:59 (PT)", "2026-09-21T15:59:00Z"),
        ("2026-01-25 07:59 PT", "2026-01-25T15:59:00Z"),
        ("2026/09/21 23:59 (UTC+8)", "2026-09-21T15:59:00Z"),
        ("October 13, 2026 (08:59 AM UTC-7)", "2026-10-13T15:59:00Z"),
        ("21 September 2026, 08:59 (GMT+8)", "2026-09-21T00:59:00Z"),
        ("Sept. 21, 2026 at 9 a.m. PT", "2026-09-21T16:00:00Z"),
        ("9 PM ET on December 1, 2026", "2026-12-02T02:00:00Z"),
        ("13 October 2026", "2026-10-13T16:59:59Z"),
        ("<t:1790006340:F>", "2026-09-21T15:59:00Z"),
        ("hôm nay", None),
    ],
)
def test_parse_vn_time(text, expected):
    assert parse_vn_time(text, NOW) == expected


def test_date_without_year_is_the_nearest_one():
    assert parse_vn_time("September 21", NOW) == "2026-09-21T16:59:59Z"
    assert parse_vn_time("December 30", datetime(2027, 1, 2, tzinfo=timezone.utc)) == "2026-12-30T16:59:59Z"
