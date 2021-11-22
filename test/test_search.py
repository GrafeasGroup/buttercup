from pytest import mark

from buttercup.cogs.search import get_transcription_type, get_transcription_source


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
    tr_type = get_transcription_type({"text": transcription})
    assert tr_type == expected


@mark.parametrize(
    "transcription,expected",
    [
        (
            "https://reddit.com/r/thatHappened/comments/qzhtyb/the_more_you_read_the_less_believable_it_gets/hlmkuau/",
            "r/thatHappened",
        ),
        (
            "https://reddit.com/r/CasualUK/comments/qzhsco/found_this_bag_of_mints_on_the_floor_which_is/hlmjpoa/",
            "r/CasualUK"
        )
    ],
)
def test_get_transcription_source(transcription: str, expected: str) -> None:
    tr_type = get_transcription_source({"text": transcription})
    assert tr_type == expected
