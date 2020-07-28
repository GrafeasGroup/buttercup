from collections import defaultdict
from typing import Any, Dict

import discord.utils
import toml
from discord.ext.commands import Bot
from discord.guild import Guild


class ButtercupBot(Bot):
    def __init__(self, command_prefix: str, **kwargs: Any) -> None:
        """
        Initialize the BubblesBot.

        Along the arguments which can be provided to discord.py's Bot class,
        one can provide:
        - config_path (default: config.toml): The path to the configuration file
        - cog_path (default: buttercup.cogs): The path to the application cogs
        - extensions (default: list): list of extensions to load
        """
        super().__init__(command_prefix, **kwargs)
        self.config_path = kwargs.get("config_path", "config.toml")
        self.cog_path = kwargs.get("cog_path", "buttercup.cogs.")
        self.guild_name = self.config["guild"]["name"]

        for extension in kwargs.get("extensions", list()):
            print(f"Loading extension {extension}...")
            self.load_extension(f"{self.cog_path}{extension}")

    async def on_ready(self) -> None:
        """Log a starting message when the bot is ready."""
        print(f"Connected as {self.user} to '{self.guild}'")

    @property
    def config(self) -> Dict[str, Any]:
        """Provide the configuration loaded from the specified file."""
        return defaultdict(dict, toml.load(self.config_path))

    @property
    def guild(self) -> Guild:
        """Retrieve the guild corresponding to the set name."""
        return discord.utils.get(self.guilds, name=self.guild_name)

    async def reload_extension(self, name: str) -> None:
        """Reload the extension with the specified name."""
        super().reload_extension(f"{self.cog_path}{name}")
