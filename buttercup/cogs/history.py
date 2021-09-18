import io
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union

import matplotlib.pyplot as plt
import pandas as pd
from blossom_wrapper import BlossomAPI, BlossomStatus
from dateutil import parser
from dateutil.tz import tzutc
from discord import File
from discord.ext.commands import Cog
from discord_slash import SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_option

from buttercup.bot import ButtercupBot
from buttercup.cogs import ranks
from buttercup.cogs.helpers import (
    BlossomException,
    format_api_time,
    get_duration_str,
    get_usernames_from_user_list,
    join_items_with_and,
    parse_time_constraints,
)
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


def get_timedelta_from_time_frame(time_frame: Optional[str]) -> timedelta:
    """Get the timedelta for the given time frame option."""
    if time_frame == "year":
        return timedelta(days=356)
    if time_frame == "month":
        return timedelta(days=30)
    if time_frame == "week":
        return timedelta(weeks=1)
    if time_frame == "hour":
        return timedelta(hours=1)
    if time_frame == "none":
        return timedelta(seconds=1)
    # One day is the default
    return timedelta(days=1)


def add_zero_rates(data: pd.DataFrame, time_frame: str) -> pd.DataFrame:
    """Add entries for the zero rates to the data frame.

    When the rate is zero, it is not returned in the API response.
    Therefore we need to add it manually.
    However, for a span of zero entries, we only need the first
    and last entry. This reduces the number of data points.
    """
    new_index = set()
    delta = get_timedelta_from_time_frame(time_frame)
    now = datetime.now(tz=tzutc())

    for date in data.index:
        new_index.add(date)
        new_index.add(date - delta)
        if date + delta < now:
            new_index.add(date + delta)

    return data.reindex(new_index, fill_value=0).sort_index()


def add_milestone_lines(
    ax: plt.Axes, milestones: List[Dict[str, Union[str, int]]], value: float
) -> plt.Axes:
    """Add the lines for the milestones the user reached.

    :param ax: The axis to draw the milestones into.
    :param milestones: The milestones to consider. Each must have a threshold and color.
    :param value: The value to determine if a user reached a given milestone.
    """
    for milestone in milestones:
        if value >= milestone["threshold"]:
            ax.axhline(y=milestone["threshold"], color=milestone["color"], zorder=-1)
    return ax


def create_file_from_figure(fig: plt.Figure, file_name: str) -> File:
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

    def get_all_rate_data(
        self,
        user_id: int,
        time_frame: str,
        after_time: Optional[datetime],
        before_time: Optional[datetime],
    ) -> pd.DataFrame:
        """Get all rate data for the given user."""
        page_size = 500

        user_data = pd.DataFrame(columns=["date", "count"]).set_index("date")
        page = 1
        # Placeholder until we get the real value from the response
        next_page = "1"

        from_str = format_api_time(after_time)
        until_str = format_api_time(before_time)

        while next_page is not None:
            response = self.blossom_api.get(
                "submission/rate",
                params={
                    "completed_by": user_id,
                    "page": page,
                    "page_size": page_size,
                    "time_frame": time_frame,
                    "from": from_str,
                    "until": until_str,
                },
            )
            if response.status_code != 200:
                raise BlossomException(response)

            rate_data = response.json()["results"]
            next_page = response.json()["next"]

            new_frame = pd.DataFrame.from_records(rate_data)
            # Convert date strings to datetime objects
            new_frame["date"] = new_frame["date"].apply(lambda x: parser.parse(x))
            # Add the data to the list
            user_data = user_data.append(new_frame.set_index("date"))

            # Continue with the next page
            page += 1

        # Add the missing zero entries
        user_data = add_zero_rates(user_data, time_frame)
        return user_data

    def get_user_history(
        self, user: str, after_time: Optional[datetime], before_time: Optional[datetime]
    ) -> Tuple[int, pd.DataFrame]:
        """Get a data frame representing the history of the user.

        :returns: The gamma of the user and their history data.
        """
        # First, get the total gamma for the user
        user_response = self.blossom_api.get_user(user)
        if user_response.status != BlossomStatus.ok:
            raise BlossomException(user_response)

        user_gamma = user_response.data["gamma"]
        user_id = user_response.data["id"]

        # Get all rate data
        time_frame = get_data_granularity(user_gamma)
        user_data = self.get_all_rate_data(user_id, time_frame, after_time, before_time)

        offset = 0
        # Calculate the gamma offset if needed
        if after_time is not None:
            if before_time is None:
                # We can calculate the offset from the given data
                offset = user_gamma - user_data.count()
            else:
                # We need to get the offset from the API
                offset_response = self.blossom_api.get(
                    "submission/",
                    params={
                        "completed_by": user_id,
                        "until": format_api_time(before_time),
                        "page_size": 1,
                    },
                )
                if offset_response.status_code == 200:
                    offset = offset_response.json()["count"]

        # Add an up-to-date entry
        user_data.loc[datetime.now(tz=tzutc())] = [0]
        # Aggregate the gamma score
        user_data = user_data.assign(gamma=user_data.expanding(1).sum() + offset)

        return user_gamma, user_data

    @cog_ext.cog_slash(
        name="history",
        description="Display the history graph.",
        options=[
            create_option(
                name="users",
                description="The users to display the history graph for (max 5)."
                "Defaults to the user executing the command.",
                option_type=3,
                required=False,
            ),
            create_option(
                name="after",
                description="The start date for the history data.",
                option_type=3,
                required=False,
            ),
            create_option(
                name="before",
                description="The end date for the history data.",
                option_type=3,
                required=False,
            ),
        ],
    )
    async def _history(
        self,
        ctx: SlashContext,
        users: Optional[str] = None,
        after: Optional[str] = None,
        before: Optional[str] = None,
    ) -> None:
        """Get the transcription history of the user."""
        start = datetime.now()

        users = get_usernames_from_user_list(users, ctx.author)
        usernames = join_items_with_and([f"u/{user}" for user in users])
        after_time, before_time, time_str = parse_time_constraints(after, before)

        # Give a quick response to let the user know we're working on it
        # We'll later edit this message with the actual content
        if len(users) == 1:
            msg = await ctx.send(
                i18n["history"]["getting_history_single"].format(user=users[0])
            )
        else:
            msg = await ctx.send(
                i18n["history"]["getting_history_multi"].format(
                    users=usernames, count=0, total=len(users)
                )
            )

        user_gammas = []

        fig: plt.Figure = plt.figure()
        ax: plt.Axes = fig.gca()

        fig.subplots_adjust(bottom=0.2)
        ax.set_xlabel(i18n["history"]["plot_xlabel"])
        ax.set_ylabel(i18n["history"]["plot_ylabel"])

        for label in ax.get_xticklabels():
            label.set_rotation(32)
            label.set_ha("right")

        if len(users) == 1:
            ax.set_title(i18n["history"]["plot_title_single"].format(user=users[0]))
        else:
            ax.set_title(i18n["history"]["plot_title_multi"])

        for index, user in enumerate(users):
            if len(users) > 1:
                await msg.edit(
                    content=i18n["history"]["getting_history_multi"].format(
                        users=usernames, count=index + 1, total=len(users)
                    )
                )

            user_gamma, user_data = self.get_user_history(user, after_time, before_time)
            user_gammas.append(user_gamma)

            # Plot the graph
            ax.plot(
                "date",
                "gamma",
                data=user_data.reset_index(),
                color=ranks[index]["color"],
            )

        # Show ranks when you are close to them already
        ax = add_milestone_lines(ax, ranks, max(user_gammas) * 1.4)

        if len(users) > 1:
            ax.legend([f"u/{user}" for user in users])

        discord_file = create_file_from_figure(fig, "history_plot.png")

        await msg.edit(
            content=i18n["history"]["response_message"].format(
                duration=get_duration_str(start)
            ),
            file=discord_file,
        )

    def get_user_rate(
        self, user: str, after_time: Optional[datetime], before_time: Optional[datetime]
    ) -> pd.DataFrame:
        """Get a data frame representing the transcription rate of the user.

        :returns: The rate data of the user.
        """
        # First, get the ID of the user
        user_response = self.blossom_api.get_user(user)
        if user_response.status != BlossomStatus.ok:
            raise BlossomException(user_response)

        user_id = user_response.data["id"]

        # Get all rate data
        user_data = self.get_all_rate_data(user_id, "day", after_time, before_time)

        # Add an up-to-date entry
        today = datetime.now(tz=tzutc()).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        if today not in user_data.index:
            user_data.loc[today] = [0]

        return user_data

    @cog_ext.cog_slash(
        name="rate",
        description="Display the rate graph.",
        options=[
            create_option(
                name="users",
                description="The users to display the rate graph for (max 5)."
                "Defaults to the user executing the command.",
                option_type=3,
                required=False,
            ),
            create_option(
                name="after",
                description="The start date for the rate data.",
                option_type=3,
                required=False,
            ),
            create_option(
                name="before",
                description="The end date for the rate data.",
                option_type=3,
                required=False,
            ),
        ],
    )
    async def _rate(
        self,
        ctx: SlashContext,
        users: Optional[str] = None,
        after: Optional[str] = None,
        before: Optional[str] = None,
    ) -> None:
        """Get the transcription rate of the user."""
        start = datetime.now()

        users = get_usernames_from_user_list(users, ctx.author)
        usernames = join_items_with_and([f"u/{user}" for user in users])
        after_time, before_time, time_str = parse_time_constraints(after, before)

        # Give a quick response to let the user know we're working on it
        # We'll later edit this message with the actual content
        if len(users) == 1:
            msg = await ctx.send(
                i18n["rate"]["getting_rate_single"].format(user=users[0])
            )
        else:
            msg = await ctx.send(
                i18n["rate"]["getting_rate_multi"].format(
                    users=usernames, count=0, total=len(users)
                )
            )

        max_rates = []

        fig: plt.Figure = plt.figure()
        ax: plt.Axes = fig.gca()

        fig.subplots_adjust(bottom=0.2)
        ax.set_xlabel(i18n["rate"]["plot_xlabel"])
        ax.set_ylabel(i18n["rate"]["plot_ylabel"])

        for label in ax.get_xticklabels():
            label.set_rotation(32)
            label.set_ha("right")

        if len(users) == 1:
            ax.set_title(i18n["rate"]["plot_title_single"].format(user=users[0]))
        else:
            ax.set_title(i18n["rate"]["plot_title_multi"])

        for index, user in enumerate(users):
            if len(users) > 1:
                await msg.edit(
                    content=i18n["rate"]["getting_rate_multi"].format(
                        users=usernames, count=index + 1, total=len(users)
                    )
                )

            user_data = self.get_user_rate(user, after_time, before_time)

            max_rates.append(user_data["count"].max())

            # Plot the graph
            ax.plot(
                "date",
                "count",
                data=user_data.reset_index(),
                color=ranks[index]["color"],
            )

        # A milestone at every 100 rate
        milestones = [
            dict(threshold=i * 100, color=ranks[i + 2]["color"]) for i in range(1, 8)
        ]
        # Show rate milestones when you are close to them already
        value = max(max_rates) + 40
        ax = add_milestone_lines(ax, milestones, value)

        if len(users) > 1:
            ax.legend([f"u/{user}" for user in users])

        discord_file = create_file_from_figure(fig, "rate_plot.png")

        await msg.edit(
            content=i18n["rate"]["response_message"].format(
                duration=get_duration_str(start)
            ),
            file=discord_file,
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
