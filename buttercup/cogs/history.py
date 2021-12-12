import io
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

import discord
import matplotlib.pyplot as plt
import pandas as pd
import pytz
from blossom_wrapper import BlossomAPI, BlossomStatus
from dateutil import parser
from dateutil.tz import tzutc
from discord import Embed, File
from discord.ext.commands import Cog
from discord_slash import SlashContext, cog_ext
from discord_slash.model import SlashMessage
from discord_slash.utils.manage_commands import create_option

from buttercup.bot import ButtercupBot
from buttercup.cogs import ranks
from buttercup.cogs.helpers import (
    BlossomException,
    BlossomUser,
    InvalidArgumentException,
    extract_username,
    get_duration_str,
    get_initial_username_list,
    get_rank,
    get_rgb_from_hex,
    get_timedelta_str,
    get_user_id,
    get_user_list,
    get_username,
    get_usernames,
    parse_time_constraints,
)
from buttercup.strings import translation

i18n = translation()


def get_data_granularity(
    user: Dict, after: Optional[datetime], before: Optional[datetime]
) -> str:
    """Determine granularity of the graph.

    It should be as detailed as possible, but only require 1 API call in the best case.
    """
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


def get_next_rank(gamma: int) -> Dict[str, Union[str, int]]:
    """Determine the next rank based on the current gamma."""
    for rank in ranks:
        if rank["threshold"] > gamma:
            return rank

    # TODO: How to handle if the user reached the highest rank?


def parse_goal_str(goal_str: str) -> Tuple[int, str]:
    """Parse the given goal string.

    :returns: The goal gamma and the goal string.
    """
    goal_str = goal_str.strip()

    if goal_str.isnumeric():
        return int(goal_str, 10), goal_str

    for rank in ranks:
        if goal_str.casefold() == rank["name"].casefold():
            return rank["threshold"], f"{rank['name']} ({rank['threshold']})"

    raise InvalidArgumentException("goal", goal_str)


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
                    "from": from_str,
                    "until": until_str,
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
        user: BlossomUser,
        rate_data: pd.DataFrame,
        after_time: Optional[datetime],
        before_time: Optional[datetime],
    ) -> int:
        """Calculate the gamma offset for the history graph.

        Note: We always need to do this, because it might be the case that some
        transcriptions don't have a date set.
        """
        if before_time is not None:
            # We need to get the offset from the API
            offset_response = self.blossom_api.get(
                "submission/",
                params={
                    "completed_by": get_user_id(user),
                    "from": before_time.isoformat(),
                    "page_size": 1,
                },
            )
            if offset_response.status_code == 200:
                # We still need to calculate based on the total gamma
                # It may be the case that not all transcriptions have a date set
                # Then they are not included in the data nor in the API response
                return user["gamma"] - rate_data.sum() - offset_response.json()["count"]
        else:
            # We can calculate the offset from the given data
            return user["gamma"] - rate_data.sum()

    def get_user_history(
        self,
        user: BlossomUser,
        after_time: Optional[datetime],
        before_time: Optional[datetime],
    ) -> Tuple[int, pd.DataFrame]:
        """Get a data frame representing the history of the user.

        :returns: The gamma of the user and their history data.
        """
        # Get all rate data
        time_frame = get_data_granularity(user, after_time, before_time)
        rate_data = self.get_all_rate_data(user, time_frame, after_time, before_time)

        # Calculate the offset for all data points
        offset = self.calculate_history_offset(user, rate_data, after_time, before_time)

        # Aggregate the gamma score
        history_data = get_history_data_from_rate_data(rate_data, offset)

        return user["gamma"], history_data

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
        usernames: str = "me",
        after: Optional[str] = None,
        before: Optional[str] = None,
    ) -> None:
        """Get the transcription history of the user."""
        start = datetime.now()

        after_time, before_time, time_str = parse_time_constraints(after, before)

        # Give a quick response to let the user know we're working on it
        # We'll later edit this message with the actual content
        msg = await ctx.send(
            i18n["history"]["getting_history"].format(
                users=get_initial_username_list(usernames, ctx), time_str=time_str,
            )
        )

        users = get_user_list(usernames, ctx, self.blossom_api)

        min_gammas = []
        max_gammas = []

        fig: plt.Figure = plt.figure()
        ax: plt.Axes = fig.gca()

        fig.subplots_adjust(bottom=0.2)
        ax.set_xlabel(i18n["history"]["plot_xlabel"])
        ax.set_ylabel(i18n["history"]["plot_ylabel"])

        for label in ax.get_xticklabels():
            label.set_rotation(32)
            label.set_ha("right")

        ax.set_title(
            i18n["history"]["plot_title"].format(
                users=get_usernames(users, 2, escape=False)
            )
        )

        for index, user in enumerate(users):
            if len(users) > 1:
                await msg.edit(
                    content=i18n["history"]["getting_history_progress"].format(
                        users=get_usernames(users),
                        time_str=time_str,
                        count=index + 1,
                        total=len(users),
                    )
                )

            user_gamma, history_data = self.get_user_history(
                user, after_time, before_time
            )

            color = ranks[index]["color"]
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

        # Show ranks when you are close to them already
        min_value, max_value = min(min_gammas), max(max_gammas)
        delta = (max_value - min_value) * 0.4
        ax = add_milestone_lines(ax, ranks, min_value, max_value, delta)

        if len(users) > 1:
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

    def get_user_rate(
        self,
        user: BlossomUser,
        after_time: Optional[datetime],
        before_time: Optional[datetime],
    ) -> pd.DataFrame:
        """Get a data frame representing the transcription rate of the user.

        :returns: The rate data of the user.
        """
        # Get all rate data
        rate_data = self.get_all_rate_data(user, "day", after_time, before_time)

        # Add an up-to-date entry
        today = datetime.now(tz=tzutc()).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        if today not in rate_data.index:
            rate_data.loc[today] = [0]

        return rate_data

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
        usernames: str = "me",
        after: Optional[str] = None,
        before: Optional[str] = None,
    ) -> None:
        """Get the transcription rate of the user."""
        start = datetime.now()

        after_time, before_time, time_str = parse_time_constraints(after, before)

        # Give a quick response to let the user know we're working on it
        # We'll later edit this message with the actual content
        msg = await ctx.send(
            i18n["rate"]["getting_rate"].format(
                users=get_initial_username_list(usernames, ctx), time_str=time_str,
            )
        )

        users = get_user_list(usernames, ctx, self.blossom_api)

        max_rates = []

        fig: plt.Figure = plt.figure()
        ax: plt.Axes = fig.gca()

        fig.subplots_adjust(bottom=0.2)
        ax.set_xlabel(i18n["rate"]["plot_xlabel"])
        ax.set_ylabel(i18n["rate"]["plot_ylabel"])

        for label in ax.get_xticklabels():
            label.set_rotation(32)
            label.set_ha("right")

        ax.set_title(
            i18n["rate"]["plot_title"].format(
                users=get_usernames(users, 2, escape=False)
            )
        )

        for index, user in enumerate(users):
            if len(users) > 1:
                await msg.edit(
                    content=i18n["rate"]["getting_rate"].format(
                        users=get_usernames(users),
                        count=index + 1,
                        total=len(users),
                        time_str=time_str,
                    )
                )

            user_data = self.get_user_rate(user, after_time, before_time)

            max_rate = user_data["count"].max()
            max_rates.append(max_rate)
            max_rate_point = user_data[user_data["count"] == max_rate].iloc[0]

            color = ranks[index]["color"]

            # Plot the graph
            ax.plot(
                "date", "count", data=user_data.reset_index(), color=color,
            )
            # At a point for the max value
            ax.scatter(
                max_rate_point.name, max_rate_point.at["count"], color=color, s=4,
            )
            # Label the last value
            ax.annotate(
                int(max_rate_point.at["count"]),
                xy=(max_rate_point.name, max_rate_point.at["count"]),
                color=color,
            )

        # A milestone at every 100 rate
        milestones = [
            dict(threshold=i * 100, color=ranks[i + 2]["color"]) for i in range(1, 8)
        ]
        ax = add_milestone_lines(ax, milestones, 0, max(max_rates), 40)

        if len(users) > 1:
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

    async def _get_user_progress(
        self, user: Dict[str, Any], start: datetime, time_frame: timedelta
    ) -> int:
        # We ask for submission completed by the user in the time frame
        # The response will contain a count, so we just need 1 result
        progress_response = self.blossom_api.get(
            "submission/",
            params={
                "completed_by": user["id"],
                "from": (start - time_frame).isoformat(),
                "page_size": 1,
            },
        )
        if progress_response.status_code != 200:
            raise RuntimeError("Failed to get progress")
        return progress_response.json()["count"]

    async def _until_user_catch_up(
        self,
        msg: SlashMessage,
        user: Dict[str, Any],
        target_username: str,
        start: datetime,
    ) -> None:
        """Determine how long it will take the user to catch up with the target user."""
        # Try to find the target user
        target_response = self.blossom_api.get_user(target_username)
        if target_response.status != BlossomStatus.ok:
            raise InvalidArgumentException("goal", target_username)

        target = target_response.data

        if user["gamma"] > target["gamma"]:
            # Swap user and target, the target has to have more gamma
            # Otherwise the goal would have already been reached
            user, target = target, user

        time_frame = timedelta(weeks=1)

        try:
            user_progress = await self._get_user_progress(user, start, time_frame)
            target_progress = await self._get_user_progress(target, start, time_frame)
        except RuntimeError:
            await msg.edit(
                content=i18n["until"]["failed_getting_prediction"].format(user=user)
            )
            return

        if user_progress <= target_progress:
            description = i18n["until"]["embed_description_user_never"].format(
                user=user["username"],
                user_gamma=user["gamma"],
                user_progress=user_progress,
                target=target["username"],
                target_gamma=target["gamma"],
                target_progress=target_progress,
                time_frame="week",
            )
        else:
            # Calculate time needed
            seconds_needed = (target["gamma"] - user["gamma"]) / (
                (user_progress - target_progress) / time_frame.total_seconds()
            )
            time_needed = timedelta(seconds=seconds_needed)

            intersection_gamma = user["gamma"] + math.ceil(
                (user_progress / time_frame.total_seconds())
                * time_needed.total_seconds()
            )

            description = i18n["until"]["embed_description_user_prediction"].format(
                user=user["username"],
                user_gamma=user["gamma"],
                user_progress=user_progress,
                target=target["username"],
                target_gamma=target["gamma"],
                target_progress=target_progress,
                intersection_gamma=intersection_gamma,
                time_frame=get_timedelta_str(time_frame),
                time_needed=get_timedelta_str(time_needed),
            )

        color = get_rank(target["gamma"])["color"]

        await msg.edit(
            content=i18n["until"]["embed_message"].format(
                duration=get_duration_str(start)
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
        ],
    )
    async def _until(
        self,
        ctx: SlashContext,
        goal: Optional[str] = None,
        username: Optional[str] = None,
    ) -> None:
        """Determine how long it will take the user to reach the given goal."""
        start = datetime.now()
        username = username or extract_username(ctx.author.display_name)

        # Send a first message to show that the bot is responsive.
        # We will edit this message later with the actual content.
        msg = await ctx.send(i18n["until"]["getting_prediction"].format(user=username))

        user_response = self.blossom_api.get_user(username)
        if user_response.status != BlossomStatus.ok:
            await msg.edit(content=i18n["until"]["user_not_found"].format(username))
            return
        user = user_response.data
        username = user["username"]

        if goal is not None:
            try:
                goal_gamma, goal_str = parse_goal_str(goal)
            except InvalidArgumentException:
                return await self._until_user_catch_up(msg, user, goal, start)
        else:
            # Take the next rank for the user
            next_rank = get_next_rank(user["gamma"])
            goal_gamma, goal_str = (
                next_rank["threshold"],
                f"{next_rank['name']} ({next_rank['threshold']})",
            )

        await msg.edit(
            content=i18n["until"]["getting_prediction_to_goal"].format(
                user=username, goal_gamma=goal_str
            )
        )

        if user["gamma"] == 0:
            # The user has not started transcribing yet
            await msg.edit(
                content=i18n["until"]["embed_message"].format(
                    duration=get_duration_str(start)
                ),
                embed=Embed(
                    title=i18n["until"]["embed_title"].format(user=username),
                    description=i18n["until"]["embed_description_new"].format(
                        user=username
                    ),
                ),
            )
            return

        time_frame = timedelta(weeks=1)

        try:
            user_progress = await self._get_user_progress(user, start, time_frame)
        except RuntimeError:
            await msg.edit(
                content=i18n["until"]["failed_getting_prediction"].format(user=username)
            )
            return

        if user["gamma"] >= goal_gamma:
            # The user has already reached the goal
            description = i18n["until"]["embed_description_reached"].format(
                time_frame="week",
                user=username,
                user_gamma=user["gamma"],
                goal=goal_str,
                user_progress=user_progress,
            )
        elif user_progress == 0:
            description = i18n["until"]["embed_description_zero"].format(
                time_frame=get_timedelta_str(time_frame),
                user=username,
                user_gamma=user["gamma"],
                goal=goal_str,
            )
        else:
            # Based on the progress in the timeframe, calculate the time needed
            gamma_needed = goal_gamma - user["gamma"]
            time_needed = timedelta(
                seconds=gamma_needed * (time_frame.total_seconds() / user_progress)
            )

            description = i18n["until"]["embed_description_prediction"].format(
                time_frame="week",
                user=username,
                user_gamma=user["gamma"],
                goal=goal_str,
                user_progress=user_progress,
                time_needed=get_timedelta_str(time_needed),
            )

        # Determine the color of the target rank
        color = get_rank(goal_gamma)["color"]

        await msg.edit(
            content=i18n["until"]["embed_message"].format(
                duration=get_duration_str(start)
            ),
            embed=Embed(
                title=i18n["until"]["embed_title"].format(user=username),
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
