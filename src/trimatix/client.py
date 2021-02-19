from discord.ext import commands
from discord import Intents
from .reactionMenus.reactionMenu import ReactionMenu
from .reactionMenus import reactionRoleMenu
from psycopg2.extras import Json
from db_gateway import db_gateway
from typing import Dict, Union

from trimatix.reactionMenus import reactionMenu


class ReactionMenuDB(dict):

    def __contains__(self, menu: Union[ReactionMenu, int]) -> bool:
        if isinstance(menu, int):
            return super().__contains__(menu)
        elif isinstance(menu, ReactionMenu):
            return super().__contains__(menu.msg.id)
        else:
            raise TypeError("ReactionMenuDB can only contain ReactionMenus, given type " + type(menu).__name__)


    def __getitem__(self, k: int) -> ReactionMenu:
        return super().__getitem__(k)


    def __setitem__(self, menuID: int, menu: ReactionMenu) -> None:
        if menuID != menu.msg.id:
            raise ValueError("Attempted to register a menu with key " + str(menuID) + ", but the message ID for the given menu is " + str(menu.msg.id))
        
        if menu.msg.id in self:
            raise KeyError("A menu is already registered with the given ID: " + str(menu.msg.id))

        super().__setitem__(menuID, menu)

        if reactionMenu.isSaveableMenuInstance(menu):
            db_gateway().insert('reaction_menus', params={'message_id': menu.msg.id, 'menu': Json(menu.toDict())})


    def __delitem__(self, menu: Union[ReactionMenu, int]) -> None:
        if isinstance(menu, int):
            if menu not in self:
                raise KeyError("No menu is registered with the given ID: " + str(menu))
            menu = self[menu]

        elif menu.msg.id not in self:
            raise KeyError("The given menu is not registered: " + str(menu.msg.id))

        super().__delitem__(menu.msg.id)

        if reactionMenu.isSaveableMenuInstance(menu):
            db_gateway().delete('reaction_menus', params={'message_id': menu.msg.id})


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
            db_gateway().update('reaction_menus', set_params={'menu': Json(menu.toDict())}, where_params={'message_id': menu.msg.id})


class EsportsBot(commands.Bot):
    """A discord.commands.Bot subclass, adding a dictionary of active reaction menus.

    :var reactionMenus: A associating integer menu message IDs to ReactionMenu objects.
    :vartype reactionMenus: Dict[int, ReactionMenu]
    """

    def __init__(self, command_prefix, **options):
        super().__init__(command_prefix, **options)
        self.reactionMenus: ReactionMenuDB = ReactionMenuDB()
        menusData = db_gateway().getall('reaction_menus')
        for msgID, menuDict in menusData:
            if 'type' in menuDict and reactionMenu.isSaveableMenuTypeName(menuDict['type']):
                self.reactionMenus.add(reactionMenu.saveableMenuClassFromName(menuDict['type']).fromDict(self, menuDict))


_instance: EsportsBot = None

def instance() -> EsportsBot:
    """Get the singular instance of the discord client.
    """
    if _instance is None:
        intents = Intents.default()
        intents.members = True
        instance = EsportsBot(command_prefix = '!', intents=intents)
    return instance
