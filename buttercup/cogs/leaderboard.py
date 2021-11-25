from datetime import datetime
from random import choice
from typing import Optional, Any, Dict

import discord
import pytz
from blossom_wrapper import BlossomAPI, BlossomStatus
from dateutil.parser import parse
from discord import Embed
from discord.ext.commands import Cog
from discord_slash import SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_option

from buttercup.bot import ButtercupBot
from buttercup.cogs.helpers import (
    extract_username,
    get_discord_time_str,
    get_duration_str,
    get_progress_bar,
    get_rank,
    get_rgb_from_hex,
    parse_time_constraints, BlossomException,
)
from buttercup.strings import translation

i18n = translation()


def format_leaderboard_user(user: Dict[str, Any]) -> str:
    """Format one user in the leaderboard."""
    rank = user["rank"]
    username = user["username"]
    gamma = user["gamma"]

    return f"{rank}. {username} ({gamma})"


class Leaderboard(Cog):
    def __init__(self, bot: ButtercupBot, blossom_api: BlossomAPI) -> None:
        """Initialize the Leaderboard cog."""
        self.bot = bot
        self.blossom_api = blossom_api

    @cog_ext.cog_slash(
        name="leaderboard",
        description="Get the current leaderboard.",
        options=[
            create_option(
                name="username",
                description="The username to get the leaderboard for. "
                "Defaults to the user executing the command.",
                option_type=3,
                required=False,
            )
        ],
    )
    async def leaderboard(self, ctx: SlashContext, username: Optional[str] = None) -> None:
        """Get the leaderboard for the given user."""
        start = datetime.now(tz=pytz.utc)

        username = username or extract_username(ctx.author.display_name)
        # Send a first message to show that the bot is responsive.
        # We will edit this message later with the actual content.
        msg = await ctx.send(i18n["leaderboard"]["getting_leaderboard"].format(user=username))

        volunteer_response = self.blossom_api.get_user(username)
        if volunteer_response.status != BlossomStatus.ok:
            raise BlossomException(volunteer_response)
        user = volunteer_response.data
        username = user["username"]

        top_count = 5
        context_count = 5

        # Get the leaderboard data
        leaderboard_response = self.blossom_api.get(
            "submission/leaderboard",
            params={
                "user_id": user["id"],
                "top_count": top_count,
                "below_count": context_count,
                "above_count": context_count,
            },
        )
        if leaderboard_response.status_code != 200:
            raise BlossomException(leaderboard_response)
        leaderboard = leaderboard_response.json()

        description = ""

        for top_user in leaderboard["top"]:
            description += format_leaderboard_user(top_user) + "\n"

        description += "...\n"

        for above_user in leaderboard["above"]:
            description += format_leaderboard_user(above_user) + "\n"

        description += "**" + format_leaderboard_user(leaderboard["user"]) + "**\n"

        for below_user in leaderboard["below"]:
            description += format_leaderboard_user(below_user) + "\n"

        await msg.edit(
            content=i18n["leaderboard"]["embed_message"].format(
                duration=get_duration_str(start)
            ),
            embed=Embed(
                title=i18n["leaderboard"]["embed_title"].format(user=username),
                description=description,
            ),
        )


def setup(bot: ButtercupBot) -> None:
    """Set up the Leaderboard cog."""
    cog_config = bot.config["Blossom"]
    email = cog_config.get("email")
    password = cog_config.get("password")
    api_key = cog_config.get("api_key")
    blossom_api = BlossomAPI(email=email, password=password, api_key=api_key)
    bot.add_cog(Leaderboard(bot=bot, blossom_api=blossom_api))


def teardown(bot: ButtercupBot) -> None:
    """Unload the Leaderboard cog."""
    bot.remove_cog("Leaderboard")
