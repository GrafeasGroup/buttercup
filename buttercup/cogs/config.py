from typing import Any, Dict

from buttercup.bot import ButtercupBot

config: Dict[str, Any] = {}


def setup(bot: ButtercupBot) -> None:
    """Set up the config globally.

    This is a hack to be able to use it in annotations for other commands.
    This cog needs to be loaded first for it to work correctly!
    """
    global config
    config = bot.config


def teardown(bot: ButtercupBot) -> None:
    """Reset the global config."""
    global config
    config = {}
