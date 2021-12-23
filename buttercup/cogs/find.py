from datetime import datetime
from typing import Dict, Optional

from blossom_wrapper import BlossomAPI
from discord import Color, Embed
from discord.ext.commands import Cog
from discord_slash import SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_option

from buttercup.bot import ButtercupBot
from buttercup.cogs.helpers import get_duration_str
from buttercup.strings import translation

i18n = translation()


def get_id_from_url(grafeas_url: str) -> int:
    """Extract the API from a Grafeas URL."""
    return int(grafeas_url.split("/")[-2])


def limit_str(text: str, limit: Optional[int] = None) -> str:
    """Limit the string to the given length."""
    if limit is None or len(text) <= limit:
        return text

    return f"{text[:(limit - 3)]}..."


def get_clean_transcription(data: Dict) -> str:
    """
    Get the content of the transcription, without header and footer.

    Because there can be an OCR transcription as well, then we'll
    try and return the human one but will fall through to the OCR
    one if we can't find any.
    """
    key = "transcription" if "transcription" in data else "ocr"
    transcription_text = data[key]["text"]

    if get_id_from_url(data[key]["author"]) == 3:
        # The author is transcribot and doesn't use our format
        return transcription_text

    parts = transcription_text.split("---")
    if len(parts) < 3:
        return transcription_text

    # Discard header and footer
    return "---".join(parts[1:-1]).strip()


class Find(Cog):
    def __init__(self, bot: ButtercupBot, blossom_api: BlossomAPI) -> None:
        """Initialize the Find cog."""
        self.bot = bot
        self.blossom_api = blossom_api

    def to_embed(self, data: Dict) -> Embed:  # noqa: C901
        """Convert the submission to a Discord embed."""
        color = Color.from_rgb(255, 176, 0)  # Orange
        status: str = "Unclaimed"

        if "transcription" in data:
            tr_link = f"[Link]({data['transcription']['url']})"
        else:
            tr_link = None

        if data["submission"].get("completed_by"):
            color = Color.from_rgb(148, 224, 68)  # Green

            if "author" in data:
                status = "Completed by {}".format(
                    i18n["find"]["discord_username_link"].format(
                        data["author"]["username"]
                    )
                )
            else:
                status = "Completed"
        elif data["submission"].get("claimed_by"):
            color = Color.from_rgb(13, 211, 187)  # Cyan

            if "author" in data:
                status = "Claimed by {}".format(
                    i18n["find"]["discord_username_link"].format(
                        data["author"]["username"]
                    )
                )
            else:
                status = "Claimed"

        embed = (
            Embed(color=color)
            .add_field(name="Status", value=status)
            .add_field(
                name="OCR",
                value="Yes"
                if data["submission"].get("has_ocr_transcription")
                else "No",
            )
            .add_field(
                name="Archived",
                value="Yes" if data["submission"].get("archived") else "No",
            )
        )

        if "transcription" in data or "ocr" in data:
            embed.description = limit_str(get_clean_transcription(data), 200)
        if data["submission"].get("content_url"):
            embed.set_image(url=data["submission"]["content_url"])
        if data["submission"].get("tor_url"):
            embed.add_field(
                name="ToR Post", value=f"[Link]({data['submission']['tor_url']})"
            )
        if data["submission"].get("url"):
            embed.add_field(
                name="Partner Post", value=f"[Link]({data['submission']['url']})"
            )
        if tr_link:
            embed.add_field(name="Transcription", value=tr_link)
        if subreddit := (
            data["submission"]["url"].split("/")[4]
            if "url" in data["submission"]
            else None
        ):
            embed.set_author(
                name=f"r/{subreddit}", url=f"https://reddit.com/r/{subreddit}"
            )

        return embed

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
            embed=self.to_embed(data),
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
