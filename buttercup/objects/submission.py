from typing import Dict, Any, List, Optional
from datetime import datetime

from dateutil import parser
from discord import Color, Embed


class Submission:
    def __init__(self, submission_data: Dict[str, Any]):
        """
        Creates a new submission based on the submission data.
        """
        self._data = submission_data

    @property
    def id(self) -> int:
        """The ID of the submission."""
        return self._data["id"]

    @property
    def original_id(self) -> str:
        """The original submission ID on the source."""
        return self._data["original_id"]

    @property
    def create_time(self) -> datetime:
        """The time when the submission was created."""
        return parser.parse(self._data["create_time"])

    @property
    def last_update_time(self) -> datetime:
        """The last time the submission was updated."""
        return parser.parse(self._data["last_update_time"])

    @property
    def claimed_by(self) -> Optional[str]:
        """The user who claimed the submission."""
        return self._data["claimed_by"]

    @property
    def claim_time(self) -> Optional[datetime]:
        """The time when the submission was claimed."""
        return parser.parse(self._data["claim_time"]) if self._data["claim_time"] is not None else None

    @property
    def completed_by(self) -> Optional[str]:
        """The user who completed the submission."""
        return self._data["completed_by"]

    @property
    def complete_time(self) -> Optional[datetime]:
        """The time when the submission was completed."""
        return parser.parse(self._data["complete_time"]) if self._data["complete_time"] is not None else None

    @property
    def source(self) -> str:
        """The source of the submission."""
        return self._data["source"]

    @property
    def url(self) -> str:
        """The URL of the submission."""
        return self._data["url"]

    @property
    def tor_url(self) -> str:
        """The URL of the submission on ToR."""
        return self._data["tor_url"]

    @property
    def content_url(self) -> str:
        """The URL of the content of the submission, i.e. the media to transcribe."""
        return self._data["content_url"]

    @property
    def has_ocr_transcription(self) -> bool:
        """Whether the submission has an OCR transcription."""
        return self._data["has_ocr_transcription"]

    @property
    def transcription_set(self) -> List[str]:
        """The set of transcriptions for this submission."""
        return self._data["transcription_set"]

    @property
    def archived(self) -> bool:
        """Whether this transcription has been archived."""
        return self._data["archived"]

    @property
    def cannot_ocr(self) -> bool:
        """Whether the submission can not be processed by OCR."""
        return self._data["cannot_ocr"]

    @property
    def redis_id(self) -> Optional[str]:
        """The Redis ID of the submission."""
        return self._data["redis_id"]

    @property
    def subreddit(self) -> str:
        """The subreddit that the submission was posted to.

        The Blossom API doesn't provide this directly, so we need to get it from the URL instead.
        """
        return self.url.split("/")[4]

    def to_embed(self) -> Embed:
        """Converts the submission to a Discord embed."""
        status = "Unclaimed"
        color = Color.from_rgb(255, 176, 0)  # Orange
        if self.completed_by is not None:
            status = "Completed"
            color = Color.from_rgb(148, 224, 68)  # Green
        elif self.claimed_by is not None:
            status = "In Progress"
            color = Color.from_rgb(13, 211, 187)  # Cyan

        tor_post = f"[Link]({self.tor_url})"
        partner_post = f"[Link]({self.url})"

        return Embed(color=color) \
            .set_image(url=self.content_url) \
            .set_author(name=f"r/{self.subreddit}", url=f"https://reddit.com/r/{self.subreddit}") \
            .add_field(name="ToR Post", value=tor_post) \
            .add_field(name="Partner Post", value=partner_post) \
            .add_field(name="Status", value=status) \
            .add_field(name="Archived", value="Yes" if self.archived else "No") \
            .add_field(name="OCR", value="Yes" if self.has_ocr_transcription else "No")

    def __str__(self) -> str:
        return str(self._data)

    def __repr__(self) -> str:
        return f"Submission({str(self._data)})"
