from datetime import datetime

from pytest import mark

from src.cogs.search import SearchCache, get_transcription_type


def get_sample_transcription_from_header(header: str) -> str:
    """Generate a sample transcription from a header."""
    return (
        header
        + """

---

Bla bla bla

---

Footer"""
    )


@mark.parametrize(
    "transcription,expected",
    [
        (
            get_sample_transcription_from_header("*Image Transcription:*"),
            "Image",
        ),
        (get_sample_transcription_from_header("*Image Transcription*"), "Image"),
        (get_sample_transcription_from_header("*Image Transcription: GIF*"), "GIF"),
        (
            get_sample_transcription_from_header("*Image Transcription: Tumblr*"),
            "Tumblr",
        ),
        (get_sample_transcription_from_header("*Video Transcription:*"), "Video"),
        (get_sample_transcription_from_header("aspdpiaosfipasof"), "Post"),
    ],
)
def test_get_transcription_type(transcription: str, expected: str) -> None:
    """Verify that the transcription type is determined correctly."""
    tr_type = get_transcription_type({"text": transcription})
    assert tr_type == expected


class TestSearchCache:
    def test_search_cache_clean(self) -> None:
        """Verify that the cache is cleaned when the capacity is exceeded."""
        cache = SearchCache(1)
        cache.set(
            "abc",
            {
                "query": "aaa",
                "cur_page": 0,
                "response_data": None,
                "request_page": 0,
                "discord_user_id": "user",
            },
            datetime(2021, 1, 3),
        )
        cache.set(
            "def",
            {
                "query": "ddd",
                "cur_page": 0,
                "response_data": None,
                "request_page": 0,
                "discord_user_id": "user",
            },
            datetime(2021, 1, 4),
        )

        assert cache.get("abc") is None
        assert cache.get("def")["query"] == "ddd"
