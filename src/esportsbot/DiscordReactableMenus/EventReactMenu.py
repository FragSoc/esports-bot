from discord import Role, TextChannel

from esportsbot.DiscordReactableMenus.ExampleMenus import RoleReactMenu
from esportsbot.DiscordReactableMenus.ReactableMenu import ReactableMenu
from esportsbot.DiscordReactableMenus.reactable_lib import clean_mentioned_role


class EventReactMenu(RoleReactMenu):

    @classmethod
    async def from_dict(cls, bot, data) -> ReactableMenu:
        kwargs = await super(EventReactMenu, cls).load_dict(bot, data)

        shared_role_mentionable = data.get("shared_role")
        shared_role_id = clean_mentioned_role(shared_role_mentionable)
        shared_role = bot.get_guild(data.get("guild_id")).get_role(shared_role_id)

        role_mentionable = list(data.get("options").values())[0].get("descriptor")
        role_id = clean_mentioned_role(role_mentionable)
        event_role = bot.get_guild(data.get("guild_id")).get_role(role_id)

        menu = EventReactMenu(event_role=event_role, shared_role=shared_role, **kwargs)
        if menu.enabled:
            menu.enabled = False
            await menu.enable_menu(bot)

        if menu.message:
            menu.event_category = menu.message.channel.category

        return menu

    def __str__(self):
        return self.title

    def to_dict(self):
        kwargs = super(EventReactMenu, self).to_dict()
        kwargs["shared_role"] = self.shared_role.mention
        return kwargs

    def __init__(self, event_role: Role, shared_role: Role, **kwargs):
        super(EventReactMenu, self).__init__(**kwargs)
        self.event_role = event_role
        self.shared_role = shared_role
        self.event_category = None

    async def finalise_and_send(self, bot, channel: TextChannel):
        await super(EventReactMenu, self).finalise_and_send(bot, channel)
        self.event_category = self.message.channel.category
