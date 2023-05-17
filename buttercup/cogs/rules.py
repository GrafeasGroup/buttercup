from datetime import datetime
from typing import Callable, List, Optional
from xmlrpc.client import Boolean

import asyncpraw
import pytz
from asyncpraw.models import Rule
from asyncprawcore import Forbidden, NotFound, Redirect
from discord import Color, Embed
from discord.ext.commands import Cog
from discord_slash import SlashContext, cog_ext
from discord_slash.model import SlashMessage
from discord_slash.utils.manage_commands import create_option

from buttercup.bot import ButtercupBot
from buttercup.cogs.helpers import (
    extract_sub_name,
    get_duration_str,
    join_items_with_and,
)
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
    return False if text is None else any(word.casefold() in text.casefold() for word in keywords)


def is_pi_rule(rule: Rule) -> bool:
    """Determine if the given rule is regarding personal information."""
    return contains_any(rule.short_name, PI_KEYWORDS) or contains_any(rule.description, PI_KEYWORDS)


async def send_rules_message(
    msg: SlashMessage,
    rules: List[Rule],
    subreddit: str,
    start_time: datetime,
    localization_key: str,
) -> None:
    """Send an embed containing the rules to the user."""
    embed = Embed(title=i18n[localization_key]["embed_title"].format(subreddit))

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
        start = datetime.now(tz=pytz.UTC)
        sub_name = extract_sub_name(subreddit)
        # Send a quick response
        # We will edit this later with the actual content
        msg = await ctx.send(i18n[localization_key]["getting_rules"].format(sub_name))
        try:
            # Get the subreddit and rules
            sub = await self.reddit_api.subreddit(subreddit)
            rules = [rule async for rule in sub.rules]
            if len(rules) == 0:
                await msg.edit(content=i18n[localization_key]["no_rules"].format(subreddit))
                return
            # Filter out relevant rules
            filtered_rules = [rule for rule in rules if filter_function(rule)]
            if len(filtered_rules) == 0:
                await msg.edit(content=i18n[localization_key]["no_filter_rules"].format(subreddit))
                return

            await send_rules_message(
                msg,
                filtered_rules,
                sub_name,
                start,
                localization_key,
            )
            return
        except Redirect:
            # The subreddit does not exist
            await msg.edit(content=i18n[localization_key]["sub_not_found"].format(subreddit))
        except NotFound:
            # A character in the sub name is not allowed
            await msg.edit(content=i18n[localization_key]["sub_not_found"].format(subreddit))
        except Forbidden:
            # The subreddit is private
            await msg.edit(content=i18n[localization_key]["sub_private"].format(subreddit))

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
        description="Get the rules of the specified subreddit " "regarding personal information.",
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

    async def _get_partner_list(self) -> List[str]:
        """Get a list of subreddits that are partnered with us."""
        # Retrieve the partners from the subreddit wiki
        sub = await self.reddit_api.subreddit("TranscribersOfReddit")
        partner_page = await sub.wiki.get_page("subreddits")
        partners: List[str] = partner_page.content_md.splitlines()
        # Sort the list alphabetically
        partners.sort(key=lambda x: x.casefold())
        return partners

    @cog_ext.cog_slash(
        name="partner",
        description="Get the list of partner subreddits.",
        options=[
            create_option(
                name="subreddit",
                description="Determine if the subreddit is already partnered with us.",
                option_type=3,
                required=False,
            )
        ],
    )
    async def _partner(self, ctx: SlashContext, subreddit: Optional[str] = None) -> None:
        """Get the list of all our partner subreddits."""
        start = datetime.now(tz=pytz.UTC)

        if subreddit is None:
            msg = await ctx.send(i18n["partner"]["getting_partner_list"])
        else:
            msg = await ctx.send(
                i18n["partner"]["getting_partner_status"].format(subreddit=subreddit)
            )

        partners = await self._get_partner_list()

        if subreddit is None:
            partner_str = join_items_with_and(partners)
            await msg.edit(
                content=i18n["partner"]["embed_partner_list_message"].format(
                    duration=get_duration_str(start)
                ),
                embed=Embed(
                    title=i18n["partner"]["embed_partner_list_title"],
                    description=i18n["partner"]["embed_partner_list_description"].format(
                        count=len(partners), partner_list=partner_str
                    ),
                ),
            )
        else:
            sub = await self.reddit_api.subreddit(subreddit)
            is_private = False

            try:
                await sub.load()
            except Redirect:
                # The subreddit does not exist
                await msg.edit(content=i18n["partner"]["sub_not_found"].format(subreddit=subreddit))
                return
            except NotFound:
                # A character in the sub name is not allowed
                await msg.edit(content=i18n["partner"]["sub_not_found"].format(subreddit=subreddit))
                return
            except Forbidden:
                # The subreddit is private
                is_private = True

            is_partner = subreddit.casefold() in [partner.casefold() for partner in partners]
            message = i18n["partner"]["embed_partner_status_message"].format(
                subreddit=subreddit, duration=get_duration_str(start)
            )

            status_message = (
                i18n["partner"]["status_yes_message"].format(subreddit=subreddit)
                if is_partner
                else i18n["partner"]["status_no_message"].format(subreddit=subreddit)
            )

            if is_private:
                status_message += i18n["partner"]["private_message"]
            else:
                status_message += "\n" + i18n["partner"]["sub_description"].format(
                    description=sub.public_description
                )

            color = (
                Color.red() if not is_partner else Color.orange() if is_private else Color.green()
            )

            await msg.edit(
                content=message,
                embed=Embed(
                    title=i18n["partner"]["embed_partner_status_title"].format(subreddit=subreddit),
                    description=i18n["partner"]["embed_partner_status_description"].format(
                        status=status_message
                    ),
                    color=color,
                ),
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
