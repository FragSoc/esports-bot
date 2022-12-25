import os
import logging
from typing import List, Dict, Union
from discord.ext.commands import Bot
from discord import Intents, Object

__all__ = ["EsportsBot"]


class __EsportsBot(Bot):

    def __init__(self, command_prefix: str, all_messages_ephemeral: bool, *args, **kwargs):
        """Creates a new instance of the the private EsportsBot class.

        Args:
            command_prefix (str): The character(s) to use as the legacy command prefix.
        """
        super().__init__(command_prefix, *args, **kwargs)
        self.logger = logging.getLogger(__name__)
        self.only_ephemeral = all_messages_ephemeral

    async def setup_hook(self):
        """The setup function that is called prior to the bot connecting to the Discord Gateway.
        """
        # List of extensions to load. Initialised with default extensions.
        enabled_extensions: List[str] = ["AdminTools"]
        # Dictionary of Environment variables -> extension name
        MODULE_ENV_VARS: Dict[str,
                              Union[str,
                                    None]] = {
                                        "VOICEADMIN": "VoiceAdmin",
                                        "EVENTTOOLS": "EventTools",
                                        "AUTOROLES": "AutoRoles"
                                    }

        # For each of the enabled Environment variables, add it's respective extension to the list.
        for var in MODULE_ENV_VARS:
            if MODULE_ENV_VARS.get(var) and os.getenv(f"ENABLE_{var.upper()}", "FALSE").upper() == "TRUE":
                enabled_extensions.append(MODULE_ENV_VARS.get(var))

        # Load the extensions from the generated list of enabled extensions.
        for extension in enabled_extensions:
            await self.load_extension(f"extensions.{extension}")

        # If in a dev environment, sync the commands to the dev guild.
        if os.getenv("DEV_GUILD_ID"):
            DEV_GUILD = Object(id=os.getenv("DEV_GUILD_ID"))
            self.logger.warning(f"Using guild with id {DEV_GUILD.id} as Development guild!")
            self.tree.copy_global_to(guild=DEV_GUILD)
            await self.tree.sync(guild=DEV_GUILD)


EsportsBot = __EsportsBot(
    command_prefix=os.getenv("COMMAND_PREFIX"),
    all_messages_ephemeral=os.getenv("ALL_MESSAGES_EPHEMERAL").upper() == "TRUE",
    intents=Intents.all()
)
