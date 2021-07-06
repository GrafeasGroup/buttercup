from datetime import datetime, timedelta
from random import choice
from typing import Optional

from blossom_wrapper import BlossomAPI, BlossomStatus
from discord import Embed
from discord.ext.commands import Cog
from discord_slash import SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_option

from buttercup.bot import ButtercupBot
from buttercup.cogs.helpers import extract_username, get_duration_str, get_progress_bar
from buttercup.strings import translation

i18n = translation()


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
