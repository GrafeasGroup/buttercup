import pathlib
import sys

import click
from click.core import Context

from buttercup import __version__, logger
from buttercup.bot import ButtercupBot

EXTENSIONS = [
    # The config cog has to be first!
    "config",
    "admin",
    "handlers",
    "welcome",
    "name_validator",
    "find",
    "search",
    "stats",
    "heatmap",
    "history",
    "ping",
    "rules",
    "leaderboard",
    "queue",
]


@click.group(
    context_settings=dict(help_option_names=["-h", "--help", "--halp"]),
    invoke_without_command=True,
)
@click.pass_context
@click.option(
    "-c",
    "--config",
    "config_path",
    default="config.toml",
    help="Path to the config file to use. Default: config.toml",
)
@click.version_option(version=__version__, prog_name="buttercup")
def main(ctx: Context, config_path: str) -> None:
    """Run Buttercup."""
    # If we didn't ask for a specific command, run the bot. Otherwise, ignore this
    # and fall through to the command we requested.
    if ctx.invoked_subcommand is None:
        logger.configure_logging()
        bot = ButtercupBot(
            command_prefix="!", config_path=config_path, extensions=EXTENSIONS
        )
        bot.run(bot.config["Discord"]["token"])


@main.command()
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Show Pytest output instead of running quietly.",
)
def selfcheck(verbose: bool) -> None:
    """
    Verify the binary passes all tests internally.

    Add any other self-check related code here.
    """
    import pytest

    import buttercup.test

    # -x is 'exit immediately if a test fails'
    # We need to get the path because the file is actually inside the extracted
    # environment maintained by shiv, not physically inside the archive at the
    # time of running.
    args = ["-x", pathlib.Path(buttercup.test.__file__).parent]
    if not verbose:
        args.append("-qq")
    # pytest will return an exit code that we can check on the command line
    sys.exit(pytest.main(args))


BANNER = r"""
__________        __    __
\______   \__ ___/  |__/  |_  ___________   ____  __ ________
 |    |  _/  |  \   __\   __\/ __ \_  __ \_/ ___\|  |  \____ \
 |    |   \  |  /|  |  |  | \  ___/|  | \/\  \___|  |  /  |_> >
 |______  /____/ |__|  |__|  \___  >__|    \___  >____/|   __/
        \/                       \/            \/      |__|
"""


@main.command()
def shell() -> None:
    """Create a Python REPL inside the environment."""
    import code

    code.interact(local=globals(), banner=BANNER)


if __name__ == "__main__":
    main()
