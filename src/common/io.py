import json
import logging
import os
from typing import Dict

import toml

logger = logging.getLogger(__name__)


def load_cog_toml(cog_path: str) -> Dict:
    """Load a cogs TOML file using a modules __name__ attribute as the key.

    Args:
        cog_path (str): The relative path of a module.

    Returns:
        Dict: A dictionary containng the key/value pairs defined in the cog's TOML file.
    """
    cog_name = os.path.splitext(cog_path)[-1][1:]
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "locale", f"{cog_name}.toml"))
    try:
        return toml.load(path)
    except FileNotFoundError:
        logger.warning(f"Unable to load TOML file for {cog_path}")
        return {}


def load_bot_version():
    """Load the bot's version number from the defined version.txt file.

    Returns:
        str: A string containing the bot's current version.
    """
    file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "version.txt"))
    try:
        with open(file_path, "rt") as file:
            return file.readline()
    except FileNotFoundError:
        return None


def load_timezones():
    """Load a JSON file containing human readble and short timezone strings.

    Returns:
        dict: A dictionary of short string to alterntive formats of timezones.
    """
    file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "timezone.json"))
    try:
        with open(file_path, "r") as file:
            data = json.load(file)
            zones = data.get("timezones")
            return zones
    except FileNotFoundError:
        return {}
