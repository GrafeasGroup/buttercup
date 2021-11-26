from typing import Optional

from blossom_wrapper import BlossomAPI
from discord import Member, TextChannel
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
        # TODO: Trigger this when the rules have been accepted
        # This event is triggered when the user joins, but they don't have
        # access to all channels at this point. A pop-up with the rules are
        # shown and they have to accept that first.
        # However, Discord currently doesn't seem to provide an event for that.
        # This causes many to miss the initial welcome message.
        welcome_channel: Optional[TextChannel] = member.guild.system_channel

        if not welcome_channel:
            return

        await welcome_channel.send(
            content=i18n["welcome"]["new_member"].format(user_id=member.id)
        )


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
