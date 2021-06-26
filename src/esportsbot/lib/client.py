from types import FrameType
from discord.ext import commands, tasks
from discord import Intents, Embed, Message, Colour, Role
from esportsbot.reactionMenus.reactionMenuDB import ReactionMenuDB
from esportsbot.reactionMenus import reactionMenu
from esportsbot.db_gateway_v1 import DBGatewayActions
from esportsbot.models import Music_channels, Pingable_roles, Guild_info, Reaction_menus
from esportsbot.lib import exceptions
from typing import Dict, MutableMapping, Set, Union
from datetime import datetime, timedelta
import os
import signal
import asyncio
import toml

from esportsbot.lib.exceptions import UnrecognisedReactionMenuMessage
from esportsbot.lib.emotes import Emote

# Type alias to be used for user facing strings. Allows for multi-level tables.
StringTable = MutableMapping[str, Union[str, "StringTable"]]


class EsportsBot(commands.Bot):
    """A discord.commands.Bot subclass, adding a dictionary of active reaction menus.

    .. codeauthor:: Trimatix

    :var reactionMenus: A associating integer menu message IDs to ReactionMenu objects.
    :vartype reactionMenus: ReactionMenuDB
    :var unknownCommandEmoji: The emote which the bot should react to messages with, if the message attempts to call an unknown command
    :vartype unknownCommandEmoji: Emote
    :var STRINGS: A dict-like object containing *all* user facing strings. The first level associates string category names with the second level.
                    The second level is another dict-like object, mapping string names to parameter-formattable user-facing strings.
    :vartype STRINGS: str
    """
    def __init__(self, command_prefix: str, unknownCommandEmoji: Emote, userStringsFile: str, **options):
        """
        :param str command_prefix: The prefix to use for bot commands when evoking from discord.
        :param Emote unknownCommandEmoji: The emote which the bot should react to messages with, if the message attempts to call an unknown command
        :param str userStringsFile: A path to the `user_strings.toml` configuration file containing *all* user facing strings
        """
        super().__init__(command_prefix, **options)
        self.reactionMenus = ReactionMenuDB()
        self.unknownCommandEmoji = unknownCommandEmoji
        self.STRINGS: StringTable = toml.load(userStringsFile)
        self.MUSIC_CHANNELS = {}

        signal.signal(signal.SIGINT, self.interruptReceived)  # keyboard interrupt
        signal.signal(signal.SIGTERM, self.interruptReceived)  # graceful exit request

    def update_music_channels(self):
        self.MUSIC_CHANNELS = {}
        temp_channels = DBGatewayActions().list(Music_channels)
        for item in temp_channels:
            self.MUSIC_CHANNELS[item.guild_id] = item.channel_id
        return self.MUSIC_CHANNELS

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

    async def rolePingCooldown(self, role: Role, cooldownSeconds: int):
        """wait cooldownSeconds seconds, then set role back to pingable.
        role must be registered in the pingable_roles table.

        :param Role role: The role to set back to pingable by anyone
        :param int cooldownSeconds: The number of seconds to wait asynchronously before updating role
        """
        await asyncio.sleep(cooldownSeconds)
        roleData = DBGatewayActions().get(Pingable_roles, role_id=role.id)
        if roleData and roleData.on_cooldown:
            roleData.on_cooldown = False
            DBGatewayActions().update(roleData)
        if role.guild.get_role(role.id) is not None:
            await role.edit(mentionable=True, colour=roleData.colour, reason="role ping cooldown complete")

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

    async def init(self):
        """Load in all of the reaction menus registered in SQL, and also restarts all pingme role cooldown tasks
        which were interrupted by bot shutdown. This method must be called upon bot.on_ready, since these tasks
        cannot be performed synchronously during EsportsBot.__init__.
        """
        if not self.reactionMenus.initializing:
            raise RuntimeError("This bot's ReactionMenuDB has already been initialized.")
        try:
            menusData = DBGatewayActions().list(Reaction_menus)
        except Exception as e:
            print("failed to load menus from SQL", e)
            raise e
        for menuData in menusData:
            msgID, menuDict = menuData.message_id, menuData.menu
            if 'type' in menuDict:
                if reactionMenu.isSaveableMenuTypeName(menuDict['type']):
                    try:
                        self.reactionMenus.add(
                            reactionMenu.saveableMenuClassFromName(menuDict['type']).fromDict(self,
                                                                                              menuDict)
                        )
                    except UnrecognisedReactionMenuMessage:
                        print(f"Unrecognised message for {menuDict['type']}, removing from the database: {menuDict['msg']}")
                        reaction_menu = DBGatewayActions().get(Reaction_menus, message_id=msgID)
                        DBGatewayActions.delete(reaction_menu)
                else:
                    print("Non saveable menu in database:", msgID, menuDict["type"])
            else:
                print(f"no type for menu {msgID}")

        self.reactionMenus.initializing = False
        if "UNKNOWN_COMMAND_EMOJI" in os.environ:
            self.unknownCommandEmoji = Emote.fromStr(os.environ.get("UNKNOWN_COMMAND_EMOJI"))

        now = datetime.now()
        roleUpdateTasks = set()
        for guildData in DBGatewayActions().list(Guild_info):
            guild = self.get_guild(guildData.guild_id)
            if guild is None:
                print(f"[Esportsbot.init] Unknown guild id in guild_info table: #{guildData.guild_id}")
            else:
                guildPingCooldown = timedelta(seconds=guildData.role_ping_cooldown_seconds)
                for roleData in DBGatewayActions().list(Pingable_roles, guild_id=guildData.guild_id):
                    role = guild.get_role(roleData.role_id)
                    if role is None:
                        print(
                            f"[Esportsbot.init] Unknown pingable role id in pingable_roles table. Removing from the table: role #{roleData.role_id} in guild #{guildData.guild_id}"
                        )
                        pingable_role = DBGatewayActions().get(Pingable_roles, role_id=roleData.role_id)
                        DBGatewayActions().delete(pingable_role)
                    else:
                        remainingCooldown = max(
                            0,
                            int((datetime.fromtimestamp(roleData.last_ping) + guildPingCooldown - now).total_seconds())
                        )
                        roleUpdateTasks.add(asyncio.create_task(self.rolePingCooldown(role, remainingCooldown)))

        if not self.monthlyPingablesReport.is_running():
            self.monthlyPingablesReport.start()

        print('[EsportsBot.init] Bot is now active')
        if roleUpdateTasks:
            await asyncio.wait(roleUpdateTasks)
            for task in roleUpdateTasks:
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

    def handleRoleMentions(self, message: Message) -> Set[asyncio.Task]:
        """Handle !pingme behaviour for the given message.
        Places mentioned roles on cooldown if they are not already on cooldown.
        Returns a set of ping cooldown tasks that should be awaited and error handled.

        :param Message message: The message containing the role mentions to handle
        :return: A potentially empty set of already scheduled tasks handling role ping cooldown
        :rtype: Set[asyncio.Task]
        """
        guildInfo = DBGatewayActions().get(Guild_info, guild_id=message.guild.id)
        roleUpdateTasks = set()
        if guildInfo:
            for role in message.role_mentions:
                roleData = DBGatewayActions().get(Pingable_roles, role_id=role.id)
                if roleData and not roleData.on_cooldown:
                    roleUpdateTasks.add(
                        asyncio.create_task(
                            role.edit(
                                mentionable=False,
                                colour=Colour.darker_grey(),
                                reason="placing pingable role on ping cooldown"
                            )
                        )
                    )
                    roleData.on_cooldown = True
                    roleData.last_ping = datetime.now().timestamp()
                    roleData.ping_count = roleData.ping_count + 1
                    roleData.monthly_ping_count = roleData.monthly_ping_count + 1
                    DBGatewayActions().update(roleData)

                    roleUpdateTasks.add(asyncio.create_task(self.rolePingCooldown(role, guildInfo.role_ping_cooldown_seconds)))
                    roleUpdateTasks.add(
                        asyncio.create_task(
                            self.adminLog(
                                message,
                                {"!pingme Role Pinged": f"Role: {role.mention}\nUser: {message.author.mention}"}
                            )
                        )
                    )
        return roleUpdateTasks


# Singular class instance of EsportsBot
_instance: EsportsBot = None


def instance() -> EsportsBot:
    """Get the singular instance of the discord client.
    EsportsBot is singular to allow for global client instance references outside of coges, e.g emoji validation in lib
    """
    global _instance
    if _instance is None:
        intents = Intents.default()
        intents.members = True
        _instance = EsportsBot('!', Emote.fromStr("⁉"), "esportsbot/user_strings.toml", intents=intents)
    return _instance
