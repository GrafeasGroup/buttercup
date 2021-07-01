import re
from datetime import datetime

from discord import DiscordException

username_regex = re.compile(r"^/?u/(?P<username>\S+)")
timezone_regex = re.compile(r"UTC(?P<offset>[+-]\d+)?", re.RegexFlag.I)


class NoUsernameError(DiscordException):
    """Exception raised when the username was not provided."""

    pass


def extract_username(display_name: str) -> str:
    """Extract the Reddit username from the display name."""
    match = username_regex.search(display_name)
    if match is None:
        raise NoUsernameError()
    return match.group("username")


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
    duration = datetime.now() - start
    if duration.seconds > 5:
        return f"{duration.seconds} s"

    duration_ms = duration.seconds * 1000 + duration.microseconds // 1000
    return f"{duration_ms} ms"
