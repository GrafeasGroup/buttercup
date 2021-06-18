import asyncpraw
from asyncprawcore import Redirect, NotFound
from discord import Embed
from discord.ext.commands import Cog
from discord_slash import SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_option

from buttercup.bot import ButtercupBot


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
        name="rules", description="Get the rules of the specified subreddit.",
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
        sub_name = extract_sub_name(subreddit)
        msg = await ctx.send(f"Getting the rules for r/{sub_name}...")

        sub = await self.reddit_api.subreddit(sub_name)

        embed = Embed(title=f"Rules for r/{sub_name}")

        try:
            async for rule in sub.rules:
                # The value field is not allowed to be a blank string
                # So we just repeat the name of the rule if it is not provided
                embed.add_field(name=rule.short_name, value=rule.description or rule.short_name, inline=False)
        except Redirect:
            # Sometimes Reddit redirects to the subreddit search
            await msg.edit(content=f"I couldn't find a sub named r/{sub_name}. Please check the spelling.")
            return
        except NotFound:
            # Sometimes it throws a not found exception, e.g. if a character isn't allowed
            await msg.edit(content=f"I couldn't find a sub named r/{sub_name}. Please check the spelling.")
            return

        await msg.edit(content="Here are the rules!", embed=embed)


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
