from typing import Optional
import re

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
