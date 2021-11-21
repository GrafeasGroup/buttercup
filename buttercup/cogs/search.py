from datetime import datetime

from blossom_wrapper import BlossomAPI, BlossomStatus
from discord import Embed
from discord.ext.commands import Cog
from discord_slash import SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_option

from buttercup.bot import ButtercupBot
from buttercup.cogs.helpers import BlossomException
from buttercup.strings import translation

i18n = translation()


class Search(Cog):
    def __init__(self, bot: ButtercupBot, blossom_api: BlossomAPI) -> None:
        """Initialize the Search cog."""
        self.bot = bot
        self.blossom_api = blossom_api

    @cog_ext.cog_slash(
        name="search",
        description="Searches for transcriptions that contain the given text.",
        options=[
            create_option(
                name="query",
                description="The text to search for (case-insensitive).",
                option_type=3,
                required=True,
            )
        ],
    )
    async def search(self, ctx: SlashContext, query: str) -> None:
        """Searches for transcriptions containing the given text."""
        start = datetime.now()

        # Send a first message to show that the bot is responsive.
        # We will edit this message later with the actual content.
        msg = await ctx.send(f"Searching for `{query}`...")

        response = self.blossom_api.get_transcription(
            text__icontains=query, url__isnull=False, ordering="-create_time"
        )
        if response.status != BlossomStatus.ok:
            raise BlossomException(response)
        results = response.data

        if len(results) == 0:
            await msg.edit(content=f"No results for `{query}` found.")
            return

        page_results = results[:5]
        description = ""

        for i, res in enumerate(page_results):
            description += f"{i + 1}. [Transcription]({res['url']})\n```\n"
            text: str = res["text"]
            lines = text.splitlines()
            pos = -1
            for line in lines:
                pos = line.casefold().find(query.casefold())
                if pos >= 0:
                    # Add the line where the word occurs
                    description += line + "\n"
                    # Underline the occurrence
                    description += " " * pos
                    description += "-" * len(query) + "\n"
            description += "```\n"

        await msg.edit(
            content=f"Here are your results!",
            embed=Embed(title=f"Results for `{query}`", description=description,),
        )


def setup(bot: ButtercupBot) -> None:
    """Set up the Stats cog."""
    cog_config = bot.config["Blossom"]
    email = cog_config.get("email")
    password = cog_config.get("password")
    api_key = cog_config.get("api_key")
    blossom_api = BlossomAPI(email=email, password=password, api_key=api_key)
    bot.add_cog(Search(bot=bot, blossom_api=blossom_api))


def teardown(bot: ButtercupBot) -> None:
    """Unload the Stats cog."""
    bot.remove_cog("Stats")
