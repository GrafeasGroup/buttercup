from discord.ext.commands import Cog
from discord_slash import SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_option
from urllib.parse import urlparse

from typing import Optional

from buttercup.bot import ButtercupBot
from blossom_wrapper import BlossomAPI, BlossomStatus


class Lookup(Cog):
    def __init__(self, bot: ButtercupBot, blossom: BlossomAPI) -> None:
        """Initialize the Lookup cog."""
        self.bot = bot
        self.blossom = blossom

    @staticmethod
    def _parse_reddit_url(reddit_url_str: str) -> Optional[str]:
        """
        Tries to parse and normalize the given Reddit URL.

        :returns: The normalized Reddit URL or None if the parsing failed.
        """
        parse_result = urlparse(reddit_url_str)

        if "reddit" not in parse_result.netloc:
            return None

        # On Blossom, all URLs end with a slash
        path = parse_result.path
        if not path.endswith("/"):
            path += "/"

        # Reformat URL in the format that Blossom uses
        return f"https://reddit.com{path}"

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

        normalized_url = Lookup._parse_reddit_url(reddit_url)

        if normalized_url is None:
            await ctx.send(f"I don't recognize '{reddit_url}' as valid Reddit URL. Please provide a link to "
                           "either a post on a r/TranscribersOfReddit, on a partner sub or a transcription.")
            return

        response = self.blossom.get_submission(url=normalized_url)
        data = response.data

        if response.status != BlossomStatus.ok or data is None or len(data) == 0:
            await ctx.send(f"""I couldn't find a post with URL "{normalized_url}", sorry.""")
            return

        submission = data[0]

        await ctx.send(f'I found your post!\n{submission["url"]}\n{submission["tor_url"]}')


def setup(bot: ButtercupBot) -> None:
    """Set up the Lookup cog."""
    cog_config = bot.config["Blossom"]
    email = cog_config.get("email")
    password = cog_config.get("password")
    api_key = cog_config.get("api_key")
    blossom = BlossomAPI(email=email, password=password, api_key=api_key)
    bot.add_cog(Lookup(bot, blossom))


def teardown(bot: ButtercupBot) -> None:
    """Unload the Lookup cog."""
    bot.remove_cog("Lookup")
