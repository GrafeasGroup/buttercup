import asyncio
import math
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict

import pytz
from blossom_wrapper import BlossomAPI
from dateutil import parser
from discord import Embed, Forbidden, Reaction, User
from discord.ext import commands
from discord.ext.commands import Cog
from discord_slash import SlashContext, cog_ext
from discord_slash.model import SlashMessage
from discord_slash.utils.manage_commands import create_option

from buttercup.bot import ButtercupBot
from buttercup.cogs.helpers import (
    BlossomException,
    BlossomUser,
    get_discord_time_str,
    get_duration_str,
    get_initial_username,
    get_transcription_source,
    get_user,
    get_username,
    parse_time_constraints,
)
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


def format_query_occurrence(line: str, line_num: int, pos: int, query: str) -> str:
    """Format a single occurrence of the query."""
    # The maximum amount of characters that fit in a single line
    # Within an embedded code block
    max_characters = 56
    line_num_str = "L" + str(line_num) + ": "

    # The number of chars that we can use to display context to the result
    remaining_chars = max_characters - len(query) - len(line_num_str)

    left_context = line[:pos]
    right_context = line[pos + len(query) :]

    left_chars = math.ceil(remaining_chars / 2)
    right_chars = math.floor(remaining_chars / 2)

    # Give each side as much context as possible
    if len(left_context) < left_chars:
        right_chars += left_chars - len(left_context)
    elif len(right_context) < right_chars:
        left_chars += right_chars - len(right_context)

    # Truncate if necessary
    if len(left_context) > left_chars:
        left_context = "..." + left_context[-left_chars + 3 :]

    if len(right_context) > right_chars:
        right_context = right_context[: right_chars - 3] + "..."

    # Calculate the offset of the query occurrence
    offset = len(line_num_str) + len(left_context)
    # Extract the actual occurrence (Might have different capitalization)
    occurrence = line[pos : pos + len(query)]

    # Show the occurrence with context
    context = f"{line_num_str}{left_context}{occurrence}{right_context}\n"
    # Underline the occurrence
    underline = " " * offset + "-" * len(query) + "\n"
    return context + underline


def create_result_description(result: Dict[str, Any], num: int, query: str) -> str:
    """Crate a description for the given result."""
    transcription: str = result["text"]
    total_occurrences = transcription.casefold().count(query.casefold())
    # Determine meta info about the post/transcription
    tr_type = get_transcription_type(result)
    tr_source = get_transcription_source(result)
    time = parser.parse(result["create_time"])
    description = (
        i18n["search"]["description"]["item"].format(
            num=num,
            tr_type=tr_type,
            tr_source=tr_source,
            url=result["url"],
            timestamp=get_discord_time_str(time, "R"),
        )
        # Start code block for occurrences
        + "\n```\n"
    )

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
            i18n["search"]["description"]["more_occurrences"].format(
                count=total_occurrences - cur_count
            )
            + "\n\n"
        )
    return description


async def clear_reactions(msg: SlashMessage) -> None:
    """Clear previously set control emojis."""
    if len(msg.reactions) > 0:
        try:
            await msg.clear_reactions()
        except Forbidden:
            # The bot is not allowed to clear reactions
            # This can happen when the command is executed in a DM
            # We need to clear the reactions manually
            for emoji in msg.reactions:
                await msg.remove_reaction(emoji, msg.author)


class SearchCacheItem(TypedDict):
    # The query that the user searched for
    query: str
    # The user that the search is restricted to
    user: Optional[BlossomUser]
    # The time restriction for the search
    after_time: Optional[datetime]
    before_time: Optional[datetime]
    time_str: str
    # The current Discord page for the query
    cur_page: int
    # The id of the user who executed the query
    discord_user_id: str
    # The cached response data from previous requests
    response_data: Optional[Dict[str, Any]]
    # The page of the cached response data
    request_page: int


class SearchCacheEntry(TypedDict):
    last_modified: datetime
    element: SearchCacheItem


class SearchCache:
    def __init__(self, capacity: int) -> None:
        """Initialize a new cache."""
        self.capacity = capacity
        self.cache = {}

    def _clean(self) -> None:
        """Ensure that the cache capacity isn't exceeded."""
        if len(self.cache) > self.capacity:
            # Delete the oldest entry
            sorted_entries = sorted(self.cache.items(), key=lambda x: x[1]["last_modified"])
            self.cache.pop(sorted_entries[0][0])

    def set(
        self,
        msg_id: str,
        entry: SearchCacheItem,
        time: datetime = datetime.now(tz=pytz.utc),
    ) -> None:
        """Set an entry of the cache.

        :param msg_id: The ID of the message where the search results are displayed.
        :param entry: The cache item for the corresponding message.
        :param time: The time when the message was last interacted with.
            This should only be set directly in tests, keep it as the default value.
        """
        self.cache[msg_id] = {
            "last_modified": time,
            "element": entry,
        }
        # Make sure the capacity is not exceeded
        self._clean()

    def get(self, msg_id: str) -> Optional[SearchCacheItem]:
        """Get the cache entry for the corresponding message.

        Note that this might return no message, even if it has been added at some point.
        When the capacity of the cache is exceeded, old items get deleted.
        """
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
        # Size of a search result page on Discord
        self.discord_page_size = 5
        # Size of the fetched result pages from Blossom
        self.request_page_size = self.discord_page_size * 5

    async def _search_from_cache(
        self,
        msg: SlashMessage,
        start: datetime,
        cache_item: SearchCacheItem,
        page_mod: int,
    ) -> None:
        """Execute the search with the given cache."""
        # Clear previous control emojis
        await clear_reactions(msg)

        discord_page = cache_item["cur_page"] + page_mod
        query = cache_item["query"]
        user = cache_item["user"]
        user_id = user["id"] if user else None
        after_time = cache_item["after_time"]
        before_time = cache_item["before_time"]
        time_str = cache_item["time_str"]

        from_str = after_time.isoformat() if after_time else None
        until_str = before_time.isoformat() if before_time else None

        request_page = (discord_page * self.discord_page_size) // self.request_page_size

        if not cache_item["response_data"] or request_page != cache_item["request_page"]:
            # A new request has to be made
            data = {
                "text__icontains": cache_item["query"],
                "author": user_id,
                "create_time__gte": from_str,
                "create_time__lte": until_str,
                "url__isnull": False,
                "ordering": "-create_time",
                "page_size": self.request_page_size,
                "page": request_page + 1,
            }
            response = self.blossom_api.get(path="transcription", params=data)
            if response.status_code != 200:
                raise BlossomException(response)
            response_data = response.json()
        else:
            response_data = cache_item["response_data"]

        if response_data["count"] == 0:
            await msg.edit(
                content=i18n["search"]["no_results"].format(
                    query=query,
                    user=get_username(user),
                    time_str=time_str,
                    duration_str=get_duration_str(start),
                )
            )
            return

        # Only cache the result if the user can change pages
        if response_data["count"] > self.discord_page_size:
            # Update the cache
            self.cache.set(
                msg.id,
                {
                    "query": query,
                    "user": cache_item["user"],
                    "after_time": after_time,
                    "before_time": before_time,
                    "time_str": time_str,
                    "cur_page": discord_page,
                    "discord_user_id": cache_item["discord_user_id"],
                    "response_data": response_data,
                    "request_page": request_page,
                },
            )

        # Calculate the offset within the response
        # The requested pages are larger than the pages displayed on Discord
        request_offset = request_page * self.request_page_size
        discord_offset = discord_page * self.discord_page_size
        result_offset = discord_offset - request_offset
        page_results: List[Dict[str, Any]] = response_data["results"][
            result_offset : result_offset + self.discord_page_size
        ]
        description = ""

        for i, res in enumerate(page_results):
            description += create_result_description(res, discord_offset + i + 1, query)

        total_discord_pages = math.ceil(response_data["count"] / self.discord_page_size)

        await msg.edit(
            content=i18n["search"]["embed_message"].format(
                query=query,
                user=get_username(user),
                time_str=time_str,
                duration_str=get_duration_str(start),
            ),
            embed=Embed(
                title=i18n["search"]["embed_title"].format(query=query, user=get_username(user)),
                description=description,
            ).set_footer(
                text=i18n["search"]["embed_footer"].format(
                    cur_page=discord_page + 1,
                    total_pages=total_discord_pages,
                    total_results=response_data["count"],
                ),
            ),
        )

        emoji_controls = []

        # Determine which controls are appropriate
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
            ),
            create_option(
                name="username",
                description="The user to restrict the search to. "
                "Defaults to the user executing the command.",
                option_type=3,
                required=False,
            ),
            create_option(
                name="after",
                description="Only show transcriptions after this date.",
                option_type=3,
                required=False,
            ),
            create_option(
                name="before",
                description="Only show transcriptions before this date.",
                option_type=3,
                required=False,
            ),
        ],
    )
    async def search(
        self,
        ctx: SlashContext,
        query: str,
        username: str = "me",
        after: Optional[str] = None,
        before: Optional[str] = None,
    ) -> None:
        """Search for transcriptions containing the given text."""
        start = datetime.now(tz=pytz.UTC)
        after_time, before_time, time_str = parse_time_constraints(after, before)

        # Send a first message to show that the bot is responsive.
        # We will edit this message later with the actual content.
        msg = await ctx.send(
            i18n["search"]["getting_search"].format(
                query=query, user=get_initial_username(username, ctx), time_str=time_str
            )
        )

        user = get_user(username, ctx, self.blossom_api)

        # Simulate an initial cache item
        cache_item: SearchCacheItem = {
            "query": query,
            "user": user,
            "after_time": after_time,
            "before_time": before_time,
            "time_str": time_str,
            "cur_page": 0,
            "discord_user_id": ctx.author_id,
            "response_data": None,
            "request_page": 0,
        }

        # Display the first page
        await self._search_from_cache(msg, start, cache_item, 0)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: Reaction, user: User) -> None:
        """Process reactions to go through the result pages."""
        start = datetime.now(tz=pytz.UTC)
        msg: SlashMessage = reaction.message
        cache_item = self.cache.get(msg.id)
        if cache_item is None:
            return

        # Only process controls by the user who executed the query
        if cache_item["discord_user_id"] != user.id:
            return

        discord_page = cache_item["cur_page"]
        emoji = reaction.emoji

        if response_data := cache_item["response_data"]:
            last_page = math.ceil(response_data["count"] / self.discord_page_size) - 1
        else:
            last_page = 0

        # Determine which action should be executed
        if emoji == first_page_emoji and discord_page > 0:
            page_mod = -cache_item["cur_page"]
        elif emoji == previous_page_emoji and discord_page > 0:
            page_mod = -1
        elif emoji == next_page_emoji and discord_page < last_page:
            page_mod = 1
        elif emoji == last_page_emoji and discord_page < last_page:
            page_mod = last_page - discord_page
        else:
            # Invalid control emoji
            return

        # Display the new page
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
