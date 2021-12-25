from typing import Dict

from discord.ext.commands import Cog
from discord_slash import SlashContext, cog_ext
from discord_slash.model import SlashCommandPermissionType
from discord_slash.utils.manage_commands import create_option, create_permission

from buttercup.bot import ButtercupBot
from buttercup.cogs.config import config


def generate_admin_permissions() -> Dict:
    """Generate the admin permissions from the config.

    Note that this is a bit hacky and the config cog has to be loaded first.
    Unfortunately we can't use the bot object in the annotation, so we can't
    access the config like this directly.
    """
    permissions = {}
    for guild in config["Discord"]["guilds"]:
        permissions[guild["id"]] = [
            create_permission(role_id, SlashCommandPermissionType.ROLE, True)
            for role_id in guild["mod_roles"]
        ]
    print(permissions)
    return permissions


class AdminCommands(Cog):
    def __init__(self, bot: ButtercupBot) -> None:
        """Initialize the Admin Commands cog."""
        self.bot = bot

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
        default_permission=False,
        permissions=generate_admin_permissions(),
    )
    async def _reload(self, ctx: SlashContext, cog_name: str) -> None:
        """Allow for the provided cog to be reloaded."""
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
        default_permission=False,
        permissions=generate_admin_permissions(),
    )
    async def _load(self, ctx: SlashContext, cog_name: str) -> None:
        """Allow for the provided cog to be loaded."""
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
        default_permission=False,
        permissions=generate_admin_permissions(),
    )
    async def _unload(self, ctx: SlashContext, cog_name: str) -> None:
        """Allow for the provided cog to be unloaded."""
        self.bot.unload(cog_name)
        await ctx.send(f'Cog "{cog_name}" has been successfully unloaded :+1:')


def setup(bot: ButtercupBot) -> None:
    """Set up the Admin cog."""
    bot.add_cog(AdminCommands(bot))


def teardown(bot: ButtercupBot) -> None:
    """Unload the Admin cog."""
    bot.remove_cog("AdminCommands")
