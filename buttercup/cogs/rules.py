from datetime import datetime
from typing import List, Optional

import asyncpraw
from asyncpraw.models import Rule
from asyncprawcore import Forbidden, NotFound, Redirect
from discord import Embed
from discord.ext.commands import Cog
from discord_slash import SlashContext, cog_ext
from discord_slash.model import SlashMessage
from discord_slash.utils.manage_commands import create_option

from buttercup.bot import ButtercupBot
from buttercup.cogs.helpers import get_duration_str
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


def extract_sub_name(subreddit: str) -> str:
    """Extract the name of the sub without prefix."""
    if subreddit.startswith("/r/"):
        return subreddit[3:]
    if subreddit.startswith("r/"):
        return subreddit[2:]
    return subreddit


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

    async def _get_rule_list(
        self, msg: SlashMessage, subreddit: str
    ) -> Optional[List[Rule]]:
        """Get the list of rules for the given subreddit."""
        try:
            sub = await self.reddit_api.subreddit(subreddit)
            return [rule async for rule in sub.rules]
        except Redirect:
            # The subreddit does not exist
            await msg.edit(content=i18n["rules"]["sub_not_found"].format(subreddit))
        except NotFound:
            # A character in the sub name is not allowed
            await msg.edit(content=i18n["rules"]["sub_not_found"].format(subreddit))
        except Forbidden:
            # The subreddit is private
            await msg.edit(content=i18n["rules"]["sub_private"].format(subreddit))

        return None

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
        start = datetime.now()
        sub_name = extract_sub_name(subreddit)
        # Send a quick response
        # We will edit this later with the actual content
        msg = await ctx.send(i18n["rules"]["getting_rules"].format(sub_name))

        rules = await self._get_rule_list(msg, subreddit)
        if rules is None:
            return

        await send_rules_message(msg, rules, subreddit, start, "rules")

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
        start = datetime.now()
        sub_name = extract_sub_name(subreddit)
        # Send a quick response
        # We will edit this later with the actual content
        msg = await ctx.send(i18n["pi_rules"]["getting_rules"].format(sub_name))

        rules = await self._get_rule_list(msg, subreddit)
        if rules is None:
            return
        rules = [rule for rule in rules if is_pi_rule(rule)]

        await send_rules_message(msg, rules, subreddit, start, "pi_rules")


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
