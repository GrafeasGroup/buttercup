import asyncio
import math
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict

import pytz
from blossom_wrapper import BlossomAPI
from dateutil import parser
from discord import Embed, Forbidden, Reaction, User
from discord.ext import commands
from discord.ext.commands import Cog
from discord_slash import SlashContext, cog_ext
from discord_slash.model import SlashMessage
from discord_slash.utils.manage_commands import create_option

from buttercup.bot import ButtercupBot
from buttercup.cogs.helpers import (
    BlossomException,
    BlossomUser,
    get_discord_time_str,
    get_duration_str,
    get_initial_username,
    get_user,
    get_username,
    parse_time_constraints,
)
from buttercup.strings import translation

i18n = translation()


class Queue(Cog):
    def __init__(self, bot: ButtercupBot, blossom_api: BlossomAPI) -> None:
        """Initialize the Queue cog."""
        self.bot = bot
        self.blossom_api = blossom_api

    @cog_ext.cog_slash(
        name="queue",
        description="Display the current status of the queue.",
        options=[
            create_option(
                name="source",
                description="The source (subreddit) to filter the queue by.",
                option_type=3,
                required=False,
            ),
        ],
    )
    async def queue(self, ctx: SlashContext, source: Optional[str] = None,) -> None:
        """Display the current status of the queue."""
        start = datetime.now()

        # Send a first message to show that the bot is responsive.
        # We will edit this message later with the actual content.
        msg = await ctx.send(i18n["queue"]["getting_queue"])

        await msg.edit(
            content=i18n["queue"]["embed_message"].format(
                duration_str=get_duration_str(start)
            )
        )


def setup(bot: ButtercupBot) -> None:
    """Set up the Queue cog."""
    cog_config = bot.config["Blossom"]
    email = cog_config.get("email")
    password = cog_config.get("password")
    api_key = cog_config.get("api_key")
    blossom_api = BlossomAPI(email=email, password=password, api_key=api_key)
    bot.add_cog(Queue(bot=bot, blossom_api=blossom_api))


def teardown(bot: ButtercupBot) -> None:
    """Unload the Queue cog."""
    bot.remove_cog("Queue")
