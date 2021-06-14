import logging
from typing import Dict, Optional, Union
from urllib.parse import urlparse

from blossom_wrapper import BlossomAPI, BlossomStatus
from discord import Color, Embed
from discord.ext.commands import Cog
from discord_slash import SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_option

from buttercup.bot import ButtercupBot

PLEASE_CHECK_URL = (
    " Please check that your link is correct, it should lead to"
    " either a post on r/TranscribersOfReddit, a post on a partner"
    " sub or to a transcription."
)
DISCORD_USERNAME_LINK = "[{0}](https://reddit.com/u/{0})"


def normalize_url(reddit_url_str: str) -> Union[str, None]:
    """
    Normalize a Reddit URL to the format that Blossom uses.

    This is necessary because the link could be to Old Reddit, for example.
    """
    parse_result = urlparse(reddit_url_str)
    if "reddit" not in parse_result.netloc:
        return None

    # On Blossom, all URLs end with a slash
    path = parse_result.path

    if not path.endswith("/"):
        path += "/"

    return f"https://reddit.com{path}"


def get_id_from_url(grafeas_url: str) -> int:
    """Extract the API from a Grafeas URL."""
    return int(grafeas_url.split("/")[-2])


def limit_str(text: str, limit: Optional[int] = None) -> str:
    """Limit the string to the given length."""
    if limit is None or len(text) <= limit:
        return text

    return f"{text[:(limit - 3)]}..."


class Find(Cog):
    def __init__(self, bot: ButtercupBot, blossom_api: BlossomAPI) -> None:
        """Initialize the Find cog."""
        self.bot = bot
        self.blossom_api = blossom_api

    def to_embed(self) -> Embed:  # noqa: C901
        """Convert the submission to a Discord embed."""
        color = Color.from_rgb(255, 176, 0)  # Orange
        status: str = "Unclaimed"

        tr_link = f"[Link]({self.transcription['url']})" if self.transcription else None

        if self.submission["completed_by"]:
            color = Color.from_rgb(148, 224, 68)  # Green

            if self.author:
                status = "Completed by {}".format(
                    DISCORD_USERNAME_LINK.format(self.author["username"])
                )
            else:
                status = "Completed"
        elif self.submission["claimed_by"]:
            color = Color.from_rgb(13, 211, 187)  # Cyan

            if self.author:
                status = "Claimed by {}".format(
                    DISCORD_USERNAME_LINK.format(self.author["username"])
                )
            else:
                status = "Claimed"

        embed = (
            Embed(color=color)
            .add_field(name="Status", value=status)
            .add_field(
                name="OCR",
                value="Yes" if self.submission["has_ocr_transcription"] else "No",
            )
            .add_field(
                name="Archived", value="Yes" if self.submission["archived"] else "No"
            )
        )

        if self.transcription:
            embed.description = limit_str(self.transcription["text"], 200)
        if self.submission.get("content_url"):
            embed.set_image(url=self.submission["content_url"])
        if self.submission.get("tor_url"):
            embed.add_field(
                name="ToR Post", value=f"[Link]({self.submission['tor_url']})"
            )
        if self.submission.get("url"):
            embed.add_field(
                name="Partner Post", value=f"[Link]({self.submission.get('url')})"
            )
        if tr_link:
            embed.add_field(name="Transcription", value=tr_link)
        subreddit = (
            self.submission["url"].split("/")[4] if self.submission["url"] else None
        )
        if subreddit:
            embed.set_author(
                name=f"r/{subreddit}", url=f"https://reddit.com/r/{subreddit}"
            )

        return embed

    def _clear(self) -> None:
        """Reset the local scope caches for a new search."""
        self.transcription: Union[Dict, None] = None
        self.submission: Union[Dict, None] = None
        self.author: Union[Dict, None] = None

    def get_transcription(self) -> None:
        """Get the target transcription from Blossom."""
        for option in self.submission["transcription_set"]:
            response = self.blossom_api.get_transcription(id=get_id_from_url(option))
            logging.info(response.data[0])
            if response.data[0]["author"] == self.submission["completed_by"]:
                self.transcription = response.data[0]
                return

    def get_author(self) -> None:
        """Retrieve the author from the submission or the transcription."""
        if self.transcription:
            source_url = self.transcription["author"]
        else:
            source_url = self.submission["claimed_by"]
        self.author = self.blossom_api.get(
            "volunteer/", params={"id": get_id_from_url(source_url)}
        ).json()["results"][0]

    def get_submission_from_url(self, reddit_url: str) -> Union[Dict, None]:
        """
        Try to get the submission corresponding to the given Reddit URL.

        The URL can be a link to either a post on the partner sub, a post
        on r/ToR, or it can be a transcription link.
        """
        # Determine what kind of link we're dealing with:
        logging.critical(len(reddit_url.split("/")))
        if len(reddit_url.split("/")) <= 9:
            # It's a link to a submission, either on ToR or a partner
            urltype = "tor_url" if "TranscribersOfReddit" in reddit_url else "url"
            result = self.blossom_api.get_submission(**{urltype: reddit_url})
        else:
            # It's a comment on a partner sub, i.e. a transcription
            # This means that the path is longer, because of the added comment ID
            tr_response = self.blossom_api.get_transcription(url=reddit_url)
            if tr_response.status == BlossomStatus.not_found:
                return None
            self.transcription = tr_response.data[0]

            # We don't have direct access to the submission ID, so we need to
            # extract it from the submission URL
            submission_id = get_id_from_url(self.transcription["submission"])
            result = self.blossom_api.get_submission(id=submission_id)

        logging.critical(result.data[0] if result.status == BlossomStatus.ok else None)
        self.submission = result.data[0] if result.status == BlossomStatus.ok else None

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
        self._clear()
        if (reddit_url := normalize_url(reddit_url)) is None:
            await ctx.send(
                "Sorry, that doesn't look like a URL I can work with."
                + PLEASE_CHECK_URL
            )
            return

        # Send a first message to show that the bot is responsive.
        # We will edit this message later with the actual content.
        msg = await ctx.send(f"Looking for post <{reddit_url}>...")

        self.get_submission_from_url(reddit_url)
        if self.submission is None:
            await msg.edit(
                content=(
                    f"Sorry, I couldn't find a post with the URL <{reddit_url}>."
                    + PLEASE_CHECK_URL
                )
            )
            return

        await msg.edit(content="I found the post!", embed=self.to_embed())

        # If we started with a transcription link, this will be set already.
        if not self.transcription:
            self.get_transcription()

        await msg.edit(content="I found the post!", embed=self.to_embed())

        if self.transcription or self.submission["claimed_by"]:
            self.get_author()

        await msg.edit(content="I found the post!", embed=self.to_embed())


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
