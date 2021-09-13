import re
import time
from datetime import datetime

import pytz
from dateutil import parser
from typing import List, Optional, Union, Tuple

import discord
from blossom_wrapper import BlossomResponse
from discord import DiscordException
from requests import Response

username_regex = re.compile(r"^(?:/?u/)?(?P<username>\S+)")
timezone_regex = re.compile(r"UTC(?P<offset>[+-]\d+)?", re.RegexFlag.I)


class NoUsernameException(DiscordException):
    """Exception raised when the username was not provided."""

    pass


class BlossomException(RuntimeError):
    """Exception raised when a problem with the Blossom API occurred."""

    def __init__(self, response: Union[BlossomResponse, Response]) -> None:
        """Create a new Blossom API exception."""
        super().__init__()
        if isinstance(response, BlossomResponse):
            self.status = response.status.__str__()
            self.data = response.data
        else:
            self.status = response.status_code.__str__()
            self.data = response.json()


class TimeParseError(DiscordException):
    """Exception raised when a time string is invalid."""

    def __init__(self, time_str: str) -> None:
        """Create a new TimeParseError exception."""
        super().__init__()
        self.time_str = time_str


def extract_username(display_name: str) -> str:
    """Extract the Reddit username from the display name."""
    match = username_regex.search(display_name)
    if match is None:
        raise NoUsernameException()
    return match.group("username")


def get_usernames_from_user_list(
    user_list: Optional[str], author: Optional[discord.User], limit: int = 5
) -> List[str]:
    """Get the individual usernames from a list of users.

    :param user_list: The list of users, separated by spaces.
    :param author: The author of the message, taken as the default user.
    :param limit: The maximum number of users to handle.
    """
    raw_names = (
        [user.strip() for user in user_list.split(" ")] if user_list is not None else []
    )

    if len(raw_names) == 0:
        # No users provided, fall back to the author of the message
        if author is None:
            raise NoUsernameException()
        return [extract_username(author.display_name)]

    return [extract_username(user) for user in raw_names][:limit]


def extract_sub_name(subreddit: str) -> str:
    """Extract the name of the sub without prefix."""
    if subreddit.startswith("/r/"):
        return subreddit[3:]
    if subreddit.startswith("r/"):
        return subreddit[2:]
    return subreddit


def extract_utc_offset(display_name: str) -> int:
    """Extract the user's timezone (UTC offset) from the display name."""
    match = timezone_regex.search(display_name)
    if match is None or match.group("offset") is None:
        return 0
    return int(match.group("offset"))


def get_duration_str(start: datetime) -> str:
    """Get the processing duration based on the start time."""
    duration = datetime.now(tz=start.tzinfo) - start

    if duration.days >= 365:
        duration_years = duration.days / 365
        return f"{duration_years:.1f} years"
    if duration.days >= 7:
        duration_weeks = duration.days / 7
        return f"{duration_weeks:.1f} weeks"
    if duration.days >= 1:
        duration_days = duration.days + duration.seconds / 86400
        return f"{duration_days:.1f} days"
    if duration.seconds >= 3600:
        duration_hours = duration.seconds / 3600
        return f"{duration_hours:.1f} hours"
    if duration.seconds >= 60:
        duration_mins = duration.seconds / 60
        return f"{duration_mins:.1f} mins"
    if duration.seconds > 5:
        duration_secs = duration.seconds + duration.microseconds / 1000000
        return f"{duration_secs:.1f} secs"

    duration_ms = duration.seconds * 1000 + duration.microseconds / 1000
    return f"{duration_ms:0.0f} ms"


def get_progress_bar(
    count: int,
    total: int,
    width: int = 10,
    display_count: bool = False,
    as_code: bool = True,
) -> str:
    """Get a textual progress bar."""
    bar_count = round(count / total * width)
    inner_bar_count = min(bar_count, width)
    inner_space_count = width - inner_bar_count
    outer_bar_count = bar_count - inner_bar_count

    bar_str = (
        f"[{'#' * inner_bar_count}{' ' * inner_space_count}]{'#' * outer_bar_count}"
    )
    if as_code:
        bar_str = f"`{bar_str}`"
    count_str = f" ({count:,d}/{total:,d})" if display_count else ""

    return f"{bar_str}{count_str}"


def join_items_with_and(items: List[str]) -> str:
    """Join the list with commas and "and"."""
    if len(items) <= 2:
        return " and ".join(items)
    return "{} and {}".format(", ".join(items[:-1]), items[-1])


def get_discord_time_str(date_time: datetime, style: str = "f") -> str:
    """Get a Discord time string for the given datetime.

    Style should be one of the timestamp styles defined here:
    https://discord.com/developers/docs/reference#message-formatting-timestamp-styles
    """
    timestamp = time.mktime(date_time.timetuple())
    # https://discord.com/developers/docs/reference#message-formatting-formats
    return f"<t:{timestamp:0.0f}:{style}>"


def try_parse_time(time_str: str) -> Optional[datetime]:
    try:
        return parser.parse(time_str)
    except ValueError:
        raise TimeParseError(time_str)


def parse_time_constraints(
    after_str: Optional[str], before_str: Optional[str]
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """Parse user-given time constraints and convert them to datetimes."""
    after_time = None
    before_time = None

    if after_str is not None and after_str not in ["start", "none"]:
        after_time = try_parse_time(after_str)
    if before_str is not None and before_str not in ["end", "none"]:
        before_time = try_parse_time(before_str)

    return after_time, before_time
