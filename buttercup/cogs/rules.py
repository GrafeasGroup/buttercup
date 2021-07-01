from datetime import datetime
from typing import Callable, List, Optional
from xmlrpc.client import Boolean

import asyncpraw
from asyncpraw.models import Rule
from asyncprawcore import Forbidden, NotFound, Redirect
from discord import Embed
from discord.ext.commands import Cog
from discord_slash import SlashContext, cog_ext
from discord_slash.model import SlashMessage
from discord_slash.utils.manage_commands import create_option

from buttercup.bot import ButtercupBot
from buttercup.cogs.helpers import extract_sub_name, get_duration_str
from buttercup.strings import translation

i18n = translation()


PI_KEYWORDS = [
    "personal info",
    "identifying info",
    "censor",
    "redact",
    "blur",
    "obscure",
    "privacy",
    "dox",
    "witch hunt",
]


def contains_any(text: Optional[str], keywords: List[str]) -> bool:
    """Determine if the text contains any of the keywords."""
    return (
        False
        if text is None
        else any(word.casefold() in text.casefold() for word in keywords)
    )


def is_pi_rule(rule: Rule) -> bool:
    """Determine if the given rule is regarding personal information."""
    return contains_any(rule.short_name, PI_KEYWORDS) or contains_any(
        rule.description, PI_KEYWORDS
    )


async def send_rules_message(
    msg: SlashMessage,
    rules: List[Rule],
    subreddit: str,
    start_time: datetime,
    localization_key: str,
) -> None:
    """Send an embed containing the rules to the user."""
    embed = Embed(title=i18n[localization_key]["embed_title"].format(subreddit))

    if len(rules) == 0:
        await msg.edit(content=i18n[localization_key]["no_rules"].format(subreddit))
        return

    for rule in rules:
        # The value field is not allowed to be a blank string
        # So we just repeat the name of the rule if it is not provided
        embed.add_field(
            name=rule.short_name,
            value=rule.description or rule.short_name,
            inline=False,
        )

    await msg.edit(
        content=i18n["rules"]["embed_message"].format(get_duration_str(start_time)),
        embed=embed,
    )


class Rules(Cog):
    def __init__(self, bot: ButtercupBot, reddit_api: asyncpraw.Reddit) -> None:
        """Initialize the Rules cog."""
        self.bot = bot
        self.reddit_api = reddit_api

    async def _send_filtered_rules(
        self,
        ctx: SlashContext,
        subreddit: str,
        localization_key: str,
        filter_function: Callable[[Rule], Boolean],
    ) -> None:
        """Send the rules filtered by the given function to the user."""
        start = datetime.now()
        sub_name = extract_sub_name(subreddit)
        # Send a quick response
        # We will edit this later with the actual content
        msg = await ctx.send(i18n[localization_key]["getting_rules"].format(sub_name))
        try:
            sub = await self.reddit_api.subreddit(subreddit)
            return await send_rules_message(
                msg,
                [rule async for rule in sub.rules if filter_function(rule)],
                sub_name,
                start,
                localization_key,
            )
        except Redirect:
            # The subreddit does not exist
            await msg.edit(
                content=i18n[localization_key]["sub_not_found"].format(subreddit)
            )
        except NotFound:
            # A character in the sub name is not allowed
            await msg.edit(
                content=i18n[localization_key]["sub_not_found"].format(subreddit)
            )
        except Forbidden:
            # The subreddit is private
            await msg.edit(
                content=i18n[localization_key]["sub_private"].format(subreddit)
            )

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
        await self._send_filtered_rules(ctx, subreddit, "rules", lambda rule: True)

    @cog_ext.cog_slash(
        name="pirules",
        description="Get the rules of the specified subreddit "
        "regarding personal information.",
        options=[
            create_option(
                name="subreddit",
                description="The subreddit to get the PI rules of.",
                option_type=3,
                required=True,
            )
        ],
    )
    async def _pi_rules(self, ctx: SlashContext, subreddit: str) -> None:
        """Get the rules of the specified subreddit regarding personal information."""
        await self._send_filtered_rules(ctx, subreddit, "pi_rules", is_pi_rule)


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
