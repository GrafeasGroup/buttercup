import re
from datetime import datetime

from discord import DiscordException


class NoUsernameError(DiscordException):
    """Exception raised when the username was not provided."""

    pass


def extract_username(display_name: str) -> str:
    """Extract the Reddit username from the display name."""
    pattern = re.compile(r"^/?u/(?P<username>\S+)")
    match = pattern.search(display_name)
    if match is None:
        raise NoUsernameError()
    return match.group("username")


def extract_utc_offset(display_name: str) -> int:
    """Extract the user's timezone (UTC offset) from the display name."""
    pattern = re.compile(r"UTC(?P<offset>[+-]\d+)?", re.RegexFlag.I)
    match = pattern.search(display_name)
    if match is None or match.group("offset") is None:
        return 0
    return int(match.group("offset"))


def get_duration_str(start: datetime) -> str:
    """Get the processing duration based on the start time."""
    duration = datetime.now() - start
    duration_ms = duration.microseconds / 1000
    return f"{duration_ms:0.0f} ms"
