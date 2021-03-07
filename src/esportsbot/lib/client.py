from discord.ext import commands
from discord import Intents, Embed, Message, Colour, NotFound, HTTPException, Forbidden
from ..reactionMenus.reactionMenu import ReactionMenu
from psycopg2.extras import Json
from ..db_gateway import db_gateway
from typing import Dict, Union
from datetime import datetime
import os

from ..reactionMenus import reactionMenu
from .exceptions import UnrecognisedReactionMenuMessage
from .emotes import Emote


class ReactionMenuDB(dict):
    """A database of ReactionMenus.
    When a message is interacted with through reactions, that message should be cross referenced with this database.
    If a menu exists for that message, the menu's reaction behaviour should be called.
    ReactionMenuDB will also save saveable menu instances to SQL automatically.
    """

    def __init__(self):
        self.initializing = True


    def __contains__(self, menu: Union[ReactionMenu, int]) -> bool:
        """decide whether a menu or menu ID is registered in the database.
        Overrides 'if x in db:'

        :param menu: The menu ID or ReactionMenu instance to check for registration
        :type menu: ReactionMenu or int
        :return: True if menu is registered in the DB, False otherwise
        :rtype: True
        :raise TypeError: if menu is neither int nor ReactionMenu
        """
        if isinstance(menu, int):
            return super().__contains__(menu)
        elif isinstance(menu, ReactionMenu):
            return super().__contains__(menu.msg.id)
        else:
            raise TypeError("ReactionMenuDB can only contain ReactionMenus, given type " + type(menu).__name__)


    def __getitem__(self, k: int) -> ReactionMenu:
        """Get the registered ReactionMenu instance for the given menu ID.
        Overrides getting through 'db[id]'
        No behaviour added currently, only here for type hinting

        :param int k: The ID of the menu to fetch
        :return: The registered menu with the given ID
        :rtype: ReactionMenu
        """
        return super().__getitem__(k)


    def __setitem__(self, menuID: int, menu: ReactionMenu) -> None:
        """Registers the given menu into the database.
        Overrides setting through 'db[id] = menu'

        :param ReactionMenu menu: The ReactionMenu instance to register
        :param int menuID: The ID to register menu under. Must be the same as menu.msg.id
        :raise ValueError: menuID differs from menu.msg.id
        :raise KeyError: If a menu with the given ID is already registered
        """
        if menuID != menu.msg.id:
            raise ValueError("Attempted to register a menu with key " + str(menuID) + ", but the message ID for the given menu is " + str(menu.msg.id))
        
        if menu.msg.id in self:
            raise KeyError("A menu is already registered with the given ID: " + str(menu.msg.id))

        super().__setitem__(menuID, menu)

        if not self.initializing and reactionMenu.isSaveableMenuInstance(menu):
            db_gateway().insert('reaction_menus', params={'message_id': menu.msg.id, 'menu': str(Json(menu.toDict())).lstrip("'").rstrip("'")})


    def __delitem__(self, menu: Union[ReactionMenu, int]) -> None:
        """Unregisters the given menu or menu ID from the database.
        Overrides removing through 'del db[id]'

        :param menu: The ReactionMenu instance or menu ID to unregister
        :type menu: ReactionMenu or int
        :raise KeyError: If menu is not registered in the db
        """
        if isinstance(menu, int):
            if menu not in self:
                raise KeyError("No menu is registered with the given ID: " + str(menu))
            menu = self[menu]

        elif menu.msg.id not in self:
            raise KeyError("The given menu is not registered: " + str(menu.msg.id))

        super().__delitem__(menu.msg.id)

        if reactionMenu.isSaveableMenuInstance(menu):
            db_gateway().delete('reaction_menus', where_params={'message_id': menu.msg.id})


    def add(self, menu: ReactionMenu):
        """Register a ReactionMenu with the database, and save to SQL.

        :param ReactionMenu menu: The menu to register
        :raise KeyError: When a menu with the same id as menu is already registered
        """
        self[menu.msg.id] = menu


    def remove(self, menu: ReactionMenu):
        """Unregister the given menu, preventing menu interaction through reactions.

        :param ReactionMenu menu: The menu to remove
        :raise KeyError: When the given menu is not registered
        """
        del self[menu.msg.id]


    def removeID(self, menuID: int):
        """Unregister menu with the given ID, preventing menu interaction through reactions.

        :param id menuID: The message ID for the menu to remove
        :raise KeyError: When the given menu is not registered
        """
        if menuID not in self:
            raise KeyError("No menu is registered with the given ID: " + str(menuID))
        self.remove(self[menuID])


    def updateDB(self, menu: ReactionMenu):
        """Update the database's record for the given menu, for example when changing the content of a menu.

        :param ReactionMenu menu: The menu whose database record to update
        :raise KeyError: When the given menu is not registered
        """
        if menu.msg.id not in self:
            raise KeyError("The given menu is not registered: " + str(menu.msg.id))
        if reactionMenu.isSaveableMenuInstance(menu):
            db_gateway().update('reaction_menus', set_params={'menu': str(Json(menu.toDict())).lstrip("'").rstrip("'")}, where_params={'message_id': menu.msg.id})


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
        if message is None and "guildID" not in kwargs:
            raise ValueError("Given None message and no guildID")
        if message is None:
            guildID = kwargs["guildID"]
            del kwargs["guildID"]
        else:
            guildID = message.guild.id
        db_logging_call = db_gateway().get('guild_info', params={'guild_id': guildID})
        if db_logging_call and db_logging_call[0]['log_channel_id']:
            if "embed" not in kwargs:
                if message is None:
                    logEmbed = Embed(description="Responsible user unknown. Check the server's audit log.")
                else:
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
