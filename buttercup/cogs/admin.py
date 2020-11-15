import discord.utils
from discord.ext.commands import Cog, Context, command
from discord.role import Role

from buttercup.bot import ButtercupBot


class AdminCommands(Cog):
    def __init__(self, bot: ButtercupBot, role_name: str = "ToR Mods") -> None:
        """Initialize the Admin Commands cog."""
        self.bot = bot
        self.role_name = role_name

    @property
    def role(self) -> Role:
        """Provide the role corresponding to that of the ToR Moderators."""
        return discord.utils.get(self.bot.guild.roles, name=self.role_name)

    def cog_check(self, ctx: Context) -> bool:
        """Check whether the user invoking the command is the correct role."""
        return self.role in ctx.author.roles

    @command()
    async def reload(self, ctx: Context, cog_name: str) -> None:
        """Allow for the provided cog to be reloaded."""
        self.bot.reload(cog_name)
        await ctx.send(f'Cog "{cog_name}" has been successfully reloaded :+1:')

    @command()
    async def load(self, ctx: Context, cog_name: str) -> None:
        """Allow for the provided cog to be loaded."""
        self.bot.load(cog_name)
        await ctx.send(f'Cog "{cog_name}" has been successfully loaded :+1:')

    @command()
    async def unload(self, ctx: Context, cog_name: str) -> None:
        """Allow for the provided cog to be unloaded."""
        self.bot.unload(cog_name)
        await ctx.send(f'Cog "{cog_name}" has been successfully unloaded :+1:')


def setup(bot: ButtercupBot) -> None:
    """Set up the Admin cog."""
    role_name = bot.config["Admin"]["role"]
    bot.add_cog(AdminCommands(bot, role_name))


def teardown(bot: ButtercupBot) -> None:
    """Unload the Admin cog."""
    bot.remove_cog("AdminCommands")
