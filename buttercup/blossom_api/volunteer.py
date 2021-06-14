from datetime import datetime
from typing import Any, Dict, Optional

from blossom_wrapper import BlossomAPI, BlossomResponse
from dateutil import parser

from buttercup.blossom_api.helpers import try_get_first


class Volunteer:
    def __init__(self, volunteer_data: Dict[str, Any]) -> None:
        """Create a new volunteer based on the volunteer data."""
        self._data = volunteer_data

    @property
    def id(self) -> int:
        """Get the ID of the volunteer."""
        return self._data["id"]

    @property
    def username(self) -> str:
        """Get the username of the volunteer."""
        return self._data["username"]

    @property
    def gamma(self) -> int:
        """Get the gamma score (transcription count) of the volunteer."""
        return self._data["gamma"]

    @property
    def date_joined(self) -> datetime:
        """Get the date when the volunteer joined Grafeas."""
        return parser.parse(self._data["date_joined"])

    @property
    def last_login(self) -> datetime:
        """Get the last time the volunteer logged in."""
        return parser.parse(self._data["last_login"])

    @property
    def last_update_time(self) -> datetime:
        """Get the last time the volunteer was updated."""
        return parser.parse(self._data["last_update_time"])

    @property
    def accepted_coc(self) -> bool:
        """Determine whether the volunteer has accepted the Code of Conduct."""
        return self._data["accepted_coc"]

    @property
    def blacklisted(self) -> bool:
        """Determine whether the volunteer is blacklisted from all of our systems.

        When this is true, the bot should not respond to their commands,
        but still to commands of others asking for data about
        this volunteer.
        """
        return self._data["accepted_coc"]

    @property
    def formatted_link(self) -> str:
        """Get a link in the Discord format pointing to the volunteer on Reddit."""
        return f"[{self.username}](https://reddit.com/u/{self.username})"


def try_get_volunteer(blossom_api: BlossomAPI, **kwargs: Any) -> Optional[Volunteer]:
    """Try to get the volunteer with the given arguments."""
    response = blossom_api.get("volunteer/", params=kwargs)
    response.raise_for_status()
    results = response.json()["results"]
    if not results:
        return None

    data = try_get_first(BlossomResponse(data=results))

    if data is None:
        return None

    return Volunteer(data)
