from datetime import datetime
from typing import Optional, Dict, List

import matplotlib.pyplot as plt
from blossom_wrapper import BlossomAPI
from discord.ext.commands import Cog
from discord_slash import SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_option

from buttercup.bot import ButtercupBot


def init_heatmap_dict() -> Dict[int, Dict[int, int]]:
    """Get the initial dictionary for the heatmap data.

    For every day (1 = Monday, 7 = Sunday), it contains a dict entry
    with an entry 0 for every hour.
    """
    heatmap_dict = {}

    for day in range(1, 8):
        day_dict = {}

        for hour in range(0, 24):
            day_dict[hour] = 0

        heatmap_dict[day] = day_dict

    return heatmap_dict


def get_heatmap_dict(data: List[Dict[str, int]]) -> Dict[int, Dict[int, int]]:
    """Populate the heatmap dictionary with the data returned by Blossom."""
    heatmap_dict = init_heatmap_dict()

    for entry in data:
        day = entry["day"]
        hour = entry["hour"]
        count = entry["count"]

        heatmap_dict[day][hour] += count

    return heatmap_dict


class Heatmap(Cog):
    def __init__(self, bot: ButtercupBot, blossom_api: BlossomAPI) -> None:
        """Initialize the Heatmap cog."""
        self.bot = bot
        self.blossom_api = blossom_api

    @cog_ext.cog_slash(
        name="heatmap",
        description="Display the activity heatmap for the given user.",
        options=[
            create_option(
                name="username",
                description="The user to get the heatmap for. Defaults to the user executing the command.",
                option_type=3,
                required=False,
            )
        ],
    )
    async def _heatmap(self, ctx: SlashContext, username: Optional[str] = None) -> None:
        """Generate a heatmap for the given user."""
        msg = await ctx.send(f"Generating a heatmap for u/{username}...")

        response = self.blossom_api.get(
            "volunteer/heatmap/", params={"username": username}
        )

        if response.status_code != 200:
            await msg.edit(content=f"User u/{username} not found!")
            return

        data = response.json()
        heatmap_dict = get_heatmap_dict(data)

        await msg.edit(content=f"Data: {heatmap_dict}")


def setup(bot: ButtercupBot) -> None:
    """Set up the Heatmap cog."""
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

    bot.add_cog(Heatmap(bot=bot, blossom_api=blossom_api))


def teardown(bot: ButtercupBot) -> None:
    """Unload the Heatmap cog."""
    bot.remove_cog("Heatmap")
