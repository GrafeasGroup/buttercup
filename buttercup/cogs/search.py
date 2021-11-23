import asyncio
from datetime import datetime
import re
from typing import Any, Dict, TypedDict, Optional, List

import pytz
from blossom_wrapper import BlossomAPI
from discord import Embed, Reaction, User
from discord.ext import commands
from discord.ext.commands import Cog
from discord_slash import SlashContext, cog_ext
from discord_slash.model import SlashMessage
from discord_slash.utils.manage_commands import create_option

from buttercup.bot import ButtercupBot
from buttercup.cogs.helpers import BlossomException, get_duration_str
from buttercup.strings import translation

i18n = translation()


# Unicode characters for control emojis
first_page_emoji = "\u23EE\uFE0F"  # Previous track button
previous_page_emoji = "\u25C0\uFE0F"  # Left triangle button
next_page_emoji = "\u25B6\uFE0F"  # Right triangle button
last_page_emoji = "\u23ED\uFE0F"  # Next track button


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


def get_transcription_source(transcription: Dict[str, Any]) -> str:
    """Try to determine the source (subreddit) of the transcription."""
    # E.g. https://reddit.com/r/thatHappened/comments/qzhtyb/the_more_you_read_the_less_believable_it_gets/hlmkuau/
    url: str = transcription["url"]
    return "r/" + url.split("/")[4]


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
    tr_source = get_transcription_source(result)
    description = f"{num}. [{tr_type} on {tr_source}]({result['url']})\n```\n"

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


class SearchCacheItem(TypedDict):
    # The query that the user searched for
    query: str
    # The current Discord page for the query
    cur_page: int
    # The id of the user who executed the query
    discord_user_id: str
    # The cached response data from previous requests
    response_data: Optional[Dict[str, Any]]
    # The offset of the results in the response data
    response_data_offset: int


class SearchCacheEntry(TypedDict):
    last_modified: datetime
    element: SearchCacheItem


class SearchCache:
    def __init__(self, size: int) -> None:
        self.size = size
        self.cache = {}

    def _clean(self) -> None:
        """Ensure that the cache size isn't exceeded."""
        if len(self.cache) > self.size:
            # Delete the oldest entry
            sorted_entries = sorted(
                self.cache.items(), key=lambda x: x[1]["last_modified"]
            )
            self.cache.pop(sorted_entries[0][0])

    def set(
        self,
        msg_id: str,
        entry: SearchCacheItem,
        time: datetime = datetime.now(tz=pytz.utc),
    ):
        self.cache[msg_id] = {
            "last_modified": time,
            "element": entry,
        }
        self._clean()

    def get(self, msg_id: str) -> Optional[SearchCacheItem]:
        item = self.cache.get(msg_id)
        if item is not None:
            return item["element"]
        else:
            return None


class Search(Cog):
    def __init__(self, bot: ButtercupBot, blossom_api: BlossomAPI) -> None:
        """Initialize the Search cog."""
        self.bot = bot
        self.blossom_api = blossom_api
        self.cache = SearchCache(10)

    async def _search_from_cache(
        self,
        msg: SlashMessage,
        start: datetime,
        cache_item: SearchCacheItem,
        page_mod: int,
    ) -> None:
        """Executes the search with the given cache."""
        # Clear previous control emojis
        await msg.clear_reactions()

        discord_page_size = 5

        discord_page = cache_item["cur_page"] + page_mod
        query = cache_item["query"]

        data = dict(
            text__icontains=cache_item["query"],
            url__isnull=False,
            ordering="-create_time",
            page_size=discord_page_size,
            page=discord_page + 1,
        )
        response = self.blossom_api.get(path="transcription", params=data)
        if response.status_code != 200:
            raise BlossomException(response)
        response_data = response.json()

        # Internal pagination of results (on Discord)
        total_discord_pages = response_data["count"] // discord_page_size

        if response_data["count"] == 0:
            await msg.edit(content=f"No results for `{query}` found.")
            return

        # Update the cache
        self.cache.set(
            msg.id,
            {
                "query": query,
                "cur_page": discord_page,
                "discord_user_id": cache_item["discord_user_id"],
                "response_data": response_data,
                "response_data_offset": 0,
            },
        )

        results_offset = discord_page * discord_page_size
        page_results: List[Dict[str, Any]] = response_data["results"]
        description = ""

        for i, res in enumerate(page_results):
            description += create_result_description(res, results_offset + i + 1, query)

        await msg.edit(
            content=f"Here are your results! ({get_duration_str(start)})",
            embed=Embed(
                title=f"Results for `{query}`", description=description,
            ).set_footer(
                text=f"Page {discord_page + 1}/{total_discord_pages} ({response_data['count']} results)"
            ),
        )

        emoji_controls = []

        if discord_page > 0:
            emoji_controls.append(first_page_emoji)
            emoji_controls.append(previous_page_emoji)
        if discord_page < total_discord_pages - 1:
            emoji_controls.append(next_page_emoji)
            emoji_controls.append(last_page_emoji)

        # Add control emojis to message
        await asyncio.gather(*[msg.add_reaction(emoji) for emoji in emoji_controls])

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

        # Simulate an initial cache item
        cache_item: SearchCacheItem = {
            "query": query,
            "cur_page": 0,
            "discord_user_id": ctx.author_id,
            "response_data": None,
            "response_data_offset": 0,
        }

        await self._search_from_cache(msg, start, cache_item, 0)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: Reaction, user: User):
        start = datetime.now()
        msg: SlashMessage = reaction.message
        cache_item = self.cache.get(msg.id)
        if cache_item is None:
            return

        # Only process controls by the user who executed the query
        if cache_item["discord_user_id"] != user.id:
            return

        discord_page = cache_item["cur_page"]
        emoji = reaction.emoji

        if emoji == first_page_emoji and discord_page != 0:
            page_mod = -cache_item["cur_page"]
        elif emoji == previous_page_emoji and discord_page != 0:
            page_mod = -1
        elif emoji == next_page_emoji:
            page_mod = 1
        elif emoji == last_page_emoji:
            page_mod = 1
        else:
            # No control emoji
            return

        await self._search_from_cache(msg, start, cache_item, page_mod)


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
