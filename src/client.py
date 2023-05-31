import logging
import os

from discord import Intents, Object
from discord.ext.commands import Bot

import glob

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
        self.logging_prefix = os.getenv("LOGGING_PREFIX")

    def find_extensions(self):
        defaults = []
        dynamic = []

        def get_files(path):
            files = []
            for file_path in glob.glob(path):
                file = os.path.basename(file_path).split(".")[0]
                if file != "__init__":
                    files.append(file)
            return files

        defaults = get_files(os.path.join(os.path.dirname(__file__), "extensions", "default", "*.py"))
        dynamic = get_files(os.path.join(os.path.dirname(__file__), "extensions", "dynamic", "*.py"))

        return defaults, dynamic

    async def setup_hook(self):
        """The setup function that is called prior to the bot connecting to the Discord Gateway.
        """
        if not self.only_ephemeral:
            self.only_ephemeral = os.getenv("ALL_MESSAGES_EPHEMERAL", "FALSE").upper() == "TRUE"

        default_extensions, dynamic_extensions = self.find_extensions()
        enabled_extensions = []

        # For each of the enabled Environment variables, add it's respective extension to the list.
        for extension in dynamic_extensions:
            if os.getenv(f"ENABLE_{extension.upper()}", "FALSE").upper() == "TRUE":
                enabled_extensions.append(extension)

        # Load the extensions from the generated list of enabled extensions.
        for extension in default_extensions:
            await self.load_extension(f"extensions.default.{extension}")

        for extension in enabled_extensions:
            await self.load_extension(f"extensions.dynamic.{extension}")

        # If in a dev environment, sync the commands to the dev guild.
        if os.getenv("DEV_GUILD_ID"):
            DEV_GUILD = Object(id=os.getenv("DEV_GUILD_ID"))
            self.logger.warning(f"Using guild with id {DEV_GUILD.id} as Development guild!")
            self.tree.copy_global_to(guild=DEV_GUILD)
        else:
            DEV_GUILD = None

        await self.tree.sync(guild=DEV_GUILD)


EsportsBot = __EsportsBot(command_prefix=os.getenv("COMMAND_PREFIX"), all_messages_ephemeral=False, intents=Intents.all())
