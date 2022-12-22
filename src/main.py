import coloredlogs
import logging
import os
import sys
from bot import start_bot

if __name__ == "__main__":
    coloredlogs.install(level=logging.INFO)
    logger = logging.getLogger(__name__)
    if os.getenv("DISCORD_TOKEN") is None:
        logger.warning("Missing Discord Token environment variable, attempting manual load...")
        from dotenv import load_dotenv
        env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "secrets.env"))
        if not load_dotenv(dotenv_path=env_path):
            raise RuntimeError(f"Unable to load .env file: {env_path}")
    if sys.platform not in ('win32', 'cygwin', 'cli'):
        logger.info("Deteced UNIX platform, using uvloop for asyncio operations!")
        import uvloop
        uvloop.install()
    start_bot()
