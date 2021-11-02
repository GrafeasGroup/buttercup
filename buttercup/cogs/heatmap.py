import io
from datetime import datetime
from typing import Any, Dict, Optional

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from blossom_wrapper import BlossomAPI, BlossomStatus
from discord import File
from discord.ext.commands import Cog
from discord_slash import SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_option

from buttercup.bot import ButtercupBot
from buttercup.cogs.helpers import (
    extract_username,
    extract_utc_offset,
    get_duration_str,
    parse_time_constraints,
)
from buttercup.strings import translation

i18n = translation()


def create_file_from_heatmap(
    heatmap: pd.DataFrame, username: str, utc_offset: int = 0
) -> File:
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
    fig.set_size_inches(9, 3.44)

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

    timezone = "UTC" if utc_offset == 0 else f"UTC{utc_offset:+d}"

    plt.title(i18n["heatmap"]["plot_title"].format(username))
    plt.xlabel(i18n["heatmap"]["plot_xlabel"].format(timezone))
    plt.ylabel(i18n["heatmap"]["plot_ylabel"])

    fig.tight_layout()
    heatmap_table = io.BytesIO()
    plt.savefig(heatmap_table, format="png")
    heatmap_table.seek(0)
    plt.clf()

    return File(heatmap_table, "heatmap_table.png")


def adjust_with_timezone(hour_data: Dict[str, Any], utc_offset: int) -> Dict[str, Any]:
    """Adjust the heatmap data according to the UTC offset of the user."""
    hour_offset = hour_data["hour"] + utc_offset
    new_hour = hour_offset % 24
    # The days go from 1 to 7, so we need to adjust this to zero index and back
    new_day = ((hour_data["day"] + hour_offset // 24) - 1) % 7 + 1
    return {"day": new_day, "hour": new_hour, "count": hour_data["count"]}


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
            ),
            create_option(
                name="after",
                description="The start date for the heatmap data.",
                option_type=3,
                required=False,
            ),
            create_option(
                name="before",
                description="The end date for the heatmap data.",
                option_type=3,
                required=False,
            ),
        ],
    )
    async def _heatmap(
        self,
        ctx: SlashContext,
        username: Optional[str] = None,
        after: Optional[str] = None,
        before: Optional[str] = None,
    ) -> None:
        """Generate a heatmap for the given user."""
        start = datetime.now()
        user = username or extract_username(ctx.author.display_name)
        utc_offset = extract_utc_offset(ctx.author.display_name)
        after_time, before_time, time_str = parse_time_constraints(after, before)
        msg = await ctx.send(
            i18n["heatmap"]["getting_heatmap"].format(user=user, time_str=time_str)
        )
        from_str = after_time.isoformat() if after_time else None
        until_str = before_time.isoformat() if before_time else None

        volunteer_response = self.blossom_api.get_user(user)
        if not volunteer_response.status == BlossomStatus.ok:
            await msg.edit(content=i18n["heatmap"]["user_not_found"].format(user))
            return
        volunteer = volunteer_response.data

        heatmap_response = self.blossom_api.get(
            "submission/heatmap/",
            params={
                "completed_by": volunteer["id"],
                "from": from_str,
                "until": until_str,
            },
        )
        if heatmap_response.status_code != 200:
            await msg.edit(content=i18n["heatmap"]["user_not_found"].format(user))
            return

        data = heatmap_response.json()
        data = [adjust_with_timezone(hour_data, utc_offset) for hour_data in data]

        day_index = pd.Index(range(1, 8))
        hour_index = pd.Index(range(0, 24))

        heatmap = (
            # Create a data frame from the data
            pd.DataFrame.from_records(data, columns=["day", "hour", "count"])
            # Convert it into a table with the days as rows and hours as columns
            .pivot(index="day", columns="hour", values="count")
            # Add the missing days and hours
            .reindex(index=day_index, columns=hour_index)
        )

        heatmap_table = create_file_from_heatmap(heatmap, user, utc_offset)

        await msg.edit(
            content=i18n["heatmap"]["response_message"].format(
                user=user, time_str=time_str, duration=get_duration_str(start)
            ),
            file=heatmap_table,
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
