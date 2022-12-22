import logging
import os
from time import sleep

from client import EsportsBot

__all__ = ["start_bot"]
logger = logging.getLogger(__name__)


def start_bot():
    """Performs final checks before running the bot and if successful, starts the bot.

    Raises:
        RuntimeError: If DISCORD_TOKEN environment variable is missing.
    """
    logger.info("Loading bot...")

    if not os.getenv("DISCORD_TOKEN"):
        raise RuntimeError("Missing required `DISCORD_TOKEN` environment variable!")

    if not os.getenv("DEV_GUILD_ID"):
        logger.warning("No Dev guild specified, waiting 5s before starting...")
        sleep(5.0)
        logger.warning("Continuing with live launch!")

    EsportsBot.run(os.getenv("DISCORD_TOKEN"))


if __name__ == "__main__":
    raise RuntimeError(
        "This module should not be run directly. \
        Instead run `main.py` to ensure logging and environment variables are correctly loaded."
    )
