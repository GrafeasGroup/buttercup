from datetime import datetime, timedelta
from random import choice
from typing import Dict, Optional, Tuple, Union

import discord
import pytz
from blossom_wrapper import BlossomAPI, BlossomStatus
from dateutil.parser import parse
from discord import Embed
from discord.ext.commands import Cog
from discord_slash import SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_option

from buttercup.bot import ButtercupBot
from buttercup.cogs import ranks
from buttercup.cogs.helpers import (
    extract_username,
    get_discord_time_str,
    get_duration_str,
    get_progress_bar,
)
from buttercup.strings import translation

i18n = translation()


def get_rank(gamma: int) -> Dict[str, Union[str, int]]:
    """Get the rank matching the gamma score."""
    for rank in reversed(ranks):
        if gamma >= rank["threshold"]:
            return rank

    return {"name": "Visitor", "threshold": 0, "color": "#000000"}


def get_rgb_from_hex(hex_str: str) -> Tuple[int, int, int]:
    """Get the rgb values from a hex string."""
    # Adopted from
    # https://stackoverflow.com/questions/29643352/converting-hex-to-rgb-value-in-python
    hx = hex_str.lstrip("#")
    return int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)


def get_motivational_message(user: str, progress_count: int) -> str:
    """Determine the motivational message for the current progress."""
    all_messages = i18n["progress"]["motivational_messages"]
    message_set = []

    # Determine the motivational messages for the current progress
    for threshold in reversed(all_messages):
        if progress_count >= threshold:
            message_set = all_messages[threshold]
            break

    # Select a random message
    return choice(message_set).format(user=user)


class Stats(Cog):
    def __init__(self, bot: ButtercupBot, blossom_api: BlossomAPI) -> None:
        """Initialize the Stats cog."""
        self.bot = bot
        self.blossom_api = blossom_api

    @cog_ext.cog_slash(
        name="stats", description="Get stats about all users.",
    )
    async def _stats(self, ctx: SlashContext) -> None:
        """Get stats about all users."""
        # Send a first message to show that the bot is responsive.
        # We will edit this message later with the actual content.
        msg = await ctx.send(i18n["stats"]["getting_stats"])

        response = self.blossom_api.get("summary/")

        if response.status_code != 200:
            await msg.edit(content=i18n["stats"]["failed_getting_stats"])
            return

        data = response.json()

        description = i18n["stats"]["embed_description"].format(
            data["volunteer_count"],
            data["transcription_count"],
            data["days_since_inception"],
        )

        await msg.edit(
            content=i18n["stats"]["embed_message"],
            embed=Embed(title=i18n["stats"]["embed_title"], description=description),
        )

    @cog_ext.cog_slash(
        name="userstats",
        description="Get stats about a user.",
        options=[
            create_option(
                name="username",
                description="The username to get the stats for.",
                option_type=3,
                required=False,
            )
        ],
    )
    async def _user_stats(
        self, ctx: SlashContext, username: Optional[str] = None
    ) -> None:
        """Get stats about a user."""
        start = datetime.now(tz=pytz.utc)
        user = username or extract_username(ctx.author.display_name)
        # Send a first message to show that the bot is responsive.
        # We will edit this message later with the actual content.
        msg = await ctx.send(i18n["user_stats"]["getting_stats"].format(user=user))

        volunteer_response = self.blossom_api.get_user(user)
        if volunteer_response.status != BlossomStatus.ok:
            await msg.edit(
                content=i18n["user_stats"]["failed_getting_stats"].format(user=user)
            )
            return
        volunteer_data = volunteer_response.data

        # Get the date of last activity
        submission_response = self.blossom_api.get(
            "submission/",
            params={
                "completed_by": volunteer_data["id"],
                "ordering": "-complete_time",
                "complete_time__isnull": False,
                "page_size": 1,
                "page": 1,
            },
        )
        if submission_response.status_code != 200:
            await msg.edit(
                content=i18n["user_stats"]["failed_getting_stats"].format(user=user)
            )
            return
        submission_data = submission_response.json()["results"][0]

        date_joined = parse(volunteer_data["date_joined"])
        # For some reason, the complete_time is sometimes None, so we have to fall back
        last_active = parse(
            submission_data["complete_time"]
            or submission_data["claim_time"]
            or submission_data["create_time"]
        )

        rank = get_rank(volunteer_data["gamma"])

        description = i18n["user_stats"]["embed_description"].format(
            gamma=volunteer_data["gamma"],
            flair_rank=rank["name"],
            date_joined=get_discord_time_str(date_joined),
            joined_ago=get_discord_time_str(date_joined, "R"),
            last_active=get_discord_time_str(last_active),
            last_ago=get_discord_time_str(last_active, "R"),
        )

        await msg.edit(
            content=i18n["user_stats"]["embed_message"].format(
                user=user, duration=get_duration_str(start)
            ),
            embed=Embed(
                title=i18n["user_stats"]["embed_title"].format(user=user),
                color=discord.Colour.from_rgb(*get_rgb_from_hex(rank["color"])),
                description=description,
            ),
        )

    @cog_ext.cog_slash(
        name="progress",
        description="Get the transcribing progress of a user.",
        options=[
            create_option(
                name="username",
                description="The user to get the progress of. "
                "Defaults to the user executing the command.",
                option_type=3,
                required=False,
            ),
            create_option(
                name="hours",
                description="The time frame of the progress in hours. "
                "Defaults to 24 hours.",
                option_type=4,
                required=False,
            ),
        ],
    )
    async def _progress(
        self, ctx: SlashContext, username: Optional[str] = None, hours: int = 24,
    ) -> None:
        """Get the transcribing progress of a user in the given time frame."""
        start = datetime.now()
        user = username or extract_username(ctx.author.display_name)
        # Send a first message to show that the bot is responsive.
        # We will edit this message later with the actual content.
        msg = await ctx.send(
            i18n["progress"]["getting_progress"].format(user=user, hours=hours)
        )

        volunteer_response = self.blossom_api.get_user(user)
        if volunteer_response.status != BlossomStatus.ok:
            await msg.edit(content=i18n["progress"]["user_not_found"].format(user))
            return
        volunteer_id = volunteer_response.data["id"]

        if volunteer_response.data["gamma"] == 0:
            # The user has not started transcribing yet
            await msg.edit(
                content=i18n["progress"]["embed_message"].format(
                    get_duration_str(start)
                ),
                embed=Embed(
                    title=i18n["progress"]["embed_title"].format(user),
                    description=i18n["progress"]["embed_description_new"].format(
                        user=user
                    ),
                ),
            )
            return

        from_date = start - timedelta(hours=hours)

        # We ask for submission completed by the user in the last 24 hours
        # The response will contain a count, so we just need 1 result
        progress_response = self.blossom_api.get(
            "submission/",
            params={
                "completed_by": volunteer_id,
                "from": from_date.isoformat(),
                "page_size": 1,
            },
        )
        if progress_response.status_code != 200:
            await msg.edit(
                content=i18n["progress"]["failed_getting_progress"].format(user)
            )
            return
        progress_count = progress_response.json()["count"]

        if hours != 24:
            # If it isn't 24, we can't really display a progress bar
            await msg.edit(
                content=i18n["progress"]["embed_message"].format(
                    get_duration_str(start)
                ),
                embed=Embed(
                    title=i18n["progress"]["embed_title"].format(user),
                    description=i18n["progress"]["embed_description_other"].format(
                        count=progress_count, hours=hours,
                    ),
                ),
            )
            return

        motivational_message = get_motivational_message(user, progress_count)

        await msg.edit(
            content=i18n["progress"]["embed_message"].format(get_duration_str(start)),
            embed=Embed(
                title=i18n["progress"]["embed_title"].format(user),
                description=i18n["progress"]["embed_description_24"].format(
                    bar=get_progress_bar(progress_count, 100),
                    count=progress_count,
                    total=100,
                    hours=hours,
                    message=motivational_message,
                ),
            ),
        )


def setup(bot: ButtercupBot) -> None:
    """Set up the Stats cog."""
    cog_config = bot.config["Blossom"]
    email = cog_config.get("email")
    password = cog_config.get("password")
    api_key = cog_config.get("api_key")
    blossom_api = BlossomAPI(email=email, password=password, api_key=api_key)
    bot.add_cog(Stats(bot=bot, blossom_api=blossom_api))


def teardown(bot: ButtercupBot) -> None:
    """Unload the Stats cog."""
    bot.remove_cog("Stats")
