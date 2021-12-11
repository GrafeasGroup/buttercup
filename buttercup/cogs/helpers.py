import re
from datetime import datetime, timedelta
from time import mktime
from typing import Any, Dict, List, Optional, Tuple, Union, TypedDict

import pytz
from blossom_wrapper import BlossomResponse, BlossomAPI, BlossomStatus
from dateutil import parser
from discord import DiscordException, User
from discord_slash import SlashContext
from requests import Response

from buttercup.cogs import ranks

username_regex = re.compile(r"^(?:/?u/)?(?P<username>\S+)")
timezone_regex = re.compile(r"UTC(?P<offset>[+-]\d+)?", re.RegexFlag.I)

# First an amount and then a unit
relative_time_regex = re.compile(
    r"^(?P<amount>\d+(?:\.\d+)?)\s*(?P<unit>\w*)\s*(?:ago\s*)?$"
)
# The different time units
unit_regexes: Dict[str, re.Pattern] = {
    "seconds": re.compile(r"^s(?:ec(?:ond)?s?)?$"),
    "minutes": re.compile(r"^min(?:ute)?s?$"),
    # Hour is the default, so the whole thing is optional
    "hours": re.compile(r"^(?:h(?:ours?)?)?$"),
    "days": re.compile(r"^d(?:ays?)?$"),
    "weeks": re.compile(r"^w(?:eeks?)?$"),
    "months": re.compile(r"^m(?:onths?)?$"),
    "years": re.compile(r"^y(?:ears?)?$"),
}


class BlossomUser(TypedDict):
    id: int
    username: str
    gamma: int
    date_joined: str


class UserNotFoundException(DiscordException):
    """Exception raised when the given user could not be found."""

    def __init__(self, username: str) -> None:
        """Create a new user not found exception."""
        super().__init__()
        self.username = username


class NoUsernameException(DiscordException):
    """Exception raised when the username was not provided."""

    pass


class InvalidArgumentException(DiscordException):
    """Exception raised when an argument has an invalid value."""

    def __init__(self, argument: str, value: str) -> None:
        """Create a new argument exception."""
        super().__init__()
        self.argument = argument
        self.value = value


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


class TimeParseError(RuntimeError):
    """Exception raised when a time string is invalid."""

    def __init__(self, time_str: str) -> None:
        """Create a new TimeParseError exception."""
        super().__init__()
        self.message = f"Invalid time string: '{time_str}'"
        self.time_str = time_str


def extract_username(display_name: str) -> str:
    """Extract the Reddit username from the display name."""
    match = username_regex.search(display_name)
    if match is None:
        raise NoUsernameException()
    return match.group("username")


def get_usernames_from_user_list(
    user_list: Optional[str], author: Optional[User], limit: int = 5
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


def get_initial_username(username: str, ctx: SlashContext) -> str:
    """Get the initial, unverified username.

    This does not make any API requests yet, so it can be used for the first message.

    Special keywords:
    - "me": Returns the user executing the command (from the SlashContext).
    - "all"/"everyone"/"everybody": Returns "everyone".
    """
    if username.casefold() in ["all", "everyone", "everybody"]:
        # Handle command execution for everyone
        return "everyone"

    _username = ctx.author.display_name if username.casefold() == "me" else username
    return "u/" + extract_username(_username)


def get_user(username: str, ctx: SlashContext, blossom_api: BlossomAPI) -> Optional[BlossomUser]:
    """Get the given user from Blossom.

    Special keywords:
    - "me": Returns the user executing the command (from the SlashContext).
    - "all"/"everyone"/"everybody": Returns None, should return stats for all users if possible.

    If the user could not be found, a UserNotFoundException is thrown and handled automatically.
    """
    if username.casefold() in ["all", "everyone", "everybody"]:
        # Handle command execution for everyone
        return None

    # Handle command execution for the current user
    _username = ctx.author.display_name if username.casefold() == "me" else username
    _username = extract_username(_username)

    user_response = blossom_api.get_user(_username)

    if user_response.status != BlossomStatus.ok:
        raise UserNotFoundException(_username)

    return user_response.data


def get_username(user: Optional[BlossomUser]) -> str:
    """Get the name of the given user.

    None is interpreted as all users.
    """
    return "u/" + user["username"] if user else "everyone"


def get_user_id(user: Optional[BlossomUser]) -> Optional[int]:
    """Get the ID of the given user.

    None is interpreted as all users and will also return None.
    """
    return user["id"] if user else None


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
    return get_timedelta_str(duration)


def get_timedelta_str(duration: timedelta) -> str:
    """Format the given timedelta."""
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
    timestamp = mktime(date_time.timetuple())
    # https://discord.com/developers/docs/reference#message-formatting-formats
    return f"<t:{timestamp:0.0f}:{style}>"


def format_absolute_datetime(date_time: datetime) -> str:
    """Generate a human-readable absolute time string."""
    now = datetime.now(tz=pytz.utc)
    format_str = ""
    if date_time.date() != now.date():
        format_str += "%Y-%m-%d"

        time_part = date_time.time()
        # Only add the relevant time parts
        if time_part.hour != 0 or time_part.minute != 0 or time_part.second != 0:
            if time_part.second != 0:
                format_str += " %H:%M:%S"
            else:
                format_str += " %H:%M"
    else:
        time_part = date_time.time()
        # Only add the relevant time parts
        if time_part.second != 0:
            format_str = "%H:%M:%S"
        else:
            format_str = "%H:%M"

    return date_time.strftime(format_str)


def format_relative_datetime(amount: float, unit_key: str) -> str:
    """Generate a human-readable relative time string."""
    # Only show relevant decimal places https://stackoverflow.com/a/51227501
    amount_str = f"{amount:f}".rstrip("0").rstrip(".")
    # Only show the plural s if needed
    unit_str = unit_key if amount != 1.0 else unit_key[:-1]
    return f"{amount_str} {unit_str} ago"


def try_parse_time(time_str: str) -> Tuple[datetime, str]:
    """Try to parse the given time string.

    Handles absolute times like '2021-09-14' and relative times like '2 hours ago'.
    If the string cannot be parsed, a TimeParseError is raised.
    """
    # Check for relative time
    # For example "2.4 years"
    rel_time_match = relative_time_regex.match(time_str)
    if rel_time_match is not None:
        # Extract amount and unit
        amount = float(rel_time_match.group("amount"))
        unit = rel_time_match.group("unit")
        # Determine which unit we are dealing with
        for unit_key in unit_regexes:
            match = unit_regexes[unit_key].match(unit)
            if match is not None:
                # Construct the time delta from the unit and amount
                if unit_key == "months":
                    delta = timedelta(days=30 * amount)
                elif unit_key == "years":
                    delta = timedelta(days=365 * amount)
                else:
                    delta = timedelta(**{unit_key: amount})

                absolute_time = datetime.now(tz=pytz.utc) - delta
                relative_time_str = format_relative_datetime(amount, unit_key)

                return absolute_time, relative_time_str

    # Check for absolute time
    # For example "2021-09-03"
    try:
        absolute_time = parser.parse(time_str)
        # Make sure it has a timezone
        absolute_time = absolute_time.replace(tzinfo=absolute_time.tzinfo or pytz.utc)
        absolute_time_str = format_absolute_datetime(absolute_time)
        return absolute_time, absolute_time_str
    except ValueError:
        raise TimeParseError(time_str)


def parse_time_constraints(
    after_str: Optional[str], before_str: Optional[str]
) -> Tuple[Optional[datetime], Optional[datetime], str]:
    """Parse user-given time constraints and convert them to datetimes."""
    after_time = None
    before_time = None
    after_time_str = "the start"
    before_time_str = "now"

    if after_str is not None and after_str not in ["start", "none"]:
        after_time, after_time_str = try_parse_time(after_str)
    if before_str is not None and before_str not in ["end", "none"]:
        before_time, before_time_str = try_parse_time(before_str)

    time_str = f"from {after_time_str} until {before_time_str}"

    return after_time, before_time, time_str


def get_rank(gamma: int) -> Dict[str, Union[str, int]]:
    """Get the rank matching the gamma score."""
    for rank in reversed(ranks):
        if gamma >= rank["threshold"]:
            return rank

    return {"name": "Visitor", "threshold": 0, "color": "#000000"}


def get_rgb_from_hex(hex_str: str) -> Tuple[int, int, int]:
    """Get the rgb values from a hex string."""
    # Adopted from
    # https://stackoverflow.com/questions/29643352/converting-hex-to-rgb-value-in-python
    hx = hex_str.lstrip("#")
    return int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)
