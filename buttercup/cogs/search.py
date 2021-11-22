from datetime import datetime
import re
from typing import Any, Dict, List

from blossom_wrapper import BlossomAPI, BlossomStatus
from discord import Embed
from discord.ext.commands import Cog
from discord_slash import SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_option

from buttercup.bot import ButtercupBot
from buttercup.cogs.helpers import BlossomException
from buttercup.strings import translation

i18n = translation()


header_regex = re.compile(
    r"^\s*\*(?P<format>\w+)\s*Transcription:?(?:\s*(?P<type>[\w ]+))?\*", re.IGNORECASE
)


def get_transcription_type(transcription: Dict[str, Any]) -> str:
    """Try to determine the type of the transcription."""
    text: str = transcription["text"]
    header = text.split("---")[0]

    match = header_regex.search(header)
    if match is None:
        return "Post"

    tr_format = match.group("format")
    if tr_format:
        tr_format = tr_format.strip()
    tr_type = match.group("type")
    if tr_type:
        tr_type = tr_type.strip()

    return tr_type or tr_format


def format_query_occurrence(line: str, line_num: int, pos: int, query: str) -> str:
    """Format a single occurrence of the query."""
    max_context = 20
    line_num_str = "L" + str(line_num) + ": "
    before_context = line[:pos]
    if len(before_context) > max_context:
        before_context = "..." + before_context[-max_context:]
    offset = len(line_num_str) + len(before_context)
    occurrence = line[pos : pos + len(query)]
    after_context = line[pos + len(query) :]
    if len(after_context) > max_context:
        after_context = after_context[:max_context] + "..."

    # Show the occurrence with context
    context = f"{line_num_str}{before_context}{occurrence}{after_context}\n"
    # Underline the occurrence
    underline = " " * offset + "-" * len(query) + "\n"
    return context + underline


def create_result_description(result: Dict[str, Any], num: int, query: str) -> str:
    """Crate a description for the given result."""
    transcription: str = result["text"]
    total_occurrences = transcription.casefold().count(query.casefold())
    tr_type = get_transcription_type(result)
    description = f"{num}. [{tr_type}]({result['url']}) ({total_occurrences} occurrence(s))\n```\n"

    # The maximum number of occurrences to show
    max_occurrences = 4
    cur_count = 0

    for i, line in enumerate(transcription.splitlines()):
        start = 0
        pos = line.casefold().find(query.casefold())
        while pos >= 0 and cur_count < max_occurrences:
            # Add the line where the word occurs
            description += format_query_occurrence(line, i + 1, pos, query)
            # Move to the next occurrence in the line
            cur_count += 1
            start = pos + len(query)
            pos = line.casefold().find(query.casefold(), start)

        if cur_count >= max_occurrences:
            break

    description += "```\n"
    if cur_count < total_occurrences:
        description += (
            f"... and {total_occurrences - cur_count} more occurrence(s).\n\n"
        )
    return description


class Search(Cog):
    def __init__(self, bot: ButtercupBot, blossom_api: BlossomAPI) -> None:
        """Initialize the Search cog."""
        self.bot = bot
        self.blossom_api = blossom_api

    @cog_ext.cog_slash(
        name="search",
        description="Searches for transcriptions that contain the given text.",
        options=[
            create_option(
                name="query",
                description="The text to search for (case-insensitive).",
                option_type=3,
                required=True,
            )
        ],
    )
    async def search(self, ctx: SlashContext, query: str) -> None:
        """Searches for transcriptions containing the given text."""
        start = datetime.now()

        # Send a first message to show that the bot is responsive.
        # We will edit this message later with the actual content.
        msg = await ctx.send(f"Searching for `{query}`...")

        response = self.blossom_api.get_transcription(
            text__icontains=query, url__isnull=False, ordering="-create_time"
        )
        if response.status != BlossomStatus.ok:
            raise BlossomException(response)
        results = response.data

        if len(results) == 0:
            await msg.edit(content=f"No results for `{query}` found.")
            return

        page_results = results[:5]
        description = ""

        for i, res in enumerate(page_results):
            description += create_result_description(res, i + 1, query)

        await msg.edit(
            content=f"Here are your results!",
            embed=Embed(title=f"Results for `{query}`", description=description,),
        )


def setup(bot: ButtercupBot) -> None:
    """Set up the Stats cog."""
    cog_config = bot.config["Blossom"]
    email = cog_config.get("email")
    password = cog_config.get("password")
    api_key = cog_config.get("api_key")
    blossom_api = BlossomAPI(email=email, password=password, api_key=api_key)
    bot.add_cog(Search(bot=bot, blossom_api=blossom_api))


def teardown(bot: ButtercupBot) -> None:
    """Unload the Stats cog."""
    bot.remove_cog("Stats")
