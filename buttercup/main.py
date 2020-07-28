import sys

from buttercup.bot import ButtercupBot

EXTENSIONS = ["admin", "new_member"]


config_path = sys.argv[1] if len(sys.argv) > 1 else "config.toml"
bot = ButtercupBot(command_prefix="!", config_path=config_path, extensions=EXTENSIONS)
bot.run(bot.config["secrets"]["discord"])
