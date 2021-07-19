from types import FrameType
from discord.ext import commands, tasks
from discord import Intents, Embed, Message, Colour
from esportsbot.db_gateway import DBGatewayActions
from esportsbot.models import Pingable_roles, Guild_info
from esportsbot.lib import exceptions
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

        self.unknown_command_emoji = os.getenv("UNKNOWN_COMMAND_EMOJI", "⁉")
        self.STRINGS: StringTable = toml.load(user_strings_file)

        signal.signal(signal.SIGINT, self.interruptReceived)  # keyboard interrupt
        signal.signal(signal.SIGTERM, self.interruptReceived)  # graceful exit request

    def interruptReceived(self, signum: signal.Signals, frame: FrameType):
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

    @tasks.loop(hours=24)
    async def monthlyPingablesReport(self):
        """Send a report to all joined servers, summarising the number of times each !pingme
        role was pinged this month.
        Also resets the monthly ping count for all !pingme roles.
        """
        if datetime.now().day == 1:
            loggingTasks = set()
            baseEmbed = Embed(
                title="Monthly !pingme Report",
                description="The number of times each !pingme role was pinged last month:"
            )
            baseEmbed.colour = Colour.random()
            baseEmbed.set_thumbnail(url=self.user.avatar_url_as(size=128))
            baseEmbed.set_footer(text=datetime.now().strftime("%m/%d/%Y"))
            for guildData in DBGatewayActions().list(Guild_info):
                pingableRoles = DBGatewayActions().list(Pingable_roles, guild_id=guildData.guild_id)
                if pingableRoles:
                    guild = self.get_guild(guildData.guild_id)
                    if guild is None:
                        print(
                            f"[Esportsbot.monthlyPingablesReport] Unknown guild id in guild_info table: #{guildData.guild_id}"
                        )
                    elif guildData.log_channel_id is not None:
                        reportEmbed = baseEmbed.copy()
                        rolesAdded = False
                        for roleData in pingableRoles:
                            role = guild.get_role(roleData.role_id)
                            if role is None:
                                print(
                                    f"[Esportsbot.monthlyPingablesReport] Unknown pingable role id in pingable_roles table. Removing from the table: role #{roleData.role_id} in guild #{guildData.guild_id}"
                                )
                                DBGatewayActions().delete(roleData)
                            else:
                                reportEmbed.add_field(
                                    name=role.name,
                                    value=f"{role.mention}\n{roleData.monthly_ping_count} pings"
                                )
                                roleData.monthly_ping_count = 0
                                DBGatewayActions().update(roleData)
                                rolesAdded = True
                        if rolesAdded:
                            loggingTasks.add(
                                asyncio.create_task(guild.get_channel(guildData.log_channel_id).send(embed=reportEmbed))
                            )

            if loggingTasks:
                await asyncio.wait(loggingTasks)
                for task in loggingTasks:
                    if e := task.exception():
                        exceptions.print_exception_trace(e)

    async def adminLog(self, message: Message, actions: Dict[str, str], *args, guildID=None, **kwargs):
        """Log an event or series of events to the server's admin logging channel.
        To log an administration action which was not due to a user command, give message as None, and specify the guild in
        which to send the log with the guildID kwarg.

        :param Message message: The message that triggered this log. Probably a command.
        :param actions: A dictionary associating action types with action details. No key or value can be empty.
        :type actions: Dict[str, str]
        :param int guildID: The ID of the guild in which to send the log, if message is given as None. Ignored otherwise.
        """
        if message is None:
            if guildID is None:
                raise ValueError("Must give at least one of message or guildID")
        else:
            guildID = message.guild.id
        db_logging_call = DBGatewayActions().get(Guild_info, guild_id=guildID)
        if db_logging_call and db_logging_call.log_channel_id:
            if "embed" not in kwargs:
                if message is None:
                    logEmbed = Embed(description="Responsible user unknown. Check the server's audit log.")
                else:
                    logEmbed = Embed(
                        description=" | ".
                        join((message.author.mention,
                              "#" + message.channel.name,
                              "[message](" + message.jump_url + ")"))
                    )
                logEmbed.set_author(icon_url=self.user.avatar_url_as(size=64), name="Admin Log")
                logEmbed.set_footer(text=datetime.now().strftime("%m/%d/%Y, %H:%M:%S"))
                logEmbed.colour = Colour.random()
                for aTitle, aDesc in actions.items():
                    logEmbed.add_field(name=str(aTitle), value=str(aDesc), inline=False)
                kwargs["embed"] = logEmbed
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
        _instance = EsportsBot(os.getenv("COMMAND_PREFIX", "!"), "esportsbot/user_strings.toml", intents=intents)
    return _instance
