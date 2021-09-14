from types import FrameType
from discord.ext import commands
from discord import Intents, Embed, Message, Colour
from esportsbot.DiscordReactableMenus.EmojiHandler import MultiEmoji
from esportsbot.db_gateway import DBGatewayActions
from esportsbot.lib.CustomHelpCommand import CustomHelpCommand
from esportsbot.models import GuildInfo
from typing import Dict, MutableMapping, Union
from datetime import datetime
import os
import signal
import asyncio
import toml

# Type alias to be used for user facing strings. Allows for multi-level tables.
StringTable = MutableMapping[str, Union[str, "StringTable"]]


class EsportsBot(commands.Bot):
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

    async def admin_log(self, message: Message, actions: Dict[str, str], *args, guild_id=None, **kwargs):
        """Log an event or series of events to the server's admin logging channel.
        To log an administration action which was not due to a user command, give message as None, and specify the guild in
        which to send the log with the guildID kwarg.

        :param Message message: The message that triggered this log. Probably a command.
        :param actions: A dictionary associating action types with action details. No key or value can be empty.
        :type actions: Dict[str, str]
        :param int guild_id: The ID of the guild in which to send the log, if message is given as None. Ignored otherwise.
        """
        if message is None:
            if guild_id is None:
                raise ValueError("Must give at least one of message or guildID")
        else:
            guild_id = message.guild.id
        db_logging_call = DBGatewayActions().get(GuildInfo, guild_id=guild_id)
        if db_logging_call and db_logging_call.log_channel_id:
            if "embed" not in kwargs:
                if message is None:
                    log_embed = Embed(description="Responsible user unknown. Check the server's audit log.")
                else:
                    log_embed = Embed(
                        description=" | ".
                        join((message.author.mention,
                              "#" + message.channel.name,
                              "[message](" + message.jump_url + ")"))
                    )
                log_embed.set_author(icon_url=self.user.avatar_url_as(size=64), name="Admin Log")
                log_embed.set_footer(text=datetime.now().strftime("%m/%d/%Y, %H:%M:%S"))
                log_embed.colour = Colour.random()
                for aTitle, aDesc in actions.items():
                    log_embed.add_field(name=str(aTitle), value=str(aDesc), inline=False)
                kwargs["embed"] = log_embed
            await self.get_channel(db_logging_call.log_channel_id).send(*args, **kwargs)


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
