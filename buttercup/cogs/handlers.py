from discord.ext import commands
from discord.errors import DiscordException

from buttercup import logger
from buttercup.bot import ButtercupBot
from buttercup.strings import translation


class Handlers(commands.Cog):
    def __init__(self):
        pass

    @commands.Cog.listener()
    async def on_command(self, ctx: commands.Context) -> None:
        logger.info(f"Command Invoked: \"{ctx.message.content}\"", ctx)

    @commands.Cog.listener()
    async def on_command_completion(self, ctx: commands.Context) -> None:
        logger.info("Command Completed", ctx)

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: DiscordException) -> None:
        logger.warning(f"{type(error).__name__}: {str(error)}", ctx)

        if isinstance(error, commands.CheckFailure):
            await ctx.send("You are not authorized to use this command.")
        else:
            await ctx.send("Something went wrong, please contact a moderator.")


def setup(bot: ButtercupBot) -> None:
    """Set up the Handlers cog."""
    bot.add_cog(Handlers())


def teardown(bot: ButtercupBot) -> None:
    """Unload the Handlers cog."""
    bot.remove_cog("Handlers")
