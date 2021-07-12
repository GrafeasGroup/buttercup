import io
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, Union

import matplotlib.pyplot as plt
import pandas as pd
from blossom_wrapper import BlossomAPI, BlossomStatus
from dateutil import parser
from dateutil.tz import tzutc
from discord import Embed, File
from discord.ext.commands import Cog
from discord_slash import SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_option

from buttercup.bot import ButtercupBot
from buttercup.cogs import ranks
from buttercup.cogs.helpers import (
    BlossomException,
    InvalidArgumentException,
    extract_username,
    get_duration_str,
    get_timedelta_str,
    join_items_with_and,
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


def add_rank_lines(ax: plt.Axes, gamma: int) -> plt.Axes:
    """Add the rank lines to the given axes."""
    # Show ranks when you are close to them already
    threshold_factor = 0.7
    for rank in ranks:
        if gamma >= rank["threshold"] * threshold_factor:
            ax.axhline(y=rank["threshold"], color=rank["color"], zorder=-1)
    return ax


def create_file_from_figure(fig: plt.Figure, file_name: str) -> File:
    """Create a Discord file containing the figure."""
    history_plot = io.BytesIO()

    fig.savefig(history_plot, format="png")
    history_plot.seek(0)
    plt.close(fig)

    return File(history_plot, file_name)


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

    def get_user_history(self, user: str) -> Tuple[int, pd.DataFrame]:
        """Get a data frame representing the history of the user.

        :returns: The gamma of the user and their history data.
        """
        page_size = 500

        # First, get the total gamma for the user
        user_response = self.blossom_api.get_user(user)
        if user_response.status != BlossomStatus.ok:
            raise BlossomException(user_response)

        user_gamma = user_response.data["gamma"]
        user_id = user_response.data["id"]

        time_frame = get_data_granularity(user_gamma)

        # Get all rate data
        user_data = pd.DataFrame(columns=["date", "count"]).set_index("date")
        page = 1
        # Placeholder until we get the real value from the response
        next_page = "1"

        while next_page is not None:
            response = self.blossom_api.get(
                f"volunteer/{user_id}/rate",
                params={"page": page, "page_size": page_size, "time_frame": time_frame},
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

        user_data = add_zero_rates(user_data, time_frame)

        # Add an up-to-date entry
        user_data.loc[datetime.now(tz=tzutc())] = [0]
        # Aggregate the gamma score
        user_data = user_data.assign(gamma=user_data.expanding(1).sum())

        return user_gamma, user_data

    @cog_ext.cog_slash(
        name="history",
        description="Display the history graph.",
        options=[
            create_option(
                name="user_1",
                description="The user to display the history graph for.",
                option_type=3,
                required=False,
            ),
            create_option(
                name="user_2",
                description="The second user to add to the graph.",
                option_type=3,
                required=False,
            ),
            create_option(
                name="user_3",
                description="The third user to add to the graph.",
                option_type=3,
                required=False,
            ),
        ],
    )
    async def _history(
        self,
        ctx: SlashContext,
        user_1: Optional[str] = None,
        user_2: Optional[str] = None,
        user_3: Optional[str] = None,
    ) -> None:
        """Find the post with the given URL."""
        # Give a quick response to let the user know we're working on it
        # We'll later edit this message with the actual content
        start = datetime.now()

        username_1 = user_1 or extract_username(ctx.author.display_name)
        users = [user for user in [username_1, user_2, user_3] if user is not None]
        usernames = join_items_with_and([f"u/{user}" for user in users])
        if len(users) == 1:
            msg = await ctx.send(
                i18n["history"]["getting_history_single"].format(user=username_1)
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
            ax.set_title(i18n["history"]["plot_title_single"].format(user=username_1))
        else:
            ax.set_title(i18n["history"]["plot_title_multi"])

        for index, user in enumerate(users):
            if len(users) > 1:
                await msg.edit(
                    content=i18n["history"]["getting_history_multi"].format(
                        users=usernames, count=index + 1, total=len(users)
                    )
                )

            user_gamma, user_data = self.get_user_history(user)
            user_gammas.append(user_gamma)

            # Plot the graph
            ax.plot(
                "date",
                "gamma",
                data=user_data.reset_index(),
                color=ranks[index]["color"],
            )

        add_rank_lines(ax, max(user_gammas))
        if len(users) > 1:
            ax.legend([f"u/{user}" for user in users])

        discord_file = create_file_from_figure(fig, "history_plot.png")

        await msg.edit(
            content=i18n["history"]["response_message"].format(
                duration=get_duration_str(start)
            ),
            file=discord_file,
        )

    @cog_ext.cog_slash(
        name="until",
        description="Determines the time required to reach the next milestone.",
        options=[
            create_option(
                name="goal",
                description="The gamma or flair rank to reach. "
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
        user = username or extract_username(ctx.author.display_name)

        # Send a first message to show that the bot is responsive.
        # We will edit this message later with the actual content.
        msg = await ctx.send(i18n["until"]["getting_prediction"].format(user=user))

        volunteer_response = self.blossom_api.get_user(user)
        if volunteer_response.status != BlossomStatus.ok:
            await msg.edit(content=i18n["until"]["user_not_found"].format(user))
            return
        volunteer_id = volunteer_response.data["id"]
        gamma = volunteer_response.data["gamma"]

        if goal is not None:
            goal_gamma, goal_str = parse_goal_str(goal)
        else:
            # Take the next rank for the user
            next_rank = get_next_rank(gamma)
            goal_gamma, goal_str = (
                next_rank["threshold"],
                f"{next_rank['name']} ({next_rank['threshold']})",
            )

        await msg.edit(
            content=i18n["until"]["getting_prediction_to_goal"].format(
                user=user, goal_gamma=goal_str
            )
        )

        if gamma == 0:
            # The user has not started transcribing yet
            await msg.edit(
                content=i18n["until"]["embed_message"].format(
                    duration=get_duration_str(start)
                ),
                embed=Embed(
                    title=i18n["until"]["embed_title"].format(user),
                    description=i18n["until"]["embed_description_new"].format(
                        user=user
                    ),
                ),
            )
            return

        time_frames = [
            (timedelta(hours=24), "day"),
            (timedelta(weeks=1), "week"),
            (timedelta(days=30), "month"),
            (timedelta(days=365), "year"),
        ]

        predictions = []

        for delta, unit in time_frames:
            # We ask for submission completed by the user in the time frame
            # The response will contain a count, so we just need 1 result
            progress_response = self.blossom_api.get(
                "submission/",
                params={
                    "completed_by": volunteer_id,
                    "from": (start - delta).isoformat(),
                    "page_size": 1,
                },
            )
            if progress_response.status_code != 200:
                await msg.edit(
                    content=i18n["until"]["failed_getting_prediction"].format(user=user)
                )
                return
            progress_count = progress_response.json()["count"]

            if progress_count == 0:
                predictions.append(
                    i18n["until"]["prediction_zero"].format(time_frame=unit,)
                )
            else:
                # Based on the progress in the timeframe, calculate the time needed
                gamma_needed = goal_gamma - gamma
                time_needed = timedelta(
                    seconds=gamma_needed * (delta.total_seconds() / progress_count)
                )

                predictions.append(
                    i18n["until"]["prediction"].format(
                        progress=progress_count,
                        time_frame=unit,
                        time_needed=get_timedelta_str(time_needed),
                    )
                )

        await msg.edit(
            content=i18n["until"]["embed_message"].format(
                duration=get_duration_str(start)
            ),
            embed=Embed(
                title=i18n["until"]["embed_title"].format(user=user),
                description=i18n["until"]["embed_description"].format(
                    cur_gamma=gamma,
                    goal_gamma=goal_str,
                    predictions="\n".join(predictions),
                ),
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
