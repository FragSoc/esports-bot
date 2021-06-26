"""
The reactionMenus package was partially copied over from the BASED template project: https://github.com/Trimatix/BASED
It is modified and not actively synced with BASED, so will very likely be out of date.

.. codeauthor:: Trimatix
"""

from typing import Union
from esportsbot.reactionMenus.reactionMenu import ReactionMenu, isSaveableMenuInstance
from psycopg2.extras import Json
from esportsbot.db_gateway_v1 import DBGatewayActions
from esportsbot.models import Reaction_menus


class ReactionMenuDB(dict):
    """A database of ReactionMenus.
    When a message is interacted with through reactions, that message should be cross referenced with this database.
    If a menu exists for that message, the menu's reaction behaviour should be called.
    ReactionMenuDB will also save saveable menu instances to SQL automatically.

    To help with loading in existing menu instances from file after a restart, the initializing flag has been added.
    Messages cannot be loaded synchronously, and so the database cannot be loaded completely from the EsportsBot constructor.
    Instead, messages are fetched asynchronously during the EsportsBot.init coroutine, which also sets the initializing
    flag to false once it's done.

    :var initializing: Whether or not the DB has been initialized yet
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
            raise ValueError(
                f"Attempted to register a menu with key {menuID}, but the message ID for the given menu is {menu.msg.id}"
            )

        if menu.msg.id in self:
            raise KeyError(f"A menu is already registered with the given ID: {menu.msg.id}")

        super().__setitem__(menuID, menu)

        if not self.initializing and isSaveableMenuInstance(menu):
            DBGatewayActions().create(
                Reaction_menus(message_id=menu.msg.id,
                               menu=str(Json(menu.toDict())).lstrip("'").rstrip("'"))
            )

    def __delitem__(self, menu: Union[ReactionMenu, int]) -> None:
        """Unregisters the given menu or menu ID from the database.
        Overrides removing through 'del db[id]'

        :param menu: The ReactionMenu instance or menu ID to unregister
        :type menu: ReactionMenu or int
        :raise KeyError: If menu is not registered in the db
        """
        if isinstance(menu, int):
            if menu not in self:
                raise KeyError(f"No menu is registered with the given ID: {menu}")
            menu = self[menu]

        elif menu.msg.id not in self:
            raise KeyError(f"The given menu is not registered: {menu.msg.id}")

        super().__delitem__(menu.msg.id)

        if isSaveableMenuInstance(menu):
            reaction_menu = DBGatewayActions().get(Reaction_menus, message_id=menu.msg.id)
            DBGatewayActions.delete(reaction_menu)

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
            raise KeyError(f"No menu is registered with the given ID: {menuID}")
        self.remove(self[menuID])

    def updateDB(self, menu: ReactionMenu):
        """Update the database's record for the given menu, for example when changing the content of a menu.

        :param ReactionMenu menu: The menu whose database record to update
        :raise KeyError: When the given menu is not registered
        """
        if menu.msg.id not in self:
            raise KeyError("The given menu is not registered: " + str(menu.msg.id))
        if isSaveableMenuInstance(menu):
            reaction_menu = DBGatewayActions().get(Reaction_menus, message_id=menu.msg.id)
            reaction_menu.menu = str(Json(menu.toDict())).lstrip("'").rstrip("'")
            DBGatewayActions().update(reaction_menu)
