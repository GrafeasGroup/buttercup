import logging
from typing import Dict

from discord.ext.commands import Context

_logger = logging.getLogger("Buttercup Logger")


def configure_logging() -> None:
    """Set the configuration for logging.

    Note that a custom set of methods is provided, where the Context is provided. This is
    used to retrieve the command and user for the logging message. This file should be
    used instead of the "logging" module.
    """
    formatter = logging.Formatter(
        "%(asctime)-15s | %(levelname)7s | %(user)23s | %(command)10s | %(message)s"
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    _logger.addHandler(console_handler)

    logging.getLogger().setLevel(logging.INFO)
    logging.basicConfig(format="%(asctime)-15s | %(levelname)7s | %(message)s")


def critical(message: str, ctx: Context = None) -> None:
    """Log a critical message using the provided Context."""
    _logger.critical(message, extra=_retrieve_logging_fields(ctx))


def error(message: str, ctx: Context = None) -> None:
    """Log an error message using the provided Context."""
    _logger.error(message, extra=_retrieve_logging_fields(ctx))


def warning(message: str, ctx: Context = None) -> None:
    """Log a warning message using the provided Context."""
    _logger.warning(message, extra=_retrieve_logging_fields(ctx))


def info(message: str, ctx: Context = None) -> None:
    """Log an information message using the provided Context."""
    _logger.info(message, extra=_retrieve_logging_fields(ctx))


def debug(message: str, ctx: Context = None) -> None:
    """Log a debug message using the provided Context."""
    _logger.debug(message, extra=_retrieve_logging_fields(ctx))


def _retrieve_logging_fields(ctx: Context = None) -> Dict:
    if ctx is None:
        return {"user": "", "command": ""}
    return {
        "user": ctx.author.display_name,
        "command": ctx.invoked_with,
    }
