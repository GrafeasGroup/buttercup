import io
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union

import discord
import matplotlib.pyplot as plt
import pandas as pd
import pytz
from blossom_wrapper import BlossomAPI
from dateutil import parser
from discord import Embed, File
from discord.ext.commands import Cog, UserNotFound
from discord_slash import SlashContext, cog_ext
from discord_slash.model import SlashMessage
from discord_slash.utils.manage_commands import create_option

from buttercup.bot import ButtercupBot
from buttercup.cogs import ranks
from buttercup.cogs.helpers import (
    BlossomException,
    BlossomUser,
    InvalidArgumentException,
    get_discord_time_str,
    get_duration_str,
    get_initial_username,
    get_initial_username_list,
    get_rank,
    get_rgb_from_hex,
    get_timedelta_str,
    get_user,
    get_user_gamma,
    get_user_id,
    get_user_list,
    get_username,
    get_usernames,
    parse_time_constraints,
    extract_utc_offset,
    utc_offset_to_str,
)
from buttercup.strings import translation

i18n = translation()


def get_data_granularity(
    user: Optional[BlossomUser], after: Optional[datetime], before: Optional[datetime]
) -> str:
    """Determine granularity of the graph.

    It should be as detailed as possible, but only require 1 API call in the best case.
    """
    if not user:
        return "week"

    # TODO: Adjust this when the Blossom dates have been fixed
    now = datetime.now(tz=pytz.utc)
    date_joined = parser.parse(user["date_joined"])
    total_delta = now - date_joined
    total_hours = total_delta.total_seconds() / 60
    # The time delta that the data is calculated on
    relevant_delta = (before or now) - (after or date_joined)
    relevant_hours = relevant_delta.total_seconds() / 60
    time_factor = relevant_hours / total_hours

    total_gamma: int = user["gamma"]
    # The expected gamma in the relevant time frame
    adjusted_gamma = total_gamma * time_factor

    if adjusted_gamma <= 500:
        return "none"
    if relevant_hours * 0.3 <= 500 or adjusted_gamma <= 1500:
        # We estimate that the user is only active in one third of the hours
        # The user is expected to complete 3 transcriptions within the same hour
        return "hour"

    # Don't be less accurate than a day, it loses too much detail
    return "day"


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


def add_zero_rates(
    data: pd.DataFrame,
    time_frame: str,
    after_time: Optional[datetime],
    before_time: Optional[datetime],
) -> pd.DataFrame:
    """Add entries for the zero rates to the data frame.

    When the rate is zero, it is not returned in the API response.
    Therefore we need to add it manually.
    However, for a span of zero entries, we only need the first
    and last entry. This reduces the number of data points.
    """
    new_index = set()
    delta = get_timedelta_from_time_frame(time_frame)
    now = datetime.now(tz=pytz.utc)

    if after_time:
        # Add the earliest point according to the timeframe
        first_date = data.index[0]
        # Make sure everything is localized
        first_date = first_date.replace(tzinfo=pytz.utc)

        missing_delta: timedelta = first_date - after_time
        missing_time_frames = missing_delta.total_seconds() // delta.total_seconds()
        if missing_time_frames > 0:
            # We need to add a new entry at the beginning
            missing_delta = timedelta(
                seconds=missing_time_frames * delta.total_seconds()
            )
            missing_date = first_date - missing_delta
            new_index.add(missing_date)

    for date in data.index:
        new_index.add(date)
        new_index.add(date - delta)
        if date + delta < now:
            new_index.add(date + delta)

    # Add the latest point according to the timeframe
    last_date = data.index[-1]
    # Make sure everything is localized
    last_date = last_date.replace(tzinfo=pytz.utc)

    missing_delta: timedelta = (before_time or now) - last_date
    missing_time_frames = missing_delta.total_seconds() // delta.total_seconds()
    if missing_time_frames > 0:
        # We need to add a new entry at the end
        missing_delta = timedelta(seconds=missing_time_frames * delta.total_seconds())
        missing_date = last_date + missing_delta
        new_index.add(missing_date)

    return data.reindex(new_index, fill_value=0).sort_index()


def get_user_colors(users: Optional[List[BlossomUser]]) -> List[str]:
    """Assign a color to each user.

    This will prefer to assign a user their rank color.
    A single user will get white for better readability.
    """
    if not users or len(users) == 1:
        # If we don't need to distinguish, take white (best contrast)
        return ["#eeeeee"]

    color_mapping = {}
    available_ranks = [r for r in ranks]
    left_over_users = []

    for user in users:
        user_rank = get_rank(user["gamma"])

        # Give the user their rank color if possible
        if user_rank in available_ranks:
            color_mapping[user["username"]] = user_rank["color"]
            available_ranks = [
                r for r in available_ranks if r["name"] != user_rank["name"]
            ]
        else:
            left_over_users.append(user)

    # Give the left over users another rank's color
    for i, user in enumerate(left_over_users):
        color_mapping[user["username"]] = available_ranks[i]["color"]

    return [color_mapping[user["username"]] for user in users]


def add_milestone_lines(
    ax: plt.Axes,
    milestones: List[Dict[str, Union[str, int]]],
    min_value: float,
    max_value: float,
    delta: float,
) -> plt.Axes:
    """Add the lines for the milestones the user reached.

    :param ax: The axis to draw the milestones into.
    :param milestones: The milestones to consider. Each must have a threshold and color.
    :param min_value: The minimum value to determine if a milestone should be included.
    :param max_value: The maximum value to determine if a milestone should be inlcuded.
    :param delta: Determines how "far away" milestone lines are still included.
    """
    for milestone in milestones:
        if max_value + delta >= milestone["threshold"] >= min_value - delta:
            ax.axhline(y=milestone["threshold"], color=milestone["color"], zorder=-1)
    return ax


def create_file_from_figure(fig: plt.Figure, file_name: str) -> File:
    """Create a Discord file containing the figure."""
    history_plot = io.BytesIO()

    fig.savefig(history_plot, format="png")
    history_plot.seek(0)
    plt.close(fig)

    return File(history_plot, file_name)


def get_history_data_from_rate_data(
    rate_data: pd.DataFrame, offset: int
) -> pd.DataFrame:
    """Aggregate the rate data to history data.

    :param rate_data: The rate data to calculate the history data from.
    :param offset: The gamma offset at the first point of the graph.
    """
    return rate_data.assign(gamma=rate_data.expanding(1).sum() + offset)


def get_next_rank(gamma: int) -> Optional[Dict[str, Union[str, int]]]:
    """Determine the next rank based on the current gamma."""
    for rank in ranks:
        if rank["threshold"] > gamma:
            return rank

    return None


def parse_goal_str(goal_str: str) -> Tuple[int, str]:
    """Parse the given goal string.

    :returns: The goal gamma and the goal string.
    """
    goal_str = goal_str.strip()

    if goal_str.isnumeric():
        goal_gamma = int(goal_str, 10)
        return goal_gamma, f"{goal_gamma:,}"

    for rank in ranks:
        if goal_str.casefold() == rank["name"].casefold():
            goal_gamma = int(rank["threshold"])
            return rank["threshold"], f"{rank['name']} ({goal_gamma:,})"

    raise InvalidArgumentException("goal", goal_str)


async def _get_user_progress(
    user: Optional[BlossomUser],
    after_time: Optional[datetime],
    before_time: Optional[datetime],
    blossom_api: BlossomAPI,
) -> int:
    """Get the number of transcriptions made in the given time frame."""
    from_str = after_time.isoformat() if after_time else None
    until_str = before_time.isoformat() if before_time else None

    # We ask for submission completed by the user in the time frame
    # The response will contain a count, so we just need 1 result
    progress_response = blossom_api.get(
        "submission/",
        params={
            "completed_by": get_user_id(user),
            "complete_time__gte": from_str,
            "complete_time__lte": until_str,
            "page_size": 1,
        },
    )
    if progress_response.status_code != 200:
        raise BlossomException(progress_response)

    return progress_response.json()["count"]


async def _get_progress_description(
    user: Optional[BlossomUser],
    user_gamma: int,
    goal_gamma: int,
    goal_str: str,
    start: datetime,
    after_time: datetime,
    before_time: Optional[datetime],
    blossom_api: BlossomAPI,
) -> str:
    """Get the description for the user's prediction to reach the goal."""
    user_progress = await _get_user_progress(user, after_time, before_time, blossom_api)
    time_frame = (before_time or start) - after_time

    if user_gamma >= goal_gamma:
        # The user has already reached the goal
        return i18n["until"]["embed_description_reached"].format(
            time_frame=get_timedelta_str(time_frame),
            user=get_username(user),
            user_gamma=user_gamma,
            goal=goal_str,
            user_progress=user_progress,
        )
    elif user_progress == 0:
        return i18n["until"]["embed_description_zero"].format(
            time_frame=get_timedelta_str(time_frame),
            user=get_username(user),
            user_gamma=user_gamma,
            goal=goal_str,
        )
    else:
        # Based on the progress in the timeframe, calculate the time needed
        gamma_needed = goal_gamma - user_gamma
        relative_time = timedelta(
            seconds=gamma_needed * (time_frame.total_seconds() / user_progress)
        )
        absolute_time = start + relative_time

        return i18n["until"]["embed_description_prediction"].format(
            time_frame=get_timedelta_str(time_frame),
            user=get_username(user),
            user_gamma=user_gamma,
            goal=goal_str,
            user_progress=user_progress,
            relative_time=get_timedelta_str(relative_time),
            absolute_time=get_discord_time_str(absolute_time),
        )


class History(Cog):
    def __init__(self, bot: ButtercupBot, blossom_api: BlossomAPI) -> None:
        """Initialize the History cog."""
        self.bot = bot
        self.blossom_api = blossom_api

    def get_all_rate_data(
        self,
        user: Optional[BlossomUser],
        time_frame: str,
        after_time: Optional[datetime],
        before_time: Optional[datetime],
        utc_offset: int,
    ) -> pd.DataFrame:
        """Get all rate data for the given user."""
        page_size = 500

        rate_data = pd.DataFrame(columns=["date", "count"]).set_index("date")
        page = 1
        # Placeholder until we get the real value from the response
        next_page = "1"

        from_str = after_time.isoformat() if after_time else None
        until_str = before_time.isoformat() if before_time else None

        while next_page is not None:
            response = self.blossom_api.get(
                "submission/rate",
                params={
                    "completed_by": get_user_id(user),
                    "page": page,
                    "page_size": page_size,
                    "time_frame": time_frame,
                    "complete_time__gte": from_str,
                    "complete_time__lte": until_str,
                    "utc_offset": utc_offset,
                },
            )
            if response.status_code != 200:
                raise BlossomException(response)

            new_data = response.json()["results"]
            next_page = response.json()["next"]

            new_frame = pd.DataFrame.from_records(new_data)
            # Convert date strings to datetime objects
            new_frame["date"] = new_frame["date"].apply(lambda x: parser.parse(x))
            # Add the data to the list
            rate_data = rate_data.append(new_frame.set_index("date"))

            # Continue with the next page
            page += 1

        # Add the missing zero entries
        rate_data = add_zero_rates(rate_data, time_frame, after_time, before_time)
        return rate_data

    def calculate_history_offset(
        self,
        user: Optional[BlossomUser],
        rate_data: pd.DataFrame,
        after_time: Optional[datetime],
        before_time: Optional[datetime],
    ) -> int:
        """Calculate the gamma offset for the history graph.

        Note: We always need to do this, because it might be the case that some
        transcriptions don't have a date set.
        """
        gamma = get_user_gamma(user, self.blossom_api)

        if before_time is not None:
            # We need to get the offset from the API
            offset_response = self.blossom_api.get(
                "submission/",
                params={
                    "completed_by__isnull": False,
                    "completed_by": get_user_id(user),
                    "complete_time__gte": before_time.isoformat(),
                    "page_size": 1,
                },
            )
            if not offset_response.ok:
                raise BlossomException(offset_response)

            # We still need to calculate based on the total gamma
            # It may be the case that not all transcriptions have a date set
            # Then they are not included in the data nor in the API response
            return gamma - rate_data.sum() - offset_response.json()["count"]
        else:
            # We can calculate the offset from the given data
            return gamma - rate_data.sum()

    def get_user_history(
        self,
        user: Optional[BlossomUser],
        after_time: Optional[datetime],
        before_time: Optional[datetime],
        utc_offset: int,
    ) -> pd.DataFrame:
        """Get a data frame representing the history of the user.

        :returns: The history data of the user.
        """
        # Get all rate data
        time_frame = get_data_granularity(user, after_time, before_time)
        rate_data = self.get_all_rate_data(
            user, time_frame, after_time, before_time, utc_offset
        )

        # Calculate the offset for all data points
        offset = self.calculate_history_offset(user, rate_data, after_time, before_time)

        # Aggregate the gamma score
        history_data = get_history_data_from_rate_data(rate_data, offset)

        return history_data

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
    async def history(
        self,
        ctx: SlashContext,
        usernames: str = "me",
        after: Optional[str] = None,
        before: Optional[str] = None,
    ) -> None:
        """Get the transcription history of the user."""
        start = datetime.now()

        after_time, before_time, time_str = parse_time_constraints(after, before)

        utc_offset = extract_utc_offset(ctx.author.display_name)

        # Give a quick response to let the user know we're working on it
        # We'll later edit this message with the actual content
        msg = await ctx.send(
            i18n["history"]["getting_history"].format(
                users=get_initial_username_list(usernames, ctx), time_str=time_str,
            )
        )

        users = get_user_list(usernames, ctx, self.blossom_api)
        if users:
            users.sort(key=lambda u: u["gamma"], reverse=True)
        colors = get_user_colors(users)

        min_gammas = []
        max_gammas = []

        fig: plt.Figure = plt.figure()
        ax: plt.Axes = fig.gca()

        fig.subplots_adjust(bottom=0.2)
        ax.set_xlabel(
            i18n["history"]["plot_xlabel"].format(
                timezone=utc_offset_to_str(utc_offset)
            )
        )
        ax.set_ylabel(i18n["history"]["plot_ylabel"])

        for label in ax.get_xticklabels():
            label.set_rotation(32)
            label.set_ha("right")

        ax.set_title(
            i18n["history"]["plot_title"].format(
                users=get_usernames(users, 2, escape=False)
            )
        )

        for index, user in enumerate(users or [None]):
            if users and len(users) > 1:
                await msg.edit(
                    content=i18n["history"]["getting_history_progress"].format(
                        users=get_usernames(users),
                        time_str=time_str,
                        count=index + 1,
                        total=len(users),
                    )
                )

            history_data = self.get_user_history(
                user, after_time, before_time, utc_offset
            )

            color = colors[index]
            first_point = history_data.iloc[0]
            last_point = history_data.iloc[-1]

            min_gammas.append(first_point.at["gamma"])
            max_gammas.append(last_point.at["gamma"])

            # Plot the graph
            ax.plot(
                "date", "gamma", data=history_data.reset_index(), color=color,
            )
            # At a point for the last value
            ax.scatter(
                last_point.name, last_point.at["gamma"], color=color, s=4,
            )
            # Label the last value
            ax.annotate(
                int(last_point.at["gamma"]),
                xy=(last_point.name, last_point.at["gamma"]),
                color=color,
            )

        if users:
            # Show milestone lines
            min_value, max_value = min(min_gammas), max(max_gammas)
            delta = (max_value - min_value) * 0.4
            ax = add_milestone_lines(ax, ranks, min_value, max_value, delta)

        if users and len(users) > 1:
            ax.legend([get_username(user, escape=False) for user in users])

        discord_file = create_file_from_figure(fig, "history_plot.png")

        await msg.edit(
            content=i18n["history"]["response_message"].format(
                users=get_usernames(users),
                time_str=time_str,
                duration=get_duration_str(start),
            ),
            file=discord_file,
        )

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
    async def rate(
        self,
        ctx: SlashContext,
        usernames: str = "me",
        after: Optional[str] = None,
        before: Optional[str] = None,
    ) -> None:
        """Get the transcription rate of the user."""
        start = datetime.now()

        after_time, before_time, time_str = parse_time_constraints(after, before)

        utc_offset = extract_utc_offset(ctx.author.display_name)

        # Give a quick response to let the user know we're working on it
        # We'll later edit this message with the actual content
        msg = await ctx.send(
            i18n["rate"]["getting_rate"].format(
                users=get_initial_username_list(usernames, ctx), time_str=time_str,
            )
        )

        users = get_user_list(usernames, ctx, self.blossom_api)
        if users:
            users.sort(key=lambda u: u["gamma"], reverse=True)
        colors = get_user_colors(users)

        max_rates = []

        fig: plt.Figure = plt.figure()
        ax: plt.Axes = fig.gca()

        fig.subplots_adjust(bottom=0.2)
        ax.set_xlabel(
            i18n["rate"]["plot_xlabel"].format(timezone=utc_offset_to_str(utc_offset))
        )
        ax.set_ylabel(i18n["rate"]["plot_ylabel"])

        for label in ax.get_xticklabels():
            label.set_rotation(32)
            label.set_ha("right")

        ax.set_title(
            i18n["rate"]["plot_title"].format(
                users=get_usernames(users, 2, escape=False)
            )
        )

        for index, user in enumerate(users or [None]):
            if users and len(users) > 1:
                await msg.edit(
                    content=i18n["rate"]["getting_rate"].format(
                        users=get_usernames(users),
                        count=index + 1,
                        total=len(users),
                        time_str=time_str,
                    )
                )

            user_data = self.get_all_rate_data(
                user, "day", after_time, before_time, utc_offset
            )

            max_rate = user_data["count"].max()
            max_rates.append(max_rate)
            max_rate_point = user_data[user_data["count"] == max_rate].iloc[0]

            color = colors[index]

            # Plot the graph
            ax.plot(
                "date", "count", data=user_data.reset_index(), color=color,
            )
            # At a point for the max value
            ax.scatter(
                max_rate_point.name, max_rate_point.at["count"], color=color, s=4,
            )
            # Label the max value
            ax.annotate(
                int(max_rate_point.at["count"]),
                xy=(max_rate_point.name, max_rate_point.at["count"]),
                color=color,
            )

        if users:
            # A milestone at every 100 rate
            milestones = [
                dict(threshold=i * 100, color=ranks[i + 2]["color"])
                for i in range(1, 8)
            ]
            ax = add_milestone_lines(ax, milestones, 0, max(max_rates), 40)

        if users and len(users) > 1:
            ax.legend([get_username(user, escape=False) for user in users])

        discord_file = create_file_from_figure(fig, "rate_plot.png")

        await msg.edit(
            content=i18n["rate"]["response_message"].format(
                usernames=get_usernames(users),
                time_str=time_str,
                duration=get_duration_str(start),
            ),
            file=discord_file,
        )

    async def _until_user_catch_up(
        self,
        ctx: SlashContext,
        msg: SlashMessage,
        user: BlossomUser,
        target_username: str,
        start: datetime,
        after_time: datetime,
        before_time: Optional[datetime],
        time_str: str,
    ) -> None:
        """Determine how long it will take the user to catch up with the target user."""
        # Try to find the target user
        try:
            target = get_user(target_username, ctx, self.blossom_api)
        except UserNotFound:
            # This doesn't mean the username is wrong
            # They could have also mistyped a rank
            # So we change the error message to something else
            raise InvalidArgumentException("goal", target_username)

        if not target:
            # Having the combined server as target doesn't make sense
            # Because it includes the current user, they could never reach it
            raise InvalidArgumentException("goal", target_username)

        if user["gamma"] > target["gamma"]:
            # Swap user and target, the target has to have more gamma
            # Otherwise the goal would have already been reached
            user, target = target, user

        user_progress = await _get_user_progress(
            user, after_time, before_time, blossom_api=self.blossom_api
        )
        target_progress = await _get_user_progress(
            target, after_time, before_time, blossom_api=self.blossom_api
        )

        time_frame = (before_time or start) - after_time

        if user_progress <= target_progress:
            description = i18n["until"]["embed_description_user_never"].format(
                user=get_username(user),
                user_gamma=user["gamma"],
                user_progress=user_progress,
                target=get_username(target),
                target_gamma=target["gamma"],
                target_progress=target_progress,
                time_frame=get_timedelta_str(time_frame),
            )
        else:
            # Calculate time needed
            seconds_needed = (target["gamma"] - user["gamma"]) / (
                (user_progress - target_progress) / time_frame.total_seconds()
            )
            relative_time = timedelta(seconds=seconds_needed)
            absolute_time = start + relative_time

            intersection_gamma = user["gamma"] + math.ceil(
                (user_progress / time_frame.total_seconds())
                * relative_time.total_seconds()
            )

            description = i18n["until"]["embed_description_user_prediction"].format(
                user=get_username(user),
                user_gamma=user["gamma"],
                user_progress=user_progress,
                target=get_username(target),
                target_gamma=target["gamma"],
                target_progress=target_progress,
                intersection_gamma=intersection_gamma,
                time_frame=get_timedelta_str(time_frame),
                relative_time=get_timedelta_str(relative_time),
                absolute_time=get_discord_time_str(absolute_time),
            )

        color = get_rank(target["gamma"])["color"]

        await msg.edit(
            content=i18n["until"]["embed_message"].format(
                user=get_username(user),
                goal=get_username(target),
                time_str=time_str,
                duration=get_duration_str(start),
            ),
            embed=Embed(
                title=i18n["until"]["embed_title"].format(user=get_username(user)),
                description=description,
                color=discord.Colour.from_rgb(*get_rgb_from_hex(color)),
            ),
        )

    @cog_ext.cog_slash(
        name="until",
        description="Determines the time required to reach the next milestone.",
        options=[
            create_option(
                name="goal",
                description="The gamma, flair rank or user to reach. "
                "Defaults to the next rank.",
                option_type=3,
                required=False,
            ),
            create_option(
                name="username",
                description="The user to make the prediction for. "
                "Defaults to the user executing the command.",
                option_type=3,
                required=False,
            ),
            create_option(
                name="after",
                description="The start date for the prediction data.",
                option_type=3,
                required=False,
            ),
            create_option(
                name="before",
                description="The end date for the prediction data.",
                option_type=3,
                required=False,
            ),
        ],
    )
    async def _until(
        self,
        ctx: SlashContext,
        goal: Optional[str] = None,
        username: str = "me",
        after: str = "1 week",
        before: Optional[str] = None,
    ) -> None:
        """Determine how long it will take the user to reach the given goal."""
        start = datetime.now(tz=pytz.utc)

        after_time, before_time, time_str = parse_time_constraints(after, before)

        if not after_time:
            # We need a starting point for the calculations
            raise InvalidArgumentException("after", after)

        # Send a first message to show that the bot is responsive.
        # We will edit this message later with the actual content.
        msg = await ctx.send(
            i18n["until"]["getting_prediction"].format(
                user=get_initial_username(username, ctx), time_str=time_str,
            )
        )

        user = get_user(username, ctx, self.blossom_api)

        if goal is not None:
            try:
                # Check if the goal is a gamma value or rank name
                goal_gamma, goal_str = parse_goal_str(goal)
            except InvalidArgumentException:
                # The goal could be a username
                if not user:
                    # If the user is the combined server, a target user doesn't make sense
                    raise InvalidArgumentException("goal", goal)

                # Try to treat the goal as a user
                return await self._until_user_catch_up(
                    ctx, msg, user, goal, start, after_time, before_time, time_str,
                )
        elif user:
            # Take the next rank for the user
            next_rank = get_next_rank(user["gamma"])
            if next_rank:
                goal_gamma, goal_str = parse_goal_str(next_rank["name"])
            else:
                # If the user has reached the maximum rank, take the next 10,000 tier
                goal_gamma = ((user["gamma"] + 10_000) // 10_000) * 10_000
                goal_str = f"{goal_gamma:,}"
        else:
            # You can't get the "next rank" of the whole server
            raise InvalidArgumentException("goal", "<empty>")

        user_gamma = get_user_gamma(user, self.blossom_api)

        await msg.edit(
            content=i18n["until"]["getting_prediction_to_goal"].format(
                user=get_username(user), goal=goal_str, time_str=time_str,
            )
        )

        description = await _get_progress_description(
            user,
            user_gamma,
            goal_gamma,
            goal_str,
            start,
            after_time,
            before_time,
            blossom_api=self.blossom_api,
        )

        # Determine the color of the target rank
        color = get_rank(goal_gamma)["color"]

        await msg.edit(
            content=i18n["until"]["embed_message"].format(
                user=get_username(user),
                goal=goal_str,
                time_str=time_str,
                duration=get_duration_str(start),
            ),
            embed=Embed(
                title=i18n["until"]["embed_title"].format(user=get_username(user)),
                description=description,
                color=discord.Colour.from_rgb(*get_rgb_from_hex(color)),
            ),
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
