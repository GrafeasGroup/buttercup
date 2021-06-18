from datetime import datetime

import praw
from discord import Color, Embed
from discord.ext.commands import Cog
from discord_slash import SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_option

from buttercup.bot import ButtercupBot


class Rules(Cog):
    def __init__(self, bot: ButtercupBot, reddit_api: praw.Reddit) -> None:
        """Initialize the Rules cog."""
        self.bot = bot
        self.reddit_api = reddit_api

    @cog_ext.cog_slash(
        name="rules", description="Get the rules of the specified subreddit.",
        options=[
            create_option(
                name="subreddit",
                description="The subreddit to get the rules of.",
                option_type=3,
                required=True,
            )
        ],
    )
    async def _rules(self, ctx: SlashContext, subreddit: str) -> None:
        """Get the rules of the specified subreddit."""
        # Send a quick response
        # We will edit this later with the actual content
        msg = await ctx.send(f"Getting the rules for r/{subreddit}...")


def setup(bot: ButtercupBot) -> None:
    """Set up the Rules cog."""
    reddit_config = bot.config["Reddit"]
    reddit_api = praw.Reddit(
        client_id=reddit_config["client_id"],
        client_secret=reddit_config["client_secret"],
        user_agent=reddit_config["user_agent"],
    )
    bot.add_cog(Rules(bot=bot, reddit_api=reddit_api))


def teardown(bot: ButtercupBot) -> None:
    """Unload the Rules cog."""
    bot.remove_cog("Rules")
