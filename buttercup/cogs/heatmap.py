import io
from datetime import datetime, timedelta
from typing import List, Optional

import matplotlib.pyplot as plt
import pandas as pd
import pytz
import seaborn as sns
from blossom_wrapper import BlossomAPI
from dateutil import parser
from discord import File
from discord.ext.commands import Cog
from discord_slash import SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_option

from buttercup.bot import ButtercupBot
from buttercup.cogs.helpers import (
    BlossomException,
    BlossomUser,
    extract_utc_offset,
    get_duration_str,
    get_initial_username,
    get_user,
    get_user_id,
    get_username,
    parse_time_constraints,
    utc_offset_to_str,
)
from buttercup.strings import translation

i18n = translation()


def create_file_from_heatmap(
    heatmap: pd.DataFrame, user: Optional[BlossomUser], utc_offset: int = 0
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
    fig: plt.Figure
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

    timezone = utc_offset_to_str(utc_offset)

    plt.title(
        i18n["heatmap"]["plot_title"].format(user=get_username(user, escape=False))
    )
    plt.xlabel(i18n["heatmap"]["plot_xlabel"].format(timezone=timezone))
    plt.ylabel(i18n["heatmap"]["plot_ylabel"])

    fig.tight_layout()
    heatmap_table = io.BytesIO()
    plt.savefig(heatmap_table, format="png")
    heatmap_table.seek(0)
    plt.close(fig)

    return File(heatmap_table, "heatmap_table.png")


def _get_week_index(date: datetime) -> int:
    """Get an identification number for the week.

    year * 100 + week
    """
    calendar = date.isocalendar()
    return calendar[0] * 100 + calendar[1]


def _get_month_annotations(activity_df: pd.DataFrame) -> List[str]:
    """Get the month annotations for the activity map.

    The first week that has a date of a new month will get the month
    as annotation.
    """
    annotations = []

    for col in activity_df.columns:
        # Extract the year and week number from the column name
        year = col // 100
        week = col - year * 100

        # Reconstruct all dates in this week
        dates = [datetime.fromisocalendar(year, week, day) for day in range(1, 8)]

        new_month = ""

        for date in dates:
            if date.day == 1:
                # New month, add the month name
                new_month = date.strftime("%b")
                break

        annotations.append(new_month)

    return annotations


def _create_file_from_activity_map(
    activity_df: pd.DataFrame, user: Optional[BlossomUser], time_str: str
) -> File:
    """Create a Discord file containing the activity map."""
    days = i18n["heatmap"]["days"]

    # Only annotate the maximum values
    max_value = activity_df.max().max()
    annotations = activity_df.apply(
        lambda series: series.apply(
            lambda value: f"{value:0.0f}" if value == max_value else ""
        )
    )

    fig, ax = plt.subplots()
    fig: plt.Figure
    ax: plt.Axes
    fig.set_size_inches(9, 3.44)
    fig.subplots_adjust(bottom=0.25, top=1, left=0.05, right=0.98, wspace=0, hspace=0)

    cbar_kws = {
        "orientation": "horizontal",
        "fraction": 0.08,
        "aspect": 40,
        "shrink": 0.6,
    }

    sns.heatmap(
        activity_df,
        ax=ax,
        annot=annotations,
        annot_kws={"fontsize": "x-small"},
        fmt="s",
        cbar=True,
        cbar_kws=cbar_kws,
        square=True,
        yticklabels=days,
        xticklabels=_get_month_annotations(activity_df),
    )

    ax.set_title(
        i18n["activity"]["plot_title"].format(user=get_username(user, escape=False), time=time_str)
    )
    # Remove axis labels
    ax.set_xlabel(None)
    ax.set_ylabel(None)

    activity_map = io.BytesIO()
    plt.savefig(activity_map, format="png")
    activity_map.seek(0)
    plt.close(fig)

    return File(activity_map, "activity_map.png")


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
        username: Optional[str] = "me",
        after: Optional[str] = None,
        before: Optional[str] = None,
    ) -> None:
        """Generate a heatmap for the given user."""
        start = datetime.now()

        after_time, before_time, time_str = parse_time_constraints(after, before)

        msg = await ctx.send(
            i18n["heatmap"]["getting_heatmap"].format(
                user=get_initial_username(username, ctx), time_str=time_str
            )
        )

        utc_offset = extract_utc_offset(ctx.author.display_name)

        from_str = after_time.isoformat() if after_time else None
        until_str = before_time.isoformat() if before_time else None

        user = get_user(username, ctx, self.blossom_api)

        heatmap_response = self.blossom_api.get(
            "submission/heatmap/",
            params={
                "completed_by": get_user_id(user),
                "utc_offset": utc_offset,
                "complete_time__gte": from_str,
                "complete_time__lte": until_str,
            },
        )
        if heatmap_response.status_code != 200:
            raise BlossomException(heatmap_response)

        data = heatmap_response.json()

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
                user=get_username(user),
                time_str=time_str,
                duration=get_duration_str(start),
            ),
            file=heatmap_table,
        )

    @cog_ext.cog_slash(
        name="activity",
        description="Display the yearly activity map for the given user.",
        options=[
            create_option(
                name="username",
                description="The user to get the activity map for.",
                option_type=3,
                required=False,
            ),
            create_option(
                name="before",
                description="The end time of the activity map, it will show one year before this date.",
                option_type=3,
                required=False,
            ),
        ],
    )
    async def activity_map(
        self,
        ctx: SlashContext,
        username: Optional[str] = "me",
        before: Optional[str] = None,
    ) -> None:
        """Generate a yearly activity heatmap for the given user."""
        start = datetime.now()

        # First parse the end time for the activity map
        _, before_time, _ = parse_time_constraints(None, before)

        # Then calculate the start time (one year before the end)
        after = "1 year" if before_time is None else (before_time - timedelta(days=365)).isoformat()
        # and get the string representing the time span
        after_time, _, time_str = parse_time_constraints(after, before)

        msg = await ctx.send(
            i18n["activity"]["getting_activity"].format(
                user=get_initial_username(username, ctx)
            )
        )

        from_str = after_time.isoformat() if after_time else None
        until_str = before_time.isoformat() if before_time else None

        user = get_user(username, ctx, self.blossom_api)

        rate_response = self.blossom_api.get(
            "submission/rate/",
            params={
                "completed_by__isnull": False,
                "completed_by": get_user_id(user),
                "complete_time__gte": from_str,
                "complete_time__lte": until_str,
                "page_size": 365,
                "time_frame": "day",
            },
        )
        if rate_response.status_code != 200:
            raise BlossomException(rate_response)

        rate_data = rate_response.json()["results"]
        rate_df = pd.DataFrame.from_records(rate_data, columns=["date", "count"])
        # Convert date strings to datetime objects
        rate_df["date"] = rate_df["date"].apply(lambda x: parser.parse(x))
        rate_df = rate_df.set_index("date")

        # Add the week number
        rate_df["week"] = rate_df.index.to_series().apply(lambda x: _get_week_index(x))
        # Add the week day
        rate_df["day"] = rate_df.index.to_series().apply(lambda x: x.isocalendar()[2])

        # All possible weeks, in case some are missing in the data
        all_week_indexes = [
            _get_week_index((before_time or start) - timedelta(weeks=weeks)) for weeks in range(53)
        ]

        activity_df = (
            # Create a data frame from the data
            rate_df
            # Convert it into a table with the days as rows and hours as columns
            .pivot(index="day", columns="week", values="count")
            # Make sure all week days are present
            .reindex(range(1, 8))
            .transpose()
            # Make sure all week numbers are present
            .reindex(reversed(all_week_indexes))
            .transpose()
        )

        activity_map = _create_file_from_activity_map(activity_df, user, time_str)

        await msg.edit(
            content=i18n["activity"]["response_message"].format(
                user=get_username(user),
                time=time_str,
                duration=get_duration_str(start),
            ),
            file=activity_map,
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
