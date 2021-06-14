from discord.ext.commands import Cog
from discord import Embed, Color
from discord_slash import SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_option
from urllib.parse import urlparse

from typing import Optional, Dict, Any

from buttercup.bot import ButtercupBot
from blossom_wrapper import BlossomAPI, BlossomStatus

from buttercup.blossom_api.submission import try_get_submission_from_url


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
                description="A Reddit URL, either to the submission on ToR, the partner sub or the transcription.",
                option_type=3,
                required=True,
            )
        ],
    )
    async def _find(self, ctx: SlashContext, reddit_url: str) -> None:
        """Find the post with the given URL."""
        # Send a first message to show that the bot is responsive.
        # We will edit this message later with the actual content.
        msg = await ctx.send(f"Looking for post <{reddit_url}>...")

        submission = try_get_submission_from_url(self.blossom_api, reddit_url)

        if submission is None:
            await msg.edit(content=f"Sorry, I couldn't find a post with the URL <{reddit_url}>. "
                           "Please check that your link is correct, it should lead to either a post "
                           "on r/TranscribersOfReddit, a post on a partner sub or to a transcription.")
            return

        await msg.edit(content="I found the post!", embed=submission.to_embed())

        # Also get the volunteer who is working on the post
        submission.fetch_volunteer(self.blossom_api)
        await msg.edit(content="I found the post!", embed=submission.to_embed())

        # Also get the transcription content
        submission.fetch_transcriptions(self.blossom_api)
        await msg.edit(content="I found the post!", embed=submission.to_embed())


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
