from blossom_wrapper import BlossomAPI
from discord import Embed
from discord.ext.commands import Cog
from discord_slash import SlashContext, cog_ext

from buttercup.bot import ButtercupBot
from buttercup.strings import translation

i18n = translation()


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
