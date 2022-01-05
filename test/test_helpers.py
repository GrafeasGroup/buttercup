from datetime import datetime, timedelta
from typing import List, Optional

import pytz
from pytest import mark

from buttercup.cogs.helpers import (
    BlossomUser,
    escape_formatting,
    extract_sub_name,
    extract_username,
    extract_utc_offset,
    format_absolute_datetime,
    format_relative_datetime,
    get_progress_bar,
    get_username,
    join_items_with_and,
    parse_time_constraints,
    try_parse_time,
    username_regex, utc_offset_to_str,
)


@mark.parametrize(
    "input_str,prefix,leading_slash,username,rest",
    [
        ("user", None, False, "user", ""),
        ("u/user", "u/", False, "user", ""),
        ("/u/user", "/u/", True, "user", ""),
        ("/u/user-name_with123stuff", "/u/", True, "user-name_with123stuff", ""),
        ("/u/user [mod] UTC-3 ~40⭐", "/u/", True, "user", " [mod] UTC-3 ~40⭐"),
    ],
)
def test_username_regex(
    input_str: str, prefix: str, leading_slash: bool, username: str, rest: str
) -> None:
    """Test that the user name is extracted correctly."""
    match = username_regex.match(input_str)
    assert match is not None

    assert match.group("prefix") == prefix
    assert match.group("leading_slash") == ("/" if leading_slash else None)
    assert match.group("username") == username
    assert match.group("rest") == rest


@mark.parametrize(
    "user_input,expected",
    [
        ("u/user", "user"),
        ("/u/user", "user"),
        ("/u/user-name", "user-name"),
        ("/u/user_name", "user_name"),
        ("/u/user12345", "user12345"),
        ("/u/user-name_12345 UTC-5", "user-name_12345"),
    ],
)
def test_extract_username(user_input: str, expected: str) -> None:
    """Test that the user name is extracted correctly."""
    actual = extract_username(user_input)
    assert actual == expected


@mark.parametrize(
    "sub_input,expected",
    [
        ("BoneAppleTea", "BoneAppleTea"),
        ("r/CuratedTumblr", "CuratedTumblr"),
        ("/r/me_irlgbt", "me_irlgbt"),
    ],
)
def test_extract_sub_name(sub_input: str, expected: str) -> None:
    """Test that the sub name is extracted correctly."""
    actual = extract_sub_name(sub_input)
    assert actual == expected


def test_get_username_none() -> None:
    """Test that the username of a None object is returned correctly."""
    actual = get_username(None)
    assert actual == "everyone"


def test_get_username_object() -> None:
    """Test that the username of a None object is returned correctly."""
    user: BlossomUser = {
        "id": 1314,
        "username": "abc",
        "gamma": 110,
        "date_joined": "2021-12-12T16:06Z",
    }
    actual = get_username(user)
    assert actual == "u/abc"


@mark.parametrize(
    "username,expected",
    [
        ("user", r"user"),
        ("_Diabetes", r"\_Diabetes"),
        ("test*test*test", r"test\*test\*test"),
        ("**bold**", r"\*\*bold\*\*"),
        ("**bold**", r"\*\*bold\*\*"),
        ("__BlAzEsUpErBlAzE__", r"\_\_BlAzEsUpErBlAzE\_\_"),
    ],
)
def test_escape_formatting(username: str, expected: str) -> None:
    """Test that Discord formatting is escaped properly."""
    actual = escape_formatting(username)
    assert actual == expected


@mark.parametrize(
    "name_input,expected",
    [
        ("username", 0),
        ("u/username", 0),
        ("/u/username [mod] ~20⭐", 0),
        ("/u/username UTC", 0),
        ("/u/UTC+10", 0),
        ("/u/username UTC+2", 7_200),
        ("/u/username UTC-5", -18_000),
        ("/u/username utc+4", 14400),
        ("/u/username [mod] UTC+1 - 14⭐", 3600),
        ("/u/username UTC+02:00", 7_200),
        ("/u/username UTC+10.5", 37_800),
        ("/u/username UTC+10:30", 37_800),
    ],
)
def test_extract_utc_offset(name_input: str, expected: int) -> None:
    """Test that the UTC offset is extracted correctly."""
    actual = extract_utc_offset(name_input)
    assert actual == expected


@mark.parametrize(
    "utc_offset,expected",
    [
        (0, "UTC+00:00"),
        (7_200, "UTC+02:00"),
        (-18_000, "UTC-05:00"),
        (14_400, "UTC+04:00"),
        (3_600, "UTC+01:00"),
        (37_800, "UTC+10:30")
    ],
)
def test_utc_offset_to_str(utc_offset: int, expected: str) -> None:
    """Test that the UTC offset is extracted correctly."""
    actual = utc_offset_to_str(utc_offset)
    assert actual == expected


@mark.parametrize(
    "count,total,width,display_count,as_code,expected",
    [
        (0, 10, 10, False, False, "[          ]"),
        (2, 10, 10, False, False, "[##        ]"),
        (4, 10, 10, False, False, "[####      ]"),
        (10, 10, 10, False, False, "[##########]"),
        (1, 30, 10, False, False, "[          ]"),
        (2, 30, 10, False, False, "[#         ]"),
        (4, 10, 10, True, False, "[####      ] (4/10)"),
        (4, 10, 10, False, True, "`[####      ]`"),
        (4, 10, 10, True, True, "`[####      ]` (4/10)"),
    ],
)
def test_get_progress_bar(
    count: int,
    total: int,
    width: int,
    display_count: bool,
    as_code: bool,
    expected: str,
) -> None:
    """Test that the progress bar is generated correctly."""
    actual = get_progress_bar(count, total, width, display_count, as_code)
    assert actual == expected


@mark.parametrize(
    "items,expected",
    [
        ([], ""),
        (["one"], "one"),
        (["one", "two"], "one and two"),
        (["one", "two", "three"], "one, two and three"),
        (["one", "two", "three", "four"], "one, two, three and four"),
    ],
)
def test_join_items_with_and(items: List[str], expected: str) -> None:
    """Test that the items are joined together correctly."""
    actual = join_items_with_and(items)
    assert actual == expected


now = datetime.now()


@mark.parametrize(
    "date,expected",
    [
        (datetime(2020, 5, 10, 13, 50, 2, 300), "2020-05-10 13:50:02"),
        (datetime(2020, 5, 10, 13, 50), "2020-05-10 13:50"),
        (datetime(2020, 5, 10), "2020-05-10"),
        (datetime(2020, 5, 10), "2020-05-10"),
        (datetime(now.year, now.month, now.day, 13, 50, 2, 300), "13:50:02"),
        (datetime(now.year, now.month, now.day, 13, 50), "13:50"),
    ],
)
def test_format_absolute_datetime(date: datetime, expected: str) -> None:
    """Test that absolute date times are formatted correctly."""
    actual = format_absolute_datetime(date)
    assert actual == expected


@mark.parametrize(
    "amount,unit_key,expected",
    [
        (3.7, "hours", "3.7 hours ago"),
        (3.0, "hours", "3 hours ago"),
        (1, "hours", "1 hour ago"),
        (2, "weeks", "2 weeks ago"),
        (5.31234, "years", "5.31234 years ago"),
    ],
)
def test_format_relative_datetime(amount: float, unit_key: str, expected: str) -> None:
    """Test that relative date times are formatted correctly."""
    actual = format_relative_datetime(amount, unit_key)
    assert actual == expected


@mark.parametrize(
    "input_str,expected_datetime,expected_str",
    [
        (
            "2020-03-04 10:13",
            datetime(2020, 3, 4, 10, 13, tzinfo=pytz.utc),
            "2020-03-04 10:13",
        ),
        (
            "2020-03-04T10:13",
            datetime(2020, 3, 4, 10, 13, tzinfo=pytz.utc),
            "2020-03-04 10:13",
        ),
        ("2020-03-04", datetime(2020, 3, 4, tzinfo=pytz.utc), "2020-03-04"),
        (
            "10:13",
            datetime(now.year, now.month, now.day, 10, 13, tzinfo=pytz.utc),
            "10:13",
        ),
    ],
)
def test_parse_absolute_datetime(
    input_str: str, expected_datetime: datetime, expected_str: str
) -> None:
    """Test that absolute date times are formatted correctly."""
    actual_datetime, actual_str = try_parse_time(input_str)
    assert actual_datetime == expected_datetime
    assert actual_str == expected_str


@mark.parametrize(
    "input_str,expected_timedelta,expected_str",
    [
        ("3", timedelta(hours=3), "3 hours ago"),
        ("3.2", timedelta(hours=3.2), "3.2 hours ago"),
        ("3.0 hours", timedelta(hours=3), "3 hours ago"),
        ("2.1 years", timedelta(days=766.5), "2.1 years ago"),
        ("1 minute", timedelta(minutes=1), "1 minute ago"),
        ("2 weeks ago", timedelta(weeks=2), "2 weeks ago"),
        ("2 months ago", timedelta(days=60), "2 months ago"),
    ],
)
def test_parse_relative_datetime(
    input_str: str, expected_timedelta: timedelta, expected_str: str
) -> None:
    """Test that absolute date times are formatted correctly."""
    start = datetime.now(tz=pytz.utc)
    expected_datetime = start - expected_timedelta
    actual_datetime, actual_str = try_parse_time(input_str)
    duration = datetime.now(tz=pytz.utc) - start
    epsilon = abs(actual_datetime - expected_datetime)
    # We can't check for equality because the result depends on the current time
    # Instead we assert that the difference is small enough, considering execution time
    assert duration >= epsilon
    assert actual_str == expected_str


@mark.parametrize(
    "after_str,before_str,expected_after,expected_before, expected_str",
    [
        (None, None, None, None, "from the start until now"),
        ("none", "none", None, None, "from the start until now"),
        ("start", "end", None, None, "from the start until now"),
        (
            "2020-01-08",
            None,
            datetime(2020, 1, 8, tzinfo=pytz.utc),
            None,
            "from 2020-01-08 until now",
        ),
        (
            "2020-01-08",
            "2021-09-13T13:20",
            datetime(2020, 1, 8, tzinfo=pytz.utc),
            datetime(2021, 9, 13, 13, 20, tzinfo=pytz.utc),
            "from 2020-01-08 until 2021-09-13 13:20",
        ),
    ],
)
def test_parse_absolute_time_constraints(
    after_str: Optional[str],
    before_str: Optional[str],
    expected_after: Optional[datetime],
    expected_before: Optional[datetime],
    expected_str: str,
) -> None:
    """Test that absolute time constraints are parsed correctly."""
    actual_after, actual_before, actual_str = parse_time_constraints(
        after_str, before_str
    )
    assert actual_after == expected_after
    assert actual_before == expected_before
    assert actual_str == expected_str


@mark.parametrize(
    "after_str,before_str,expected_after_delta,expected_before_delta, expected_str",
    [
        ("3", None, timedelta(hours=3), None, "from 3 hours ago until now"),
        ("3.0", None, timedelta(hours=3), None, "from 3 hours ago until now"),
        ("3.2 hours", None, timedelta(hours=3.2), None, "from 3.2 hours ago until now"),
        (
            "1.5 y",
            "1 week",
            timedelta(days=547.5),
            timedelta(weeks=1),
            "from 1.5 years ago until 1 week ago",
        ),
        (
            "30 min",
            "2 secs",
            timedelta(minutes=30),
            timedelta(seconds=2),
            "from 30 minutes ago until 2 seconds ago",
        ),
    ],
)
def test_parse_relative_time_constraints(
    after_str: Optional[str],
    before_str: Optional[str],
    expected_after_delta: Optional[timedelta],
    expected_before_delta: Optional[timedelta],
    expected_str: Optional[datetime],
) -> None:
    """Test that relative time constraints are parsed correctly."""
    start = datetime.now(tz=pytz.utc)
    expected_after = (
        start - expected_after_delta if expected_after_delta is not None else None
    )
    expected_before = (
        start - expected_before_delta if expected_before_delta is not None else None
    )
    actual_after, actual_before, actual_str = parse_time_constraints(
        after_str, before_str
    )
    duration = datetime.now(tz=pytz.utc) - start

    # We can't check for equality because the result depends on the current time
    # Instead we assert that the difference is small enough, considering execution time
    if expected_after is not None:
        after_epsilon = abs(actual_after - expected_after)
        assert duration >= after_epsilon
    else:
        assert actual_after is None
    if expected_before is not None:
        before_epsilon = abs(actual_before - expected_before)
        assert duration >= before_epsilon
    else:
        assert actual_before is None

    assert actual_str == expected_str
