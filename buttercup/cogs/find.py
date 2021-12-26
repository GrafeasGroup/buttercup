from datetime import datetime
from typing import Dict, Optional, Tuple

from blossom_wrapper import BlossomAPI
from discord import Color, Embed
from discord.ext.commands import Cog
from discord_slash import SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_option

from buttercup.bot import ButtercupBot
from buttercup.cogs.helpers import get_duration_str
from buttercup.strings import translation

i18n = translation()


UNCLAIMED_COLOR = Color.from_rgb(255, 176, 0)  # Orange
IN_PROGRESS_COLOR = Color.from_rgb(13, 211, 187)  # Cyan
COMPLETED_COLOR = Color.from_rgb(148, 224, 68)  # Green


def limit_str(text: str, limit: Optional[int] = None) -> str:
    """Limit the string to the given length."""
    if limit is None or len(text) <= limit:
        return text

    return f"{text[:(limit - 3)]}..."


def get_clean_transcription(data: Dict) -> Optional[str]:
    """
    Get the content of the transcription, without header and footer.

    Because there can be an OCR transcription as well, then we'll
    try and return the human one but will fall through to the OCR
    one if we can't find any.
    """
    if tr_text := (data.get("transcription") or {}).get("text"):
        # Take the text of the transcription
        parts = tr_text.split("---")
        if len(parts) < 3:
            return tr_text

        # Discard header and footer
        return "---".join(parts[1:-1]).strip()
    elif ocr_text := (data.get("ocr") or {}).get("text"):
        # Take the text of the OCR
        return ocr_text

    return None


def get_color_and_status(data: Dict) -> Tuple[str, str]:
    """Get the color and status for the embed."""
    author = data.get("author", None)
    author_link = (
        i18n["reddit"]["user_named_link"].format(author["username"]) if author else None
    )

    if data["submission"].get("completed_by"):
        # The post has been completed
        status = f"Completed by {author_link}" if author_link else "Completed"
        return COMPLETED_COLOR, status
    elif data["submission"].get("claimed_by"):
        # The post is in progress
        status = f"Claimed by {author_link}" if author_link else "Claimed"

        return IN_PROGRESS_COLOR, status
    else:
        # The post is unclaimed
        return UNCLAIMED_COLOR, "Unclaimed"


def to_embed(data: Dict) -> Embed:
    """Convert the submission to a Discord embed."""
    color, status = get_color_and_status(data)

    embed = (
        Embed(color=color)
        .add_field(name="Status", value=status)
        .add_field(
            name="Archived",
            value="Yes" if (data.get("submission") or {}).get("archived") else "No",
        )
    )

    submission = data.get("submission") or {}

    # Add OCR status
    if ocr_url := (data.get("ocr") or {}).get("url"):
        ocr_status = f"[Link]({ocr_url})"
    elif submission.get("has_ocr_transcription"):
        ocr_status = "Yes"
    else:
        ocr_status = "No"

    embed.add_field(name="OCR", value=ocr_status)

    # Add transcription text
    if tr_text := get_clean_transcription(data):
        embed.description = limit_str(tr_text, 200)

    # Add image preview
    if content_url := submission.get("content_url"):
        if not submission.get("nsfw"):
            # There is no way to mark the image as spoiler
            # Instead we just don't add the image if it's NSFW
            embed.set_image(url=content_url)

    # Add link to ToR post
    if tor_url := submission.get("tor_url"):
        embed.add_field(name="ToR Post", value=f"[Link]({tor_url})")

    # Add link to partner post
    if sub_url := submission.get("url"):
        subreddit = sub_url.split("/")[4]
        embed.add_field(name="Partner Post", value=f"[Link]({sub_url})")
        embed.set_author(
            name=f"r/{subreddit}", url=i18n["reddit"]["subreddit_url"].format(subreddit)
        )

    # Add link to transcription
    if tr_url := (data.get("transcription") or {}).get("url"):
        tr_link = f"[Link]({tr_url})"
        embed.add_field(name="Transcription", value=tr_link)

    return embed


class Find(Cog):
    def __init__(self, bot: ButtercupBot, blossom_api: BlossomAPI) -> None:
        """Initialize the Find cog."""
        self.bot = bot
        self.blossom_api = blossom_api

    @cog_ext.cog_slash(
        name="find",
        description="Find a post given a Reddit URL.",
        options=[
            create_option(
                name="reddit_url",
                description="A Reddit URL, either to the submission on ToR, the "
                "partner sub or the transcription.",
                option_type=3,
                required=True,
            )
        ],
    )
    async def _find(self, ctx: SlashContext, reddit_url: str) -> None:
        """Find the post with the given URL."""
        start = datetime.now()

        # Send a first message to show that the bot is responsive.
        # We will edit this message later with the actual content.
        msg = await ctx.send(i18n["find"]["looking_for_posts"].format(url=reddit_url))

        find_response = self.blossom_api.get("find", params={"url": reddit_url})
        if not find_response.ok:
            await msg.edit(content=i18n["find"]["not_found"].format(url=reddit_url))
            return
        data = find_response.json()

        await msg.edit(
            content=i18n["find"]["embed_message"].format(
                duration=get_duration_str(start)
            ),
            embed=to_embed(data),
        )


def setup(bot: ButtercupBot) -> None:
    """Set up the Find cog."""
    cog_config = bot.config["Blossom"]
    email = cog_config.get("email")
    password = cog_config.get("password")
    api_key = cog_config.get("api_key")
    blossom_api = BlossomAPI(email=email, password=password, api_key=api_key)
    bot.add_cog(Find(bot=bot, blossom_api=blossom_api))


def teardown(bot: ButtercupBot) -> None:
    """Unload the Find cog."""
    bot.remove_cog("Find")
