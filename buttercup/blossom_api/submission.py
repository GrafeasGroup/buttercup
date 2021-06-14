from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from blossom_wrapper import BlossomAPI
from dateutil import parser
from discord import Color, Embed

from buttercup.blossom_api.helpers import (
    get_id_from_url,
    limit_str,
    try_get_first,
)
from buttercup.blossom_api.transcription import Transcription, try_get_transcriptions
from buttercup.blossom_api.volunteer import Volunteer, try_get_volunteer


class Submission:
    def __init__(self, submission_data: Dict[str, Any]) -> None:
        """Create a new submission based on the submission data."""
        self._data = submission_data
        self._volunteer = None
        self._transcriptions = None

    def __str__(self) -> str:
        return str(self._data)

    def __repr__(self) -> str:
        return f"Submission({str(self._data)})"

    @property
    def id(self) -> int:
        """Get the ID of the submission."""
        return self._data["id"]

    @property
    def original_id(self) -> str:
        """Get the original submission ID on the source."""
        return self._data["original_id"]

    @property
    def create_time(self) -> datetime:
        """Get the time when the submission was created."""
        return parser.parse(self._data["create_time"])

    @property
    def last_update_time(self) -> datetime:
        """Get the last time the submission was updated."""
        return parser.parse(self._data["last_update_time"])

    @property
    def claimed_by(self) -> Optional[str]:
        """Get the user who claimed the submission."""
        return self._data["claimed_by"]

    @property
    def claim_time(self) -> Optional[datetime]:
        """Get the time when the submission was claimed."""
        return (
            parser.parse(self._data["claim_time"])
            if self._data["claim_time"] is not None
            else None
        )

    @property
    def completed_by(self) -> Optional[str]:
        """Get the user who completed the submission."""
        return self._data["completed_by"]

    @property
    def complete_time(self) -> Optional[datetime]:
        """Get the time when the submission was completed."""
        return (
            parser.parse(self._data["complete_time"])
            if self._data["complete_time"] is not None
            else None
        )

    @property
    def source(self) -> str:
        """Get the source of the submission."""
        return self._data["source"]

    @property
    def url(self) -> Optional[str]:
        """Get the URL of the submission."""
        return self._data["url"]

    @property
    def tor_url(self) -> Optional[str]:
        """Get the URL of the submission on ToR."""
        return self._data["tor_url"]

    @property
    def content_url(self) -> Optional[str]:
        """Get the URL of the content of the submission, i.e. the media to transcribe."""
        return self._data["content_url"]

    @property
    def has_ocr_transcription(self) -> bool:
        """Determine whether the submission has an OCR transcription."""
        return self._data["has_ocr_transcription"]

    @property
    def transcription_set(self) -> List[str]:
        """Get the set of transcriptions for this submission."""
        return self._data["transcription_set"]

    @property
    def archived(self) -> bool:
        """Determine whether this transcription has been archived."""
        return self._data["archived"]

    @property
    def cannot_ocr(self) -> bool:
        """Determine whether the submission can not be processed by OCR."""
        return self._data["cannot_ocr"]

    @property
    def redis_id(self) -> Optional[str]:
        """Get the Redis ID of the submission."""
        return self._data["redis_id"]

    @property
    def subreddit(self) -> Optional[str]:
        """Get the subreddit that the submission was posted to.

        The Blossom API doesn't provide this directly, so we need to get it
        from the URL instead.
        """
        return self.url.split("/")[4] if self.url is not None else None

    @property
    def volunteer(self) -> Optional[Volunteer]:
        """Get the volunteer working on this submission."""
        return self._volunteer

    def fetch_volunteer(self, blossom_api: BlossomAPI) -> Optional[Volunteer]:
        """Retrieve the volunteer working on this submission from Blossom."""
        if self._volunteer is not None:
            return self._volunteer

        if self.completed_by is not None:
            volunteer_id = get_id_from_url(self.completed_by)
            volunteer = try_get_volunteer(blossom_api, id=volunteer_id)
            self._volunteer = volunteer
            return volunteer

        if self.claimed_by is not None:
            volunteer_id = get_id_from_url(self.claimed_by)
            volunteer = try_get_volunteer(blossom_api, id=volunteer_id)
            self._volunteer = volunteer
            return volunteer

        return None

    @property
    def transcriptions(self) -> Optional[List[Transcription]]:
        """Get the transcriptions for this post."""
        return self._transcriptions

    def fetch_transcriptions(
        self, blossom_api: BlossomAPI
    ) -> Optional[List[Transcription]]:
        """Retrieve the transcriptions for this submission from Blossom."""
        if self._transcriptions is not None:
            return self._transcriptions

        transcriptions = try_get_transcriptions(blossom_api, submission=self.id)
        self._transcriptions = transcriptions
        return transcriptions

    @property
    def main_transcription(self) -> Optional[Transcription]:
        """Get the main transcription that completed the submission."""
        if self.transcriptions is None or len(self.transcriptions) == 0:
            return None

        if self.completed_by is not None:
            # Try find the user transcription
            # Kinda ugly, but Python doesn't seem to have a List.find function
            user_transcription = next(
                iter(
                    [
                        tr
                        for tr in self.transcriptions
                        if tr.author_link == self.completed_by
                    ]
                ),
                None,
            )
            if user_transcription is not None:
                return user_transcription

        # Use the last one as fallback, probably OCR
        return self.transcriptions[-1]

    def to_embed(self) -> Embed:
        """Convert the submission to a Discord embed."""
        color = Color.from_rgb(255, 176, 0)  # Orange
        status = "Unclaimed"

        main_tr = self.main_transcription
        tr_link = f"[Link]({main_tr.url})" if main_tr is not None else None

        if self.completed_by is not None:
            color = Color.from_rgb(148, 224, 68)  # Green

            if self.volunteer is not None:
                status = f"Completed by {self.volunteer.formatted_link}"
            else:
                status = "Completed"
        elif self.claimed_by is not None:
            color = Color.from_rgb(13, 211, 187)  # Cyan

            if self.volunteer is not None:
                status = f"Claimed by {self.volunteer.formatted_link}"
            else:
                status = "Claimed"

        embed = (
            Embed(color=color)
            .add_field(name="Status", value=status)
            .add_field(name="OCR", value="Yes" if self.has_ocr_transcription else "No")
            .add_field(name="Archived", value="Yes" if self.archived else "No")
        )

        if main_tr is not None:
            embed.description = limit_str(main_tr.content, 200)
        if self.content_url is not None:
            embed.set_image(url=self.content_url)
        if self.tor_url is not None:
            tor_post = f"[Link]({self.tor_url})"
            embed.add_field(name="ToR Post", value=tor_post)
        if self.url is not None:
            partner_post = f"[Link]({self.url})"
            embed.add_field(name="Partner Post", value=partner_post)
        if tr_link is not None:
            embed.add_field(name="Transcription", value=tr_link)
        if self.subreddit is not None:
            embed.set_author(
                name=f"r/{self.subreddit}", url=f"https://reddit.com/r/{self.subreddit}"
            )

        return embed


def try_get_submission(blossom_api: BlossomAPI, **kwargs: Any) -> Optional[Submission]:
    """Try to get the submission with the given arguments."""
    data = try_get_first(blossom_api.get_submission(**kwargs))

    if data is None:
        return None

    return Submission(data)


def try_get_submission_from_url(
    blossom_api: BlossomAPI, reddit_url_str: str
) -> Optional[Submission]:
    """Try to get the submission corresponding to the given Reddit URL.

    The URL can be a link to either a post on the partner sub or r/ToR, or it can be a
    transcription link.
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
        return try_get_submission(blossom_api, tor_url=normalized_url)
    elif len(path.split("/")) >= 8:
        # It's a comment on a partner sub, i.e. a transcription
        # This means that the path is longer, because of the added comment ID
        tr_response = blossom_api.get_transcription(url=normalized_url)
        tr_data = try_get_first(tr_response)

        if tr_data is None:
            return None

        # We don't have direct access to the submission ID, so we need to extract it
        # from the submission URL
        submission_url = tr_data["submission"]
        submission_id = get_id_from_url(submission_url)
        return try_get_submission(blossom_api, id=submission_id)
    else:
        # It's a link to the submission on a partner sub
        return try_get_submission(blossom_api, url=normalized_url)
