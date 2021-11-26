from typing import Optional

from blossom_wrapper import BlossomAPI
from discord import Member, Guild, TextChannel
from discord.ext.commands import Cog

from buttercup.bot import ButtercupBot
from buttercup.strings import translation

i18n = translation()


class Welcome(Cog):
    def __init__(self, bot: ButtercupBot, blossom_api: BlossomAPI) -> None:
        """Initialize the Welcome cog."""
        self.bot = bot
        self.blossom_api = blossom_api

    @Cog.listener()
    async def on_member_join(self, member: Member) -> None:
        """Welcome new members to the server."""
        welcome_channel: Optional[TextChannel] = member.guild.system_channel

        if not welcome_channel:
            return

        await welcome_channel.send(content=f"Welcome {member.display_name}!")


def setup(bot: ButtercupBot) -> None:
    """Set up the Welcome cog."""
    cog_config = bot.config["Blossom"]
    email = cog_config.get("email")
    password = cog_config.get("password")
    api_key = cog_config.get("api_key")
    blossom_api = BlossomAPI(email=email, password=password, api_key=api_key)
    bot.add_cog(Welcome(bot=bot, blossom_api=blossom_api))


def teardown(bot: ButtercupBot) -> None:
    """Unload the Welcome cog."""
    bot.remove_cog("welcome")
