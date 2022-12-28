import os
import toml
import logging
import json
from typing import Dict

logger = logging.getLogger(__name__)


def load_cog_toml(cog_path: str) -> Dict:
    cog_name = os.path.splitext(cog_path)[-1][1:]
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "locale", f"{cog_name}.toml"))
    try:
        return toml.load(path)
    except FileNotFoundError:
        logger.warning(f"Unable to load TOML file for {cog_path}")
        return {}


def load_bot_version():
    file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "version.txt"))
    try:
        with open(file_path, "rt") as file:
            return file.readline()
    except FileNotFoundError:
        return None


def load_timezones():
    file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "timezone.json"))
    try:
        with open(file_path, "r") as file:
            data = json.load(file)
            zones = data.get("timezones")
            return zones
    except FileNotFoundError:
        return {}
