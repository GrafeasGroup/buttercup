import logging
from collections import defaultdict
from typing import Any, Dict

import discord.utils
import toml
from discord.ext.commands import Bot
from discord.guild import Guild
from discord_slash import SlashCommand


class ButtercupBot(Bot):
    def __init__(self, command_prefix: str, **kwargs: Any) -> None:
        """
        Initialize the ButtercupBot.

        Along the arguments which can be provided to discord.py's Bot class,
        one can provide:
        - config_path (default: config.toml): The path to the configuration file
        - cog_path (default: buttercup.cogs): The path to the application cogs
        - extensions (default: list): list of extensions to load
        """
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(command_prefix, intents=intents, **kwargs)
        self.slash = SlashCommand(self, sync_commands=True, sync_on_cog_reload=True)
        self.config_path = kwargs.get("config_path", "../config.toml")
        self.cog_path = kwargs.get("cog_path", "buttercup.cogs.")
        self.guild_name = self.config["guild"]["name"]

        for extension in kwargs.get("extensions", list()):
            logging.info(f"Loading extension {extension}...")
            self.load(extension)

    async def on_ready(self) -> None:
        """Log a starting message when the bot is ready."""
        logging.info(f"Connected as {self.user} to '{self.guild}'")

    @property
    def config(self) -> Dict[str, Any]:
        """Provide the configuration loaded from the specified file."""
        return defaultdict(dict, toml.load(self.config_path))

    @property
    def guild(self) -> Guild:
        """Retrieve the guild corresponding to the set name."""
        return discord.utils.get(self.guilds, name=self.guild_name)

    def load(self, name: str) -> None:
        """Load the extension with the specified name."""
        if name:
            super().load_extension(f"{self.cog_path}{name}")

    def reload(self, name: str) -> None:
        """Reload the extension with the specified name."""
        if name:
            super().reload_extension(f"{self.cog_path}{name}")

    def unload(self, name: str) -> None:
        """Unload the extension with the specified name."""
        if name:
            super().unload_extension(f"{self.cog_path}{name}")
