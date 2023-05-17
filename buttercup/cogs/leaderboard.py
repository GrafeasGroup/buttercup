from datetime import datetime
from typing import Any, Dict, Optional

import pytz
from blossom_wrapper import BlossomAPI
from discord import Colour, Embed
from discord.ext.commands import Cog
from discord_slash import SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_option

from buttercup.bot import ButtercupBot
from buttercup.cogs.helpers import (
    BlossomException,
    get_duration_str,
    get_initial_username,
    get_rank,
    get_rgb_from_hex,
    get_timedelta_str,
    get_user,
    get_user_id,
    get_username,
    parse_time_constraints,
)
from buttercup.strings import translation

i18n = translation()


def format_leaderboard_user(user: Dict[str, Any]) -> str:
    """Format one user in the leaderboard."""
    rank = user["rank"]
    username = user["username"]
    gamma = user["gamma"]

    return f"{rank}. {username} ({gamma:,})"


def format_leaderboard_timeframe(after: Optional[datetime], before: Optional[datetime]) -> str:
    """Format the time frame that the leaderboard is calculated on."""
    if not after and not before:
        return "all time"

    # 2017-04-01 is the start of the project
    delta = (before or datetime.now(tz=pytz.utc)) - (after or datetime(2017, 4, 1, tzinfo=pytz.utc))

    return get_timedelta_str(delta)


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
            ),
            create_option(
                name="after",
                description="The start date for the leaderboard.",
                option_type=3,
                required=False,
            ),
            create_option(
                name="before",
                description="The end date for the leaderboard.",
                option_type=3,
                required=False,
            ),
        ],
    )
    async def leaderboard(
        self,
        ctx: SlashContext,
        username: str = "me",
        after: Optional[str] = None,
        before: Optional[str] = None,
    ) -> None:
        """Get the leaderboard for the given user."""
        start = datetime.now(tz=pytz.utc)

        after_time, before_time, time_str = parse_time_constraints(after, before)

        # Send a first message to show that the bot is responsive.
        # We will edit this message later with the actual content.
        msg = await ctx.send(
            i18n["leaderboard"]["getting_leaderboard"].format(
                user=get_initial_username(username, ctx), time_str=time_str
            )
        )

        user = get_user(username, ctx, self.blossom_api)

        top_count = 5 if user else 15
        context_count = 5

        from_str = after_time.isoformat() if after_time else None
        until_str = before_time.isoformat() if before_time else None

        # Get the leaderboard data
        leaderboard_response = self.blossom_api.get(
            "submission/leaderboard",
            params={
                "user_id": get_user_id(user),
                "top_count": top_count,
                "below_count": context_count,
                "above_count": context_count,
                "complete_time__gte": from_str,
                "complete_time__lte": until_str,
            },
        )
        if leaderboard_response.status_code != 200:
            raise BlossomException(leaderboard_response)

        leaderboard = leaderboard_response.json()
        # Extract needed data
        top_users = leaderboard["top"]
        above_users = leaderboard["above"]
        lb_user = leaderboard["user"]
        below_users = leaderboard["below"]

        description = ""

        # Only show the top users if they are not already included
        top_user_limit = (
            top_count + 1
            if user is None
            else above_users[0]["rank"]
            if len(above_users) > 0
            else lb_user["rank"]
        )

        # Show top users
        for top_user in top_users[: top_user_limit - 1]:
            description += format_leaderboard_user(top_user) + "\n"

        rank = get_rank(top_users[0]["gamma"])

        if user:
            # Add separator if necessary
            if top_user_limit > top_count + 1:
                description += "...\n"

            # Show users with more gamma than the current user
            for above_user in above_users:
                description += format_leaderboard_user(above_user) + "\n"

            # Show the current user
            description += "**" + format_leaderboard_user(lb_user) + "**\n"

            # Show users with less gamma than the current user
            for below_user in below_users:
                description += format_leaderboard_user(below_user) + "\n"

            rank = get_rank(user["gamma"])

        time_frame = format_leaderboard_timeframe(after_time, before_time)

        await msg.edit(
            content=i18n["leaderboard"]["embed_message"].format(
                user=get_username(user),
                time_str=time_str,
                duration=get_duration_str(start),
            ),
            embed=Embed(
                title=i18n["leaderboard"]["embed_title"].format(
                    user=get_username(user), time_frame=time_frame
                ),
                description=description,
                color=Colour.from_rgb(*get_rgb_from_hex(rank["color"])),
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
