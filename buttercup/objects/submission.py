from typing import Dict, Any, List, Optional
from datetime import datetime

from dateutil import parser


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
