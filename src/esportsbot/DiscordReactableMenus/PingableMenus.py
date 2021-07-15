import datetime
from typing import Dict

from discord import Embed, Role

from esportsbot.DiscordReactableMenus.ExampleMenus import PollReactMenu, RoleReactMenu
from esportsbot.DiscordReactableMenus.ReactableMenu import ReactableMenu

NO_VOTES = "No votes received!"


class PingableVoteMenu(PollReactMenu):
    def __init__(self, pingable_name: str, **kwargs):
        super().__init__(**kwargs)
        self.name = pingable_name

    def __str__(self):
        return self.name

    @classmethod
    async def from_dict(cls, bot, data) -> ReactableMenu:
        try:
            kwargs = await cls.load_dict(bot, data)

            menu = PingableVoteMenu(**kwargs)
            if menu.enabled:
                menu.enabled = False
                await menu.enable_menu(bot)

            return menu
        except AttributeError:
            return data

    @classmethod
    async def load_dict(cls, bot, data) -> Dict:
        kwargs = await super(PingableVoteMenu, cls).load_dict(bot, data)

        pingable_name = data.get("name")
        kwargs["pingable_name"] = pingable_name

        return kwargs

    def to_dict(self):
        kwargs = super(PingableVoteMenu, self).to_dict()
        kwargs["name"] = self.name
        return kwargs

    def generate_result_embed(self, dummy_emoji, vote_threshold):
        if self.total_votes <= 0:
            string = NO_VOTES
        else:
            self.options[dummy_emoji.emoji_id] = {"emoji": dummy_emoji, "descriptor": "Vote Threshold"}
            self.votes[dummy_emoji.emoji_id] = {"emoji": dummy_emoji, "votes": vote_threshold}
            self.total_votes += vote_threshold
            string = self.generate_results_string()
            self.options.pop(dummy_emoji.emoji_id)
            self.votes.pop(dummy_emoji.emoji_id)
            self.total_votes -= vote_threshold

        title = self.title
        description = self.description

        embed = Embed(title=f"{title} Results", description=description)
        embed.add_field(name="Results", value=string, inline=False)

        return embed


class PingableRoleMenu(RoleReactMenu):
    def __init__(self, pingable_role: Role, ping_cooldown: int, **kwargs):
        super(PingableRoleMenu, self).__init__(**kwargs)
        self.role = pingable_role
        self.last_pinged = datetime.datetime.now()
        self.cooldown = ping_cooldown

    @classmethod
    async def from_dict(cls, bot, data) -> ReactableMenu:
        try:
            kwargs = await cls.load_dict(bot, data)

            menu = PingableRoleMenu(**kwargs)
            if menu.enabled:
                menu.enabled = False
                await menu.enable_menu(bot)
            return menu
        except AttributeError:
            return data

    @classmethod
    async def load_dict(cls, bot, data) -> Dict:
        kwargs = await super(PingableRoleMenu, cls).load_dict(bot, data)

        guild = bot.get_guild(data.get("guild_id"))
        pingable_role = guild.get_role(data.get("role_id"))
        await pingable_role.edit(mentionable=True)
        kwargs["pingable_role"] = pingable_role
        kwargs["ping_cooldown"] = int(data.get("cooldown_seconds"))

        return kwargs

    def to_dict(self):
        kwargs = super(PingableRoleMenu, self).to_dict()
        kwargs["role_id"] = self.role.id
        kwargs["cooldown_seconds"] = self.cooldown
        return kwargs
