import asyncio
import math
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, TypedDict

import pandas as pd
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

    async def get_unclaimed_queue_submissions(self) -> pd.DataFrame:
        """Get the submissions that are currently unclaimed in the queue."""
        # Posts older than 18 hours are archived
        queue_start = datetime.now(tz=pytz.utc) - timedelta(hours=18)
        results = []
        size = 500
        page = 1

        # Fetch all unclaimed posts from the queue
        while True:
            queue_response = self.blossom_api.get(
                "submission/",
                params={
                    "page_size": size,
                    "page": page,
                    "completed_by__isnull": True,
                    "claimed_by__isnull": True,
                    "archived": False,
                    "create_time__gte": queue_start.isoformat(),
                },
            )
            if not queue_response.ok:
                raise BlossomException(queue_response)

            data = queue_response.json()["results"]
            results += data
            page += 1

            if len(data) < size:
                break

        data_frame = pd.DataFrame.from_records(data=results, index="id")
        return data_frame

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

        unclaimed = await self.get_unclaimed_queue_submissions()

        await msg.edit(
            content=i18n["queue"]["embed_message"].format(
                duration_str=get_duration_str(start),
            ),
            embed=Embed(
                title=i18n["queue"]["embed_title"],
                description=i18n["queue"]["embed_description"].format(
                    unclaimed=len(unclaimed.index),
                ),
            ),
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
