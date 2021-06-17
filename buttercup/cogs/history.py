import io
import logging
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
from buttercup.strings import translation


i18n = translation()


def username_from_display_name(display_name: str) -> Optional[str]:
    """Extract the username from the display name."""
    first_part = display_name.split(" ")[0]

    if not first_part.startswith("/u/"):
        return None

    return first_part[3:]


def create_file_from_data(
    times: List[datetime], values: List[int], username: str
) -> File:
    """Create a Discord file containing the plotted history graph."""
    plt.plot(times, values, color="white")
    plt.xlabel("Time")
    plt.ylabel("Gamma")
    plt.xticks(rotation=90)
    plt.title(f"Gamma history of u/{username}")
    history_plot = io.BytesIO()
    plt.savefig(history_plot, format="png")
    history_plot.seek(0)
    plt.clf()

    return File(history_plot, "history_plot.png")


def get_progress_indicator(current: int, maximum: int) -> str:
    """Get a string indicating the current progress."""
    max_bars = 20
    bars = math.ceil((current / maximum) * max_bars)
    return f"`[{bars * '#'}{(max_bars - bars) * ' '}]` ({current}/{maximum})"


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

        username_1 = user_1
        if user_1 is None:
            username_1 = username_from_display_name(ctx.author.display_name)
            if username_1 is None:
                await msg.edit(
                    content=f"{ctx.author.display_name} is an invalid username! "
                    "Did you change your display name to the required format?"
                )
                return

        # First, get the total gamma for the user
        user_1_response = self.blossom_api.get_user(username_1)
        if user_1_response.status != BlossomStatus.ok:
            await msg.edit(content=f"Failed to get the data for user {username_1}!")
            return
        user_1_gamma = user_1_response.data["gamma"]
        user_1_id = user_1_response.data["id"]

        await msg.edit(
            content=f"Creating the history graph... "
            f"{get_progress_indicator(0, user_1_gamma)}"
        )

        user_1_times = [datetime.now()]
        user_1_values = [user_1_gamma]
        page = 1
        gamma_offset = 0
        response = self.blossom_api.get_transcription(author=user_1_id, page=page, page_size=page_size)

        while response.status == BlossomStatus.ok:
            transcriptions = response.data

            # Add the transcriptions to the data
            for tr in transcriptions:
                date = parser.parse(tr["create_time"])
                user_1_times.append(date)
                user_1_values.append(user_1_gamma - gamma_offset)
                gamma_offset += 1

            await msg.edit(
                content=f"Creating the history graph... "
                f"{get_progress_indicator(gamma_offset, user_1_gamma)}"
            )

            # Continue with the next page
            page += 1
            try:
                response = self.blossom_api.get_transcription(
                    author=user_1_id, page=page, page_size=page_size
                )
            except HTTPError:
                # Hack: The next page is not available anymore, so we reached the end
                discord_file = create_file_from_data(
                    user_1_times, user_1_values, user_1
                )
                duration = datetime.now() - start
                await msg.edit(content=f"I created the plot in {duration.seconds}s", file=discord_file)
                break


def setup(bot: ButtercupBot) -> None:
    """Set up the History cog."""
    # Initialize blossom api
    cog_config = bot.config["Blossom"]
    email = cog_config.get("email")
    password = cog_config.get("password")
    api_key = cog_config.get("api_key")
    blossom_api = BlossomAPI(email=email, password=password, api_key=api_key)

    # Initialize PyPlot

    # Colors to use in the plots
    background_color = "#36393f"  # Discord background color
    text_color = "white"
    line_color = "white"

    # Global settings for the plots
    plt.rcParams["figure.facecolor"] = background_color
    plt.rcParams["axes.facecolor"] = background_color
    plt.rcParams["axes.labelcolor"] = text_color
    plt.rcParams["axes.edgecolor"] = line_color
    plt.rcParams["text.color"] = text_color
    plt.rcParams["xtick.color"] = line_color
    plt.rcParams["ytick.color"] = line_color
    plt.rcParams["grid.color"] = line_color
    plt.rcParams["grid.alpha"] = 0.8
    plt.rcParams["figure.dpi"] = 200.0

    bot.add_cog(History(bot=bot, blossom_api=blossom_api))


def teardown(bot: ButtercupBot) -> None:
    """Unload the History cog."""
    bot.remove_cog("History")
