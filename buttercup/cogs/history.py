import io
import math
from datetime import datetime
from typing import List, Optional

import matplotlib.pyplot as plt
from blossom_wrapper import BlossomAPI, BlossomStatus
from dateutil import parser
from discord import File
from discord.ext.commands import Cog
from discord_slash import SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_option
from requests import HTTPError

from buttercup.bot import ButtercupBot
from buttercup.cogs import ranks
from buttercup.cogs.helpers import extract_username, get_progress_bar, get_duration_str
from buttercup.strings import translation


i18n = translation()


def get_data_granularity(total_gamma: int) -> str:
    """Determine granularity of the graph.

    It should be as detailed as possible, but only require 1 API call in the best case.
    """
    # TODO: Adjust this when the Blossom dates have been fixed
    if total_gamma <= 500:
        return "none"
    if total_gamma <= 1000:
        return "hour"
    elif total_gamma <= 5000:
        return "day"
    elif total_gamma <= 10000:
        return "week"
    elif total_gamma <= 50000:
        return "month"
    return "year"


def add_rank_lines(ax: plt.Axes, gamma: int) -> plt.Axes:
    """Adds the rank lines to the given axes."""
    # Show ranks when you are close to them already
    threshold_factor = 0.7
    for rank_name in ranks:
        rank = ranks[rank_name]
        if gamma >= rank["threshold"] * threshold_factor:
            ax.axhline(y=rank["threshold"], color=rank["color"], zorder=-1)
    return ax


def create_file_from_figure(
    fig: plt.Figure, file_name: str
) -> File:
    """Create a Discord file containing the figure."""

    history_plot = io.BytesIO()

    fig.savefig(history_plot, format="png")
    history_plot.seek(0)
    plt.close(fig)

    return File(history_plot, file_name)


class History(Cog):
    def __init__(self, bot: ButtercupBot, blossom_api: BlossomAPI) -> None:
        """Initialize the History cog."""
        self.bot = bot
        self.blossom_api = blossom_api

    @cog_ext.cog_slash(
        name="history",
        description="Display the history graph.",
        options=[
            create_option(
                name="user_1",
                description="The user to display the history graph for.",
                option_type=3,
                required=False,
            )
        ],
    )
    async def _history(self, ctx: SlashContext, user_1: Optional[str] = None) -> None:
        """Find the post with the given URL."""
        # Give a quick response to let the user know we're working on it
        # We'll later edit this message with the actual content
        start = datetime.now()
        page_size = 500
        msg = await ctx.send("Creating the history graph...")

        username_1 = user_1 or extract_username(ctx.author.display_name)

        # First, get the total gamma for the user
        user_1_response = self.blossom_api.get_user(username_1)
        if user_1_response.status != BlossomStatus.ok:
            await msg.edit(content=f"Failed to get the data for user {username_1}!")
            return
        user_1_gamma = user_1_response.data["gamma"]
        user_1_id = user_1_response.data["id"]

        await msg.edit(
            content=f"Creating the history graph... "
            f"{get_progress_bar(0, user_1_gamma, display_count=True)}"
        )

        time_frame = get_data_granularity(user_1_gamma)

        user_1_times = []
        user_1_values = []
        page = 1
        gamma_offset = 0
        response = self.blossom_api.get(
            f"volunteer/{user_1_id}/rate",
            params={"page": page, "page_size": page_size, "time_frame": time_frame},
        )

        while response.status_code == 200:
            rate_data = response.json()["results"]

            for data in rate_data:
                date = parser.parse(data["date"])
                count = data["count"]
                gamma_offset += count

                user_1_times.append(date)
                user_1_values.append(gamma_offset)

            await msg.edit(
                content=f"Creating the history graph... "
                f"{get_progress_bar(gamma_offset, user_1_gamma, display_count=True)}"
            )

            # Continue with the next page
            page += 1
            response = self.blossom_api.get(
                f"volunteer/{user_1_id}/rate",
                params={"page": page, "page_size": page_size, "time_frame": time_frame},
            )

        if response.status_code == 404:
            # Hack: The next page is not available anymore, so we reached the end

            # Add an up-to-date entry for the current time
            user_1_times.append(datetime.now())
            user_1_values.append(user_1_gamma)

            fig: plt.Figure = plt.figure()
            ax: plt.Axes = fig.gca()

            ax.set_xlabel("Time")
            ax.set_ylabel("Gamma")
            ax.set_title(f"Gamma history of u/{username_1}")
            ax.plot(user_1_times, user_1_values, color="white")
            add_rank_lines(ax, user_1_gamma)
            discord_file = create_file_from_figure(fig, "history_plot.png")

            await msg.edit(
                content=f"Here is your history graph! ({get_duration_str(start)})",
                file=discord_file,
            )
        else:
            await msg.edit(
                content="Something went wrong while creating the "
                f"history graph: {response.status_code}"
            )


def setup(bot: ButtercupBot) -> None:
    """Set up the History cog."""
    # Initialize blossom api
    cog_config = bot.config["Blossom"]
    email = cog_config.get("email")
    password = cog_config.get("password")
    api_key = cog_config.get("api_key")
    blossom_api = BlossomAPI(email=email, password=password, api_key=api_key)
    bot.add_cog(History(bot=bot, blossom_api=blossom_api))


def teardown(bot: ButtercupBot) -> None:
    """Unload the History cog."""
    bot.remove_cog("History")
