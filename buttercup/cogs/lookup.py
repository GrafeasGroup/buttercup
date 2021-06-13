from discord.ext.commands import Cog
from discord_slash import SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_option

from buttercup.bot import ButtercupBot


class Lookup(Cog):
    def __init__(self, bot: ButtercupBot) -> None:
        """Initialize the Lookup cog."""
        self.bot = bot

    @cog_ext.cog_slash(
        name="lookup",
        description="Find a post given a Reddit URL.",
        options=[
            create_option(
                name="reddit_url",
                description="A Reddit URL, either to the submission on ToR, the partner sub or the transcription.",
                option_type=3,
                required=True,
            )
        ],
    )
    async def _lookup(self, ctx: SlashContext, reddit_url: str) -> None:
        """Look up the post with the given URL."""

        await ctx.send(f'Looking up post with URL "{reddit_url}"')


def setup(bot: ButtercupBot) -> None:
    """Set up the Lookup cog."""
    bot.add_cog(Lookup(bot))


def teardown(bot: ButtercupBot) -> None:
    """Unload the Lookup cog."""
    bot.remove_cog("Lookup")
