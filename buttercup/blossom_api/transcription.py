from datetime import datetime
from typing import Any, Dict, List, Optional

from blossom_wrapper import BlossomAPI
from dateutil import parser

from buttercup.blossom_api.helpers import get_url_from_id, try_get_all


class Transcription:
    def __init__(self, transcription_data: Dict[str, Any]) -> None:
        """Create a new transcription based on the transcription data."""
        self._data = transcription_data
        self._volunteer = None

    def __str__(self) -> str:
        return str(self._data)

    def __repr__(self) -> str:
        return f"Transcription({str(self._data)})"

    @property
    def id(self) -> int:
        """Get the transcription ID."""
        return self._data["id"]

    @property
    def submission_link(self) -> str:
        """Get the link to the submission that the transcription belongs to."""
        return self._data["submission"]

    @property
    def author_link(self) -> str:
        """Get the link to the author of the transcription."""
        return self._data["author"]

    @property
    def create_time(self) -> datetime:
        """Get the time when the transcription was created."""
        return parser.parse(self._data["create_time"])

    @property
    def last_update_time(self) -> datetime:
        """Get the last time the transcription was updated."""
        return parser.parse(self._data["last_update_time"])

    @property
    def original_id(self) -> str:
        """Get the original transcription ID on the source."""
        return self._data["original_id"]

    @property
    def source(self) -> str:
        """Get the source of the transcription."""
        return self._data["source"]

    @property
    def url(self) -> Optional[str]:
        """Get the URL of the transcription."""
        return self._data["url"]

    @property
    def text(self) -> str:
        """Get the full text of the transcription."""
        return self._data["text"]

    @property
    def content(self) -> str:
        """Get the content of the transcription, without header and footer."""
        if self.author_link == get_url_from_id("volunteer", 3):
            # The author is the OCR bot and doesn't use our format
            return self.text

        parts = self.text.split("---")
        if len(parts) < 3:
            return self.text

        # Discard header and footer
        return "---".join(parts[1:-1]).strip()

    @property
    def removed_from_reddit(self) -> bool:
        """Determine whether the transcription has been caught by the spam filters."""
        return self._data["removed_from_reddit"]


def try_get_transcriptions(
    blossom_api: BlossomAPI, **kwargs: Any
) -> Optional[List[Transcription]]:
    """Try to get the transcriptions with the given arguments."""
    data = try_get_all(blossom_api.get_transcription(**kwargs))

    if data is None:
        return None

    return [Transcription(tr_data) for tr_data in data]
