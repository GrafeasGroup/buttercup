from typing import List

from pytest import mark

from buttercup.cogs.helpers import (
    extract_sub_name,
    extract_username,
    extract_utc_offset,
    get_progress_bar,
)


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


@mark.parametrize(
    "name_input,expected",
    [
        ("username", 0),
        ("u/username", 0),
        ("/u/username [mod] ~20⭐", 0),
        ("/u/username UTC", 0),
        ("/u/username UTC+2", 2),
        ("/u/username UTC-5", -5),
        ("/u/username utc+4", 4),
        ("/u/username [mod] UTC+1 - 14⭐", 1),
    ],
)
def test_extract_utc_offset(name_input: str, expected: int) -> None:
    """Test that the UTC offset is extracted correctly."""
    actual = extract_utc_offset(name_input)
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
    """Test that the progress bar is generated correctly"""
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
    pass
