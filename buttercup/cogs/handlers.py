import traceback
import uuid

from discord.errors import DiscordException
from discord.ext import commands

from buttercup import logger
from buttercup.bot import ButtercupBot
from buttercup.cogs.helpers import (
    BlossomException,
    InvalidArgumentException,
    NewUserException,
    NoUsernameException,
    TimeParseError,
    UserNotFoundException,
)
from buttercup.strings import translation

i18n = translation()


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
        trace = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )

        if isinstance(error, NoUsernameException):
            logger.warning("Command executed without providing a username.", ctx)
            await ctx.send(i18n["handlers"]["no_username"])
        elif isinstance(error, UserNotFoundException):
            logger.warning(f"User '{error.username}' not found.", ctx)
            await ctx.send(
                i18n["handlers"]["user_not_found"].format(user=error.username)
            )
        elif isinstance(error, NewUserException):
            logger.warning(f"User '{error.username}' hasn't transcribed yet.", ctx)
            await ctx.send(i18n["handlers"]["new_user"].format(user=error.username))
        elif isinstance(error, TimeParseError):
            logger.warning(
                f"Command executed with an invalid time string '{error.time_str}'.", ctx
            )
            await ctx.send(
                i18n["handlers"]["invalid_time_str"].format(time_str=error.time_str)
            )
        elif isinstance(error, InvalidArgumentException):
            logger.warning(
                f"Invalid value '{error.value}' for argument '{error.argument}'.", ctx
            )
            await ctx.send(
                i18n["handlers"]["invalid_argument"].format(
                    argument=error.argument, value=error.value
                )
            )
        elif isinstance(error, BlossomException):
            tracker_id = uuid.uuid4()
            logger.warning(
                f"[{tracker_id}] Blossom Error: {error.status}\n{error.data}", ctx
            )
            await ctx.send(
                i18n["handlers"]["blossom_error"].format(tracker_id=tracker_id)
            )
        else:
            tracker_id = uuid.uuid4()
            logger.warning(
                f"[{tracker_id}] {type(error).__name__}: {str(error)}\n{trace}", ctx
            )
            await ctx.send(
                i18n["handlers"]["unknown_error"].format(tracker_id=tracker_id)
            )


def setup(bot: ButtercupBot) -> None:
    """Set up the Handlers cog."""
    bot.add_cog(Handlers())


def teardown(bot: ButtercupBot) -> None:
    """Unload the Handlers cog."""
    bot.remove_cog("Handlers")
