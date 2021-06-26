import io
from datetime import datetime
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
from buttercup.cogs.helpers import extract_username, get_duration_str
from buttercup.strings import translation

i18n = translation()


def create_file_from_heatmap(heatmap: pd.DataFrame, username: str,) -> File:
    """Create a Discord file containing the heatmap table."""
    days = i18n["heatmap"]["days"]
    hours = ["{:02d}".format(hour) for hour in range(0, 24)]

    # The built in formatting for the heatmap doesn't allow displaying floats as ints
    # And we have to use floats because empty entries are NaN
    # So we have to manually provide the annotations
    annotations = heatmap.apply(
        lambda series: series.apply(lambda value: f"{value:0.0f}")
    )

    fig, ax = plt.subplots()
    fig.set_size_inches(9, 3.2)
    plt.title(i18n["heatmap"]["plot_title"].format(username))

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

    fig.tight_layout()
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
                required=False,
            )
        ],
    )
    async def _heatmap(self, ctx: SlashContext, username: Optional[str] = None) -> None:
        """Generate a heatmap for the given user."""
        start = datetime.now()
        user = username or extract_username(ctx.author.display_name)
        msg = await ctx.send(i18n["heatmap"]["getting_heatmap"].format(user))

        response = self.blossom_api.get(
            "volunteer/heatmap/", params={"username": user}
        )

        if response.status_code != 200:
            await msg.edit(content=i18n["heatmap"]["user_not_found"].format(user))
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

        heatmap_table = create_file_from_heatmap(heatmap, user)

        await msg.edit(
            content=i18n["heatmap"]["response_message"].format(user, get_duration_str(start)), file=heatmap_table
        )


def setup(bot: ButtercupBot) -> None:
    """Set up the Heatmap cog."""
    # Initialize blossom api
    cog_config = bot.config["Blossom"]
    email = cog_config.get("email")
    password = cog_config.get("password")
    api_key = cog_config.get("api_key")
    blossom_api = BlossomAPI(email=email, password=password, api_key=api_key)

    bot.add_cog(Heatmap(bot=bot, blossom_api=blossom_api))


def teardown(bot: ButtercupBot) -> None:
    """Unload the Heatmap cog."""
    bot.remove_cog("Heatmap")
