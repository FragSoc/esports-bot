from typing import Dict

from discord import Role, TextChannel

from esportsbot.DiscordReactableMenus.ExampleMenus import RoleReactMenu
from esportsbot.DiscordReactableMenus.ReactableMenu import ReactableMenu
from esportsbot.DiscordReactableMenus.reactable_lib import clean_mentioned_role


class EventReactMenu(RoleReactMenu):
    """
    A reaction menu used in the EventCategoriesCog. Is a modified version of a role reaction menu that stores a few more
    attributes.
    """
    @classmethod
    async def from_dict(cls, bot, data) -> ReactableMenu:
        """
        Create an EventReactMenu from a dictionary representation of one.
        :param bot: The instance of the bot.
        :param data: The data of a saved EventReactMenu.
        :return: An EventReactMenu from the given data.
        """
        try:
            kwargs = await cls.load_dict(bot, data)

            menu = EventReactMenu(**kwargs)
            if menu.enabled:
                menu.enabled = False
                await menu.enable_menu(bot)

            return menu
        except AttributeError:
            # Happens when one of the values could not be loaded from the dictionary
            return data

    @classmethod
    async def load_dict(cls, bot, data) -> Dict:
        """
        Formats the incoming data to ensure it has the correct keys in kwargs.
        :param bot: The instance of the bot.
        :param data: The data of a saved EventReactMenu.
        :return: A formatted dictionary that can be passed to the constructor of an EventReactMenu.
        """
        kwargs = await super(EventReactMenu, cls).load_dict(bot, data)

        shared_role_mentionable = data.get("shared_role")
        shared_role_id = clean_mentioned_role(shared_role_mentionable)
        shared_role = bot.get_guild(data.get("guild_id")).get_role(shared_role_id)
        kwargs["shared_role"] = shared_role

        role_mentionable = list(data.get("options").values())[0].get("descriptor")
        role_id = clean_mentioned_role(role_mentionable)
        event_role = bot.get_guild(data.get("guild_id")).get_role(role_id)
        kwargs["event_role"] = event_role

        if kwargs["message"]:
            kwargs["event_category"] = kwargs["message"].channel.category

        return kwargs

    def __str__(self):
        return self.title

    def to_dict(self):
        """
        Get the dictionary representation of an EventReactMenu.
        :return: A dictionary of the saveable attributes of an EventReactMenu.
        """
        kwargs = super(EventReactMenu, self).to_dict()
        kwargs["shared_role"] = self.shared_role.mention
        return kwargs

    def __init__(self, event_role: Role, shared_role: Role, **kwargs):
        super(EventReactMenu, self).__init__(**kwargs)
        self.event_role = event_role
        self.shared_role = shared_role
        self.event_category = kwargs.get("event_category", None)

    async def finalise_and_send(self, bot, channel: TextChannel):
        """
        Create the actual menu and send it to the given channel.
        :param bot: The instance of the bot.
        :param channel: The channel in which to send the menu.
        """
        await super(EventReactMenu, self).finalise_and_send(bot, channel)
        self.event_category = self.message.channel.category
