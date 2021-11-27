from discord.ext.commands import Cog
from discord.member import Member

from buttercup.bot import ButtercupBot
from buttercup.strings import translation

i18n = translation()


class NameValidator(Cog):
    def __init__(self, bot: ButtercupBot, valid_role_id: str,) -> None:
        """Initialize the member's records and retrieve the roles and channels."""
        self.bot = bot
        self.valid_role_id = valid_role_id

    @Cog.listener()
    async def on_member_update(self, before: Member, after: Member) -> None:
        """Check whether the new nickname corresponds to the guidelines."""
        before_name = before.display_name
        after_name = after.display_name

        print(f"Display name changed from {before_name} to {after_name}")


def setup(bot: ButtercupBot) -> None:
    """Set up the NameValidator cog."""
    cog_config = bot.config["NameValidator"]
    valid_role_id = cog_config.get("valid_role_id")
    bot.add_cog(NameValidator(bot, valid_role_id))


def teardown(bot: ButtercupBot) -> None:
    """Unload the NameValidator cog."""
    bot.remove_cog("NameValidator")
