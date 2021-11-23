from datetime import datetime

from pytest import mark

from buttercup.cogs.search import (
    SearchCache,
    get_transcription_source,
    get_transcription_type,
)


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
        (get_sample_transcription_from_header("*Image Transcription:*"), "Image",),
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


@mark.parametrize(
    "url,expected",
    [
        (
            "https://reddit.com/r/thatHappened/comments/qzhtyb/the_more_you_read_the_less_believable_it_gets/hlmkuau/",  # noqa: E501
            "r/thatHappened",
        ),
        (
            # noqa: E501
            "https://reddit.com/r/CasualUK/comments/qzhsco/found_this_bag_of_mints_on_the_floor_which_is/hlmjpoa/",  # noqa: E501
            "r/CasualUK",
        ),
    ],
)
def test_get_transcription_source(url: str, expected: str) -> None:
    """Verify that the transcription source is determined correctly."""
    tr_type = get_transcription_source({"url": url})
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
