from datetime import datetime

from blossom_wrapper import BlossomAPI
from discord import Color, Embed
from discord.ext.commands import Cog
from discord_slash import SlashContext, cog_ext

from buttercup.bot import ButtercupBot


class Ping(Cog):
    def __init__(self, bot: ButtercupBot, blossom_api: BlossomAPI) -> None:
        """Initialize the Ping cog."""
        self.bot = bot
        self.blossom_api = blossom_api

    @cog_ext.cog_slash(
        name="ping", description="Ping the bot to find out if it is responsive.",
    )
    async def _ping(self, ctx: SlashContext) -> None:
        """Ping the bot to find out if it is responsive."""
        success_color = Color.green()
        failure_color = Color.red()

        embed = Embed(color=success_color, title="Pong!")

        msg = await ctx.send(embed=embed)

        # Also ping the blossom server
        start = datetime.now()
        response = self.blossom_api.get(path="ping/")
        server_delay = datetime.now() - start
        if response.status_code == 200:
            embed.add_field(
                name="Server", value=f"{server_delay.microseconds / 1000} ms"
            )
        else:
            # For some reason, the color is read-only, so we need to make a new embed
            embed = Embed(color=failure_color, title="Pong!")
            embed.add_field(
                name="Server", value=f"Error: Status code {response.status_code}"
            )

        await msg.edit(embed=embed)


def setup(bot: ButtercupBot) -> None:
    """Set up the Ping cog."""
    cog_config = bot.config["Blossom"]
    email = cog_config.get("email")
    password = cog_config.get("password")
    api_key = cog_config.get("api_key")
    blossom_api = BlossomAPI(email=email, password=password, api_key=api_key)
    bot.add_cog(Ping(bot=bot, blossom_api=blossom_api))


def teardown(bot: ButtercupBot) -> None:
    """Unload the Ping cog."""
    bot.remove_cog("Ping")
