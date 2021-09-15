from types import FrameType
from discord.ext import commands
from discord import Intents, Embed, Colour, Member, User
from esportsbot.DiscordReactableMenus.EmojiHandler import MultiEmoji
from esportsbot.db_gateway import DBGatewayActions
from esportsbot.lib.CustomHelpCommand import CustomHelpCommand
from esportsbot.models import GuildInfo
from typing import Dict, MutableMapping, Union, Any
from datetime import datetime
import os
import signal
import asyncio
import toml

# Type alias to be used for user facing strings. Allows for multi-level tables.
StringTable = MutableMapping[str, Union[str, "StringTable"]]


class EsportsBot(commands.Bot):
    """
    A slightly modified version of the basic Bot from discord.commands to include a few extra attributes.
    """
    def __init__(self, command_prefix: str, user_strings_file: str, **options):
        """
        :param str command_prefix: The prefix to use for bot commands when evoking from discord.
        :param str userStringsFile: A path to the `user_strings.toml` configuration file containing *all* user facing strings
        """
        super().__init__(command_prefix, **options)

        self.unknown_command_emoji = MultiEmoji(os.getenv("UNKNOWN_COMMAND_EMOJI", "⁉"))
        self.STRINGS: StringTable = toml.load(user_strings_file)

        signal.signal(signal.SIGINT, self.interrupt_received)  # keyboard interrupt
        signal.signal(signal.SIGTERM, self.interrupt_received)  # graceful exit request

    def interrupt_received(self, signum: signal.Signals, frame: FrameType):
        """Shut down the bot gracefully.
        This method is called automatically upon receipt of sigint/sigterm.

        :param signal.Signals signum: Enum representing the type of interrupt received
        :param FrameType frame: The current stack frame (https://docs.python.org/3/reference/datamodel.html#frame-objects)
        """
        print("[EsportsBot] Interrupt received.")
        asyncio.ensure_future(self.shutdown())

    async def shutdown(self):
        """Shut down the bot gracefully.
        """
        print("[EsportsBot] Shutting down...")
        await self.logout()

    async def admin_log(self,
                        guild_id: int,
                        actions: Dict[str, Any],
                        responsible_user: Union[Member, User] = None,
                        colour=None):
        guild_settings = DBGatewayActions().get(GuildInfo, guild_id=guild_id)
        if not guild_settings or not guild_settings.log_channel_id:
            return
        log_channel = await self.fetch_channel(guild_settings.log_channel_id)

        if not responsible_user:
            responsible_user = self.user

        if not colour:
            colour = Colour.random()

        log_info = [responsible_user.mention]

        if "command" in actions:
            # The action to log came from a message
            message = actions.pop("command")
            log_info.append(message.channel.mention)
            log_info.append(f"[message]({message.jump_url})")
        else:
            log_info.append("Action Performed:")

        log_embed = Embed(description=" | ".join(log_info), colour=colour)
        log_embed.set_author(icon_url=self.user.avatar_url_as(size=64), name="Admin Log")
        log_embed.set_footer(text=datetime.now().strftime("%m/%d/%Y, %H:%M:%S"))

        for key, value in actions.items():
            log_embed.add_field(name=key, value=value, inline=False)

        await log_channel.send(embed=log_embed)


# Singular class instance of EsportsBot
_instance: EsportsBot = None


def instance() -> EsportsBot:
    """Get the singular instance of the discord client.
    EsportsBot is singular to allow for global client instance references outside of cogs, e.g emoji validation in lib
    """
    global _instance
    if _instance is None:
        intents = Intents.default()
        intents.members = True
        _instance = EsportsBot(
            os.getenv("COMMAND_PREFIX",
                      "!"),
            "esportsbot/user_strings.toml",
            intents=intents,
            help_command=None
        )
        _instance.help_command = CustomHelpCommand(help_strings=_instance.STRINGS["help"])
    return _instance
