import uuid

from discord.errors import DiscordException
from discord.ext import commands

from buttercup import logger
from buttercup.bot import ButtercupBot


class Handlers(commands.Cog):
    @commands.Cog.listener()
    async def on_command(self, ctx: commands.Context) -> None:
        """Log when a command is ran."""
        logger.info(f'Command Invoked: "{ctx.message.content}"', ctx)

    @commands.Cog.listener()
    async def on_command_completion(self, ctx: commands.Context) -> None:
        """Log that the command is completed."""
        logger.info("Command Completed", ctx)

    @commands.Cog.listener()
    async def on_slash_command_error(
        self, ctx: commands.Context, error: DiscordException
    ) -> None:
        """Log that a command has errored and provide the user with feedback."""
        if isinstance(error, commands.CheckFailure):
            logger.warning("An unauthorized Command was performed.", ctx)
            await ctx.send(
                "You are not authorized to use this command. "
                "This incident will be reported"
            )
        else:
            tracker_id = uuid.uuid4()
            logger.warning(f"[{tracker_id}] {type(error).__name__}: {str(error)}", ctx)
            await ctx.send(
                f"[{tracker_id}] Something went wrong, "
                "please contact a moderator with the provided ID."
            )


def setup(bot: ButtercupBot) -> None:
    """Set up the Handlers cog."""
    bot.add_cog(Handlers())


def teardown(bot: ButtercupBot) -> None:
    """Unload the Handlers cog."""
    bot.remove_cog("Handlers")
