from pytest import mark

from buttercup.cogs.helpers import extract_sub_name


@mark.parametrize(
    "sub_input,expected",
    [
        ("BoneAppleTea", "BoneAppleTea"),
        ("r/CuratedTumblr", "CuratedTumblr"),
        ("/r/me_irlgbt", "me_irlgbt"),
    ],
)
def test_extract_sub_name(sub_input: str, expected: str) -> None:
    """Test that the sub name is extracted correctly."""
    actual = extract_sub_name(sub_input)
    assert actual == expected
