import io
from typing import Optional

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from blossom_wrapper import BlossomAPI
from discord import File
from discord.ext.commands import Cog
from discord_slash import SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_option

from buttercup.bot import ButtercupBot


# Colors to use in the plots
background_color = "#36393f"  # Discord background color
text_color = "white"
line_color = "white"


def create_file_from_heatmap(heatmap: pd.DataFrame, username: str,) -> File:
    """Create a Discord file containing the heatmap table."""
    days = [
        "Mon",
        "Tue",
        "Wed",
        "Thu",
        "Fri",
        "Sat",
        "Sun",
    ]
    hours = ["{:02d}".format(hour) for hour in range(0, 24)]

    # The built in formatting for the heatmap doesn't allow displaying floats as ints
    # And we have to use floats because empty entries are NaN
    # So we have to manually provide the annotations
    annotations = heatmap.apply(
        lambda series: series.apply(lambda value: f"{value:0.0f}")
    )

    fig, ax = plt.subplots()
    fig.set_size_inches(14, 5.0)

    sns.heatmap(
        heatmap,
        ax=ax,
        annot=annotations,
        fmt="s",
        cbar=False,
        square=True,
        xticklabels=hours,
        yticklabels=days,
    )

    heatmap_table = io.BytesIO()
    plt.savefig(heatmap_table, format="png")
    heatmap_table.seek(0)
    plt.clf()

    return File(heatmap_table, "heatmap_table.png")


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
                description="The user to get the heatmap for.",
                option_type=3,
                required=True,
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

        day_index = pd.Index(range(1, 8))
        hour_index = pd.Index(range(0, 24))

        heatmap = (
            # Create a data frame from the data
            pd.DataFrame.from_dict(data)
            # Convert it into a table with the days as rows and hours as columns
            .pivot(index="day", columns="hour", values="count")
            # Add the missing days and hours
            .reindex(index=day_index, columns=hour_index)
        )

        heatmap_table = create_file_from_heatmap(heatmap, username)

        await msg.edit(
            content=f"Here is the heatmap for u/{username}:", file=heatmap_table
        )


def setup(bot: ButtercupBot) -> None:
    """Set up the Heatmap cog."""
    # Initialize blossom api
    cog_config = bot.config["Blossom"]
    email = cog_config.get("email")
    password = cog_config.get("password")
    api_key = cog_config.get("api_key")
    blossom_api = BlossomAPI(email=email, password=password, api_key=api_key)

    # Initialize PyPlot
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
