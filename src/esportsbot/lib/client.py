from discord.ext import commands
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
    

    def init(self):
        """Load in all of the reaction menus registered in SQL.
        This must be called upon bot.on_ready
        """
        if not self.reactionMenus.initializing:
            raise RuntimeError("This bot's ReactionMenuDB has already been initialized.")
        try:
            menusData = db_gateway().getall('reaction_menus')
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
                        db_gateway().delete('reaction_menus', where_params={'message_id': msgID})
                else:
                    print("Non saveable menu in database:",msgID,menuDict["type"])
            else:
                print("no type for menu " + str(msgID))

        self.reactionMenus.initializing = False
        if "UNKNOWN_COMMAND_EMOJI" in os.environ:
            self.unknownCommandEmoji = Emote.fromStr(os.environ.get("UNKNOWN_COMMAND_EMOJI"))

    
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
