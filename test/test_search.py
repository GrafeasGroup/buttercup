from pytest import mark

from buttercup.cogs.search import get_transcription_type


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
