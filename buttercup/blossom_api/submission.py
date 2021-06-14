from typing import Dict, Any, List, Optional
from datetime import datetime
from urllib.parse import urlparse

from blossom_wrapper import BlossomAPI, BlossomStatus
from dateutil import parser
from discord import Color, Embed

from buttercup.blossom_api.helpers import try_get_first
from buttercup.blossom_api.volunteer import Volunteer


class Submission:
    def __init__(self, submission_data: Dict[str, Any]):
        """
        Creates a new submission based on the submission data.
        """
        self._data = submission_data
        self._volunteer = None

    def __str__(self) -> str:
        return str(self._data)

    def __repr__(self) -> str:
        return f"Submission({str(self._data)})"

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


def try_get_submission(blossom_api: BlossomAPI, **kwargs: Any) -> Optional[Submission]:
    """Tries to get the submission with the given arguments."""
    data = try_get_first(blossom_api.get_submission(kwargs=kwargs))

    if data is None:
        return None

    return Submission(data)


def try_get_submission_from_url(blossom_api: BlossomAPI, reddit_url_str: str) -> Optional[Submission]:
    """Tries to get the submission correspoding to the given Reddit URL.

    The URL can be a link to either a post on the partner sub or r/ToR, or it can be a transcription link.
    """
    parse_result = urlparse(reddit_url_str)

    if "reddit" not in parse_result.netloc:
        return None

    # On Blossom, all URLs end with a slash
    path = parse_result.path

    if not path.endswith("/"):
        path += "/"

    # Normalizes the URL to the format Blossom uses.
    # This is necessary because the link could be to Old Reddit, for example.
    normalized_url = f"https://reddit.com{path}"

    # Determine what kind of link we're dealing with:
    if "/r/TranscribersOfReddit" in path:
        # It's a link to the ToR submission
        return try_get_submission(tor_url=normalized_url)
    elif len(path.split("/")) >= 8:
        # It's a comment on a partner sub, i.e. a transcription
        # This means that the path is longer, because of the added comment ID
        tr_response = blossom_api.get_transcription(url=normalized_url)
        tr_data = tr_response.data

        if tr_response.status != BlossomStatus.ok or tr_data is None or len(tr_data) == 0:
            return None
        else:
            transcription = tr_data[0]
            # We don't have direct access to the submission ID, so we need to extract it from the submission URL
            submission_url = transcription["submission"]
            submission_id = submission_url.split("/")[-2]
            return try_get_submission(id=submission_id)
    else:
        # It's a link to the submission on a partner sub
        return try_get_submission(url=normalized_url)


