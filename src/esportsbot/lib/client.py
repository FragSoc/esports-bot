from discord.ext import commands, tasks
from discord import Intents, Embed, Message, Colour
from ..reactionMenus.reactionMenuDB import ReactionMenuDB
from ..reactionMenus import reactionMenu
from ..db_gateway import db_gateway
from typing import Dict
from datetime import datetime
import os
import signal
import asyncio

from .exceptions import UnrecognisedReactionMenuMessage
from .emotes import Emote


class EsportsBot(commands.Bot):
    """A discord.commands.Bot subclass, adding a dictionary of active reaction menus.

    :var reactionMenus: A associating integer menu message IDs to ReactionMenu objects.
    :vartype reactionMenus: ReactionMenuDB
    """

    def __init__(self, command_prefix: str, unknownCommandEmoji: Emote, **options):
        """
        :param str command_prefix: The prefix to use for bot commands when evoking from discord.
        """
        super().__init__(command_prefix, **options)
        self.reactionMenus = ReactionMenuDB()
        self.unknownCommandEmoji = unknownCommandEmoji

        signal.signal(signal.SIGINT, self.interruptReceived) # keyboard interrupt
        signal.signal(signal.SIGTERM, self.interruptReceived) # graceful exit request


    def interruptReceived(self, signum, frame):
        """Shut down the bot gracefully.
        This method is called automatically upon receipt of sigint/sigterm.
        """
        print("[EsportsBot] Interrupt received.")
        asyncio.ensure_future(self.shutdown())


    async def shutdown(self):
        """Shut down the bot gracefully.
        """
        print("[EsportsBot] Shutting down...")
        await self.logout()


    async def rolePingCooldown(self, role: discord.Role, cooldownSeconds: int):
        """wait cooldownSeconds seconds, then set role back to pingable.
        role must be registered in the pingable_roles table.
        """
        await asyncio.sleep(cooldownSeconds)
        db = db_gateway()
        roleData = db.get("pingable_roles", {"role_id": role.id})
        if roleData and roleData["on_cooldown"]:
            db.update('pingable_roles', set_params={'on_cooldown': False}, where_params={'role_id': role.id})
        if role.guild.get_role(role.id) is not None:
            await role.edit(mentionable=True, colour=roleData["colour"], reason="role ping cooldown complete")
    

    def init(self):
        """Load in all of the reaction menus registered in SQL.
        This must be called upon bot.on_ready
        """
        db = db_gateway()
        if not self.reactionMenus.initializing:
            raise RuntimeError("This bot's ReactionMenuDB has already been initialized.")
        try:
            menusData = db.getall('reaction_menus')
        except Exception as e:
            print("failed to load menus from SQL",e)
            raise e
        for menuData in menusData:
            msgID, menuDict = menuData['message_id'], menuData['menu']
            if 'type' in menuDict:
                if reactionMenu.isSaveableMenuTypeName(menuDict['type']):
                    try:
                        self.reactionMenus.add(reactionMenu.saveableMenuClassFromName(menuDict['type']).fromDict(self, menuDict))
                    except UnrecognisedReactionMenuMessage:
                        print("Unrecognised message for " + menuDict['type'] + ", removing from the database: " + str(menuDict["msg"]))
                        db.delete('reaction_menus', where_params={'message_id': msgID})
                else:
                    print("Non saveable menu in database:",msgID,menuDict["type"])
            else:
                print("no type for menu " + str(msgID))

        self.reactionMenus.initializing = False
        if "UNKNOWN_COMMAND_EMOJI" in os.environ:
            self.unknownCommandEmoji = Emote.fromStr(os.environ.get("UNKNOWN_COMMAND_EMOJI"))

        now = datetime.now()
        roleUpdateTasks = set()
        for guildData in db.getall("guild_info"):
            guild = self.get_guild(guildData["guild_id"])
            if guild is None:
                print("[Esportsbot.init] Unknown guild id in guild_info table. Removing from the table: #" + str(guildData["guild_id"]))
                db.delete("guild_info", {"guild_id": guildData["guild_id"]})
            else:
                guildPingCooldown = timedelta(seconds=guildData["role_ping_cooldown_seconds"])
                for roleIDData in db.get("guild_pingables", {"guild_id": guildData["guild_id"]}):
                    role = self.get_role(roleIDData["role_id"])
                    if role is None:
                        print("[Esportsbot.init] Unknown pingable role id in guild_pingables table. Removing from the table: role #" \
                                + str(roleIDData["role_id"]) + " in guild #" + str(guildData["guild_id"]))
                        db.delete("guild_pingables", {"guild_id": guildData["guild_id"], "role_id": roleIDData["role_id"]})
                        if db.get("pingable_roles", {"role_id": roleIDData["role_id"]}):
                            db.delete("pingable_roles", {"role_id": roleIDData["role_id"]})
                    else:
                        roleData = db.get("pingable_roles", {"role_id": role.id})
                        if not roleData:
                            print("[Esportsbot.init] Role registered in guild_pingables table, but not in pingable_roles table." \
                                    + " Removing from the table: role #" + str(roleIDData["role_id"]) \
                                    + " in guild #" + str(guildData["guild_id"]))
                            db.delete("guild_pingables", {"guild_id": guildData["guild_id"], "role_id": roleIDData["role_id"]})
                        else:
                            remainingCooldown = max(0, int((datetime.fromtimestamp(roleData["last_ping"]) + guildPingCooldown - now).total_seconds()))
                            roleUpdateTasks.add(asyncio.create_task(rolePingCooldown(role, remainingCooldown)))

        if roleUpdateTasks:
            await asyncio.wait(roleUpdateTasks)
            for task in roleUpdateTasks:
                if e := task.exception():
                    traceback.print_exception(type(e), e, e.__traceback__)

    
    @tasks.loop(hours=24)
    async def monthlyPingablesReport(self):
        """Send a report to all joined servers, summarising the number of times each !pingme
        role was pinged this month.
        Also resets the monthly ping count for all !pingme roles.
        """
        if datetime.now().day == 1:
            loggingTasks = set()
            baseEmbed = Embed(title="Monthly !pingme Report",
                                description="The number of times each !pingme role was pinged last month:")
            baseEmbed.colour = Colour.random()
            baseEmbed.set_thumbnail(url=self.user.avatar_url_as(size=128))
            baseEmbed.set_footer(text=datetime.now().strftime("%m/%d/%Y))
            for guildData in db.getall("guild_info"):
                db = db_gateway()
                pingableRoles = db.get("guild_pingables", {guildData["guild_id"]})
                if pingableRoles:
                    guild = self.get_guild(guildData["guild_id"])
                    if guild is None:
                        print("[Esportsbot.monthlyPingablesReport] Unknown guild id in guild_info table. Removing from the table: #" + str(guildData["guild_id"]))
                        db.delete("guild_info", {"guild_id": guildData["guild_id"]})
                    elif guildData["log_channel_id"] is not None:
                        reportEmbed = baseEmbed.copy()
                        rolesAdded = False
                        for roleIDData in pingableRoles:
                            roleData = db.get("pingable_roles", {"role_id": roleIDData["role_id"]})
                            if roleData:
                                print("[Esportsbot.monthlyPingablesReport] Role registered in guild_pingables table, but not in pingable_roles table." \
                                        + " Removing from the table: role #" + str(roleIDData["role_id"]) \
                                        + " in guild #" + str(guildData["guild_id"]))
                                db.delete("guild_pingables", {"guild_id": guildData["guild_id"], "role_id": roleIDData["role_id"]})
                            else:
                                role = guild.get_role(roleData["role_id"])
                                if role is None:
                                    print("[Esportsbot.monthlyPingablesReport] Unknown pingable role id in guild_pingables table. Removing from the table: role #" \
                                            + str(roleIDData["role_id"]) + " in guild #" + str(guildData["guild_id"]))
                                    db.delete("guild_pingables", {"guild_id": guildData["guild_id"], "role_id": roleIDData["role_id"]})
                                    if db.get("pingable_roles", {"role_id": roleIDData["role_id"]}):
                                        db.delete("pingable_roles", {"role_id": roleIDData["role_id"]})
                                else:
                                    reportEmbed.add_field(name=role.name, value=role.mention + "\n" + str(roleData["monthly_ping_count"]) + " pings")
                                    db.update("pingable_roles", {"monthly_ping_count": 0}, {"role_id": role.id})
                                    rolesAdded = True
                        if rolesAdded:
                            loggingTasks.add(asyncio.create_task(guild.get_channel(guildData['log_channel_id']).send(embed=reportEmbed)))

            if loggingTasks:
                await asyncio.wait(loggingTasks)
                for task in loggingTasks:
                    if e := task.exception():
                        traceback.print_exception(type(e), e, e.__traceback__)
                        


    
    async def adminLog(self, message: Message, actions: Dict[str, str], *args, **kwargs):
        """Log an event or series of events to the server's admin logging channel.
        
        :param Message message: The message that triggered this log. Probably a command.
        :param actions: A dictionary associating action types with action details. No key or value can be empty.
        :type actions: Dict[str, str]
        """
        db_logging_call = db_gateway().get('guild_info', params={'guild_id': message.guild.id})
        if db_logging_call and db_logging_call[0]['log_channel_id']:
            if "embed" not in kwargs:
                logEmbed = Embed(description=" | ".join((message.author.mention, "#" + message.channel.name, "[message](" + message.jump_url + ")")))
                logEmbed.set_author(icon_url=self.user.avatar_url_as(size=64), name="Admin Log")
                logEmbed.set_footer(text=datetime.now().strftime("%m/%d/%Y, %H:%M:%S"))
                logEmbed.colour = Colour.random()
                for aTitle, aDesc in actions.items():
                    logEmbed.add_field(name=str(aTitle), value=str(aDesc), inline=False)
                kwargs["embed"] = logEmbed
            await self.get_channel(db_logging_call[0]['log_channel_id']).send(*args, **kwargs)


_instance: EsportsBot = None

def instance() -> EsportsBot:
    """Get the singular instance of the discord client.
    """
    global _instance
    if _instance is None:
        intents = Intents.default()
        intents.members = True
        _instance = EsportsBot('!', Emote.fromStr("⁉"), intents=intents)
    return _instance
