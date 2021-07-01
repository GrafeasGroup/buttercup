from datetime import datetime

import asyncpraw
from asyncprawcore import NotFound, Redirect
from discord import Embed
from discord.ext.commands import Cog
from discord_slash import SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_option

from buttercup.bot import ButtercupBot
from buttercup.strings import translation

i18n = translation()


def extract_sub_name(subreddit: str) -> str:
    """Extract the name of the sub without prefix."""
    if subreddit.startswith("/r/"):
        return subreddit[3:]
    if subreddit.startswith("r/"):
        return subreddit[2:]
    return subreddit


class Rules(Cog):
    def __init__(self, bot: ButtercupBot, reddit_api: asyncpraw.Reddit) -> None:
        """Initialize the Rules cog."""
        self.bot = bot
        self.reddit_api = reddit_api

    @cog_ext.cog_slash(
        name="rules",
        description="Get the rules of the specified subreddit.",
        options=[
            create_option(
                name="subreddit",
                description="The subreddit to get the rules of.",
                option_type=3,
                required=True,
            )
        ],
    )
    async def _rules(self, ctx: SlashContext, subreddit: str) -> None:
        """Get the rules of the specified subreddit."""
        # Send a quick response
        # We will edit this later with the actual content
        start = datetime.now()
        sub_name = extract_sub_name(subreddit)
        msg = await ctx.send(i18n["rules"]["getting_rules"].format(sub_name))

        sub = await self.reddit_api.subreddit(sub_name)

        embed = Embed(title=i18n["rules"]["embed_title"].format(sub_name))

        try:
            async for rule in sub.rules:
                # The value field is not allowed to be a blank string
                # So we just repeat the name of the rule if it is not provided
                embed.add_field(
                    name=rule.short_name,
                    value=rule.description or rule.short_name,
                    inline=False,
                )
        except Redirect:
            # Sometimes Reddit redirects to the subreddit search
            await msg.edit(content=i18n["rules"]["sub_not_found"].format(sub_name))
            return
        except NotFound:
            # Sometimes it throws a not found exception, e.g. if a character isn't allowed
            await msg.edit(content=i18n["rules"]["sub_not_found"].format(sub_name))
            return

        delay = datetime.now() - start
        await msg.edit(
            content=i18n["rules"]["embed_message"].format(
                f"{delay.microseconds // 1000} ms"
            ),
            embed=embed,
        )


def setup(bot: ButtercupBot) -> None:
    """Set up the Rules cog."""
    reddit_config = bot.config["Reddit"]
    reddit_api = asyncpraw.Reddit(
        client_id=reddit_config["client_id"],
        client_secret=reddit_config["client_secret"],
        user_agent=reddit_config["user_agent"],
    )
    bot.add_cog(Rules(bot=bot, reddit_api=reddit_api))


def teardown(bot: ButtercupBot) -> None:
    """Unload the Rules cog."""
    bot.remove_cog("Rules")