from datetime import datetime
from random import choice
from typing import Optional

import discord
import pytz
from blossom_wrapper import BlossomAPI
from dateutil.parser import parse
from discord import Embed
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
    get_progress_bar,
    get_rank,
    get_rgb_from_hex,
    get_user,
    get_user_id,
    get_username,
    parse_time_constraints,
)
from buttercup.strings import translation

i18n = translation()


def get_motivational_message(user: Optional[BlossomUser], progress_count: int) -> str:
    """Determine the motivational message for the current progress."""
    all_messages = i18n["progress"]["motivational_messages"]
    message_set = []

    # Determine the motivational messages for the current progress
    for threshold in reversed(all_messages):
        if progress_count >= threshold:
            message_set = all_messages[threshold]
            break

    # Select a random message
    return choice(message_set).format(user=get_username(user))


class Stats(Cog):
    def __init__(self, bot: ButtercupBot, blossom_api: BlossomAPI) -> None:
        """Initialize the Stats cog."""
        self.bot = bot
        self.blossom_api = blossom_api

    @cog_ext.cog_slash(
        name="stats",
        description="Get stats about one or all users.",
        options=[
            create_option(
                name="username",
                description="The username to get the stats for. "
                + "Use 'all' to get the global stats.",
                option_type=3,
                required=False,
            )
        ],
    )
    async def _stats(self, ctx: SlashContext, username: str = "me") -> None:
        """Get the stats about one or all users."""
        initial_username = get_initial_username(username, ctx)

        # Send a first message to show that the bot is responsive.
        # We will edit this message later with the actual content.
        msg = await ctx.send(
            i18n["stats"]["getting_stats"].format(user=initial_username)
        )

        if initial_username == get_username(None):
            # Global stats
            await self._all_stats(msg)
        else:
            await self._user_stats(ctx, msg, username)

    async def _all_stats(self, msg: SlashMessage) -> None:
        """Get stats about all users."""
        start = datetime.now(tz=pytz.utc)

        response = self.blossom_api.get("summary/")

        if response.status_code != 200:
            raise BlossomException(response)

        data = response.json()

        description = i18n["stats"]["embed_description_all"].format(
            volunteers=data["volunteer_count"],
            transcriptions=data["transcription_count"],
            days=data["days_since_inception"],
        )

        await msg.edit(
            content=i18n["stats"]["embed_message"].format(
                user=get_username(None), duration=get_duration_str(start)
            ),
            embed=Embed(
                title=i18n["stats"]["embed_title"].format(user=get_username(None)),
                description=description,
            ),
        )

    async def _user_stats(
        self, ctx: SlashContext, msg: SlashMessage, username: str
    ) -> None:
        """Get stats about a single user."""
        start = datetime.now(tz=pytz.utc)

        user = get_user(username, ctx, self.blossom_api)

        # Get the date of last activity
        submission_response = self.blossom_api.get(
            "submission/",
            params={
                "completed_by": get_user_id(user),
                "ordering": "-complete_time",
                "complete_time__isnull": False,
                "page_size": 1,
                "page": 1,
            },
        )
        if not submission_response.ok:
            raise BlossomException(submission_response)

        submission_data = submission_response.json()["results"][0]

        date_joined = parse(user["date_joined"])
        # For some reason, the complete_time is sometimes None, so we have to fall back
        last_active = parse(
            submission_data["complete_time"]
            or submission_data["claim_time"]
            or submission_data["create_time"]
        )

        # Get the user's leaderboard rank
        leaderboard_response = self.blossom_api.get(
            "submission/leaderboard",
            params={
                "user_id": get_user_id(user),
                "top_count": 0,
                "below_count": 0,
                "above_count": 0,
            },
        )
        if leaderboard_response.status_code != 200:
            raise BlossomException(leaderboard_response)

        leaderboard_rank = leaderboard_response.json()["user"]["rank"]

        rank = get_rank(user["gamma"])

        description = i18n["stats"]["embed_description_user"].format(
            gamma=user["gamma"],
            flair_rank=rank["name"],
            leaderboard_rank=leaderboard_rank,
            date_joined=get_discord_time_str(date_joined),
            joined_ago=get_discord_time_str(date_joined, "R"),
            last_active=get_discord_time_str(last_active),
            last_ago=get_discord_time_str(last_active, "R"),
        )

        await msg.edit(
            content=i18n["stats"]["embed_message"].format(
                user=get_username(user), duration=get_duration_str(start)
            ),
            embed=Embed(
                title=i18n["stats"]["embed_title"].format(user=get_username(user)),
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
                name="after",
                description="The start time for the progress."
                "Defaults to 24 hours ago.",
                option_type=3,
                required=False,
            ),
            create_option(
                name="before",
                description="The end date for the progress."
                "Defaults to the current time.",
                option_type=3,
                required=False,
            ),
        ],
    )
    async def _progress(
        self,
        ctx: SlashContext,
        username: str = "me",
        after: Optional[str] = None,
        before: Optional[str] = None,
    ) -> None:
        """Get the transcribing progress of a user in the given time frame."""
        start = datetime.now()

        # Parse time frame. Defaults to 24 hours ago
        after_time, before_time, time_str = parse_time_constraints(
            after or "24", before
        )

        # Send a first message to show that the bot is responsive.
        # We will edit this message later with the actual content.
        msg = await ctx.send(
            i18n["progress"]["getting_progress"].format(
                user=get_initial_username(username, ctx), time_str=time_str
            )
        )

        user = get_user(username, ctx, self.blossom_api)

        from_str = after_time.isoformat() if after_time else None
        until_str = before_time.isoformat() if before_time else None

        # We ask for submission completed by the user in the given time frame
        # The response will contain a count, so we just need 1 result
        progress_response = self.blossom_api.get(
            "submission/",
            params={
                "completed_by": get_user_id(user),
                "complete_time__gte": from_str,
                "complete_time__lte": until_str,
                "page_size": 1,
            },
        )
        if not progress_response.ok:
            raise BlossomException(progress_response)

        progress_count = progress_response.json()["count"]

        # The progress bar only makes sense for a 24 hour time frame
        is_24_hours = (
            after_time is not None
            and (
                (before_time or datetime.now(tz=pytz.utc)) - after_time
            ).total_seconds()
            # Up to 2 seconds difference are allowed
            <= 60 * 60 * 24 + 2
        )

        if not is_24_hours or not user:
            # If it isn't 24 hours or if it's the global stats
            # a progress bar doesn't make sense
            await msg.edit(
                content=i18n["progress"]["embed_message"].format(
                    user=get_username(user), duration=get_duration_str(start),
                ),
                embed=Embed(
                    title=i18n["progress"]["embed_title"].format(
                        user=get_username(user)
                    ),
                    description=i18n["progress"]["embed_description_other"].format(
                        count=progress_count, time_str=time_str,
                    ),
                ),
            )
            return

        motivational_message = get_motivational_message(user, progress_count)

        await msg.edit(
            content=i18n["progress"]["embed_message"].format(
                user=get_username(user), duration=get_duration_str(start),
            ),
            embed=Embed(
                title=i18n["progress"]["embed_title"].format(user=get_username(user)),
                description=i18n["progress"]["embed_description_24"].format(
                    bar=get_progress_bar(progress_count, 100),
                    count=progress_count,
                    total=100,
                    time_str=time_str,
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
