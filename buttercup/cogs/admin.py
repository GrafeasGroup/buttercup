from discord import Member
from discord.ext.commands import CheckFailure, Cog
from discord_slash import SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_option

from buttercup.bot import ButtercupBot


class AdminCommands(Cog):
    def __init__(self, bot: ButtercupBot, role_name: str = "ToR Mods") -> None:
        """Initialize the Admin Commands cog."""
        self.bot = bot
        self.role_name = role_name

    def _is_authorized(self, member: Member) -> bool:
        """Check whether the user invoking the command is the correct role."""
        return self.role_name in {role.name for role in member.roles}

    @cog_ext.cog_slash(
        name="reload",
        description="Reloads the Cog with the provided name.",
        options=[
            create_option(
                name="cog_name",
                description="Name of the Cog.",
                option_type=3,
                required=True,
            )
        ],
    )
    async def _reload(self, ctx: SlashContext, cog_name: str) -> None:
        """Allow for the provided cog to be reloaded."""
        if not self._is_authorized(ctx.author):
            raise CheckFailure()
        self.bot.reload(cog_name)
        await ctx.send(f'Cog "{cog_name}" has been successfully reloaded :+1:')

    @cog_ext.cog_slash(
        name="load",
        description="Loads the Cog with the provided name.",
        options=[
            create_option(
                name="cog_name",
                description="Name of the Cog.",
                option_type=3,
                required=True,
            )
        ],
    )
    async def _load(self, ctx: SlashContext, cog_name: str) -> None:
        """Allow for the provided cog to be loaded."""
        if not self._is_authorized(ctx.author):
            raise CheckFailure()
        self.bot.load(cog_name)
        await ctx.send(f'Cog "{cog_name}" has been successfully loaded :+1:')

    @cog_ext.cog_slash(
        name="unload",
        description="Unloads the Cog with the provided name.",
        options=[
            create_option(
                name="cog_name",
                description="Name of the Cog.",
                option_type=3,
                required=True,
            )
        ],
    )
    async def _unload(self, ctx: SlashContext, cog_name: str) -> None:
        """Allow for the provided cog to be unloaded."""
        if not self._is_authorized(ctx.author):
            raise CheckFailure()
        self.bot.unload(cog_name)
        await ctx.send(f'Cog "{cog_name}" has been successfully unloaded :+1:')


def setup(bot: ButtercupBot) -> None:
    """Set up the Admin cog."""
    role_name = bot.config["Admin"]["role"]
    bot.add_cog(AdminCommands(bot, role_name))


def teardown(bot: ButtercupBot) -> None:
    """Unload the Admin cog."""
    bot.remove_cog("AdminCommands")
