from typing import Dict, Optional
from urllib.parse import urlparse

from blossom_wrapper import BlossomAPI, BlossomStatus
from discord import Color, Embed
from discord.ext.commands import Cog
from discord_slash import SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_option

from buttercup.bot import ButtercupBot
from buttercup.strings import translation

i18n = translation()


def username_from_display_name(display_name: str) -> Optional[str]:
    """Extract the username from the display name."""
    first_part = display_name.split(" ")[0]

    if not first_part.startswith("/u/"):
        return None

    return first_part[3:]


class History(Cog):
    def __init__(self, bot: ButtercupBot, blossom_api: BlossomAPI) -> None:
        """Initialize the History cog."""
        self.bot = bot
        self.blossom_api = blossom_api

    @cog_ext.cog_slash(
        name="history",
        description="Display the history graph.",
        options=[
            create_option(
                name="user_1",
                description="The user to display the history graph for.",
                option_type=3,
                required=False,
            )
        ],
    )
    async def _history(self, ctx: SlashContext, user_1: Optional[str] = None) -> None:
        """Find the post with the given URL."""
        # Give a quick response to let the user know we're working on it
        # We'll later edit this message with the actual content
        msg = await ctx.send("Creating the history graph...")

        username_1 = user_1
        if user_1 is None:
            username_1 = username_from_display_name(ctx.author.display_name)
            if username_1 is None:
                await msg.edit(content=f"{ctx.author.display_name} is an invalid username! Did you change your display name to the required format?")
                return

        # First, get the total gamma for the user
        user_1_response = self.blossom_api.get_user(username_1)
        if user_1_response.status != BlossomStatus.ok:
            await msg.edit(content=f"Failed to get the data for user {username_1}!")
            return
        user_1_gamma = user_1_response.data["gamma"]

        await msg.edit(content=f"User {username_1} has {user_1_gamma} gamma.")


def setup(bot: ButtercupBot) -> None:
    """Set up the History cog."""
    cog_config = bot.config["Blossom"]
    email = cog_config.get("email")
    password = cog_config.get("password")
    api_key = cog_config.get("api_key")
    blossom_api = BlossomAPI(email=email, password=password, api_key=api_key)
    bot.add_cog(History(bot=bot, blossom_api=blossom_api))


def teardown(bot: ButtercupBot) -> None:
    """Unload the History cog."""
    bot.remove_cog("History")
