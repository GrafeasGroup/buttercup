from datetime import datetime, timedelta
from typing import Dict, Optional

import pandas as pd
import pytz
from blossom_wrapper import BlossomAPI
from discord import Embed
from discord.ext import tasks
from discord.ext.commands import Cog
from discord_slash import SlashContext, cog_ext
from discord_slash.model import SlashMessage
from discord_slash.utils.manage_commands import create_option

from buttercup.bot import ButtercupBot
from buttercup.cogs.helpers import (
    BlossomException,
    get_duration_str,
    get_submission_source,
)
from buttercup.strings import translation

i18n = translation()


def fix_submission_source(submission: Dict) -> Dict:
    """Fix the source of the submission to be the subreddit."""
    return {
        **submission,
        "source": get_submission_source(submission),
    }


def get_source_list(sources: pd.Series) -> str:
    """Get a list of the posts grouped by sources."""
    items = [
        i18n["queue"]["source_list_entry"].format(count=count, source=source)
        for source, count in sources.head(5).iteritems()
    ]
    result = "\n".join(items)

    if len(sources) > 5:
        rest = sources[5:]
        source_count = len(rest)
        post_count = rest.sum()
        result += "\n" + i18n["queue"]["source_list_others"].format(
            post_count=post_count, source_count=source_count
        )

    return result


class Queue(Cog):
    def __init__(self, bot: ButtercupBot, blossom_api: BlossomAPI) -> None:
        """Initialize the Queue cog."""
        self.bot = bot
        self.blossom_api = blossom_api

        self.unclaimed = None
        self.messages = []

        self.update_cycle.start()

    @tasks.loop(minutes=1)
    async def update_cycle(self):
        """Keep everything up-to-date."""
        print("Updating the queue!")
        await self.update_queue()
        await self.update_messages()

    async def update_queue(self):
        """Update the cached queue items."""
        self.unclaimed = await self.get_unclaimed_queue_submissions()

    async def update_messages(self):
        """Update all messages with the latest queue stats."""
        for msg in self.messages:
            await self.update_message(msg)

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
            data = [fix_submission_source(entry) for entry in data]
            results += data
            page += 1

            if len(data) < size:
                break

        data_frame = pd.DataFrame.from_records(data=results, index="id")
        return data_frame

    def add_message(self, msg: SlashMessage):
        """Add a new message to update with the current queue stats.

        This enforces a maximum amount of messages that should
        be kept updated, to improve performance.
        """
        limit = 5
        self.messages = self.messages[:-limit] + [msg]
        print(f"Messages: {len(self.messages)}")

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
        # Send a first message to show that the bot is responsive.
        # We will edit this message later with the actual content.
        msg = await ctx.send(i18n["queue"]["getting_queue"])
        # Update the message with the last known stats
        await self.update_message(msg)
        # Keep the message updated in the future
        self.add_message(msg)

    async def update_message(self, msg: SlashMessage):
        """Update the given message with the latest queue stats."""
        start = datetime.now()

        unclaimed = self.unclaimed
        unclaimed_count = len(unclaimed.index)

        sources = (
            unclaimed.reset_index()
            .groupby(["source"])["id"]
            .count()
            .sort_values(ascending=False)
        )
        source_list = get_source_list(sources)

        unclaimed_message = (
            i18n["queue"]["unclaimed_message_cleared"]
            if unclaimed_count == 0
            else i18n["queue"]["unclaimed_message"].format(
                unclaimed_count=unclaimed_count, source_list=source_list,
            )
        )

        await msg.edit(
            content=i18n["queue"]["embed_message"].format(
                duration_str=get_duration_str(start),
            ),
            embed=Embed(
                title=i18n["queue"]["embed_title"],
                description=i18n["queue"]["embed_description"].format(
                    unclaimed_message=unclaimed_message
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
