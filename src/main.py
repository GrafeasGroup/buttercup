import sys

from src import logger
from src.bot import ButtercupBot

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


logger.configure_logging()
config_path = sys.argv[1] if len(sys.argv) > 1 else "config.toml"
bot = ButtercupBot(command_prefix="!", config_path=config_path, extensions=EXTENSIONS)
bot.run(bot.config["Discord"]["token"])
