import datetime
from typing import Dict

from discord import Embed, Reaction, Role

from esportsbot.DiscordReactableMenus.ExampleMenus import PollReactMenu, RoleReactMenu
from esportsbot.DiscordReactableMenus.ReactableMenu import ReactableMenu

NO_VOTES = "No votes received!"


class PingableVoteMenu(PollReactMenu):
    """
    A reaction menu used in the VotingCog. Is a modified Poll ReactionMenu that has a timer.
    """
    def __init__(self, pingable_name: str, **kwargs):
        super().__init__(**kwargs)
        self.name = pingable_name

    def __str__(self):
        return self.name

    @classmethod
    async def from_dict(cls, bot, data) -> ReactableMenu:
        """
        Create a PingableVoteMenu from a dictionary representation of one.
        :param bot: The instance of the bot.
        :param data: The data of a saved PingableVoteMenu
        :return: A PingableVoteMenu from the given data.
        """
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
        """
        Formats the incoming data to ensure it has the correct keys in kwargs.
        :param bot: The instance of the bot.
        :param data: The data of a saved EventReactMenu.
        :return: A formatted dictionary that can be passed to the constructor of a PingableVoteMenu
        """
        kwargs = await super(PingableVoteMenu, cls).load_dict(bot, data)

        pingable_name = data.get("name")
        kwargs["pingable_name"] = pingable_name

        return kwargs

    def to_dict(self):
        """
        Get the dictionary representation of a PingableVoteMenu
        :return: A dictionary of the saveable attributes of a PingableVoteMenu.
        """
        kwargs = super(PingableVoteMenu, self).to_dict()
        kwargs["name"] = self.name
        return kwargs

    async def generate_result_embed(self, dummy_emoji, vote_threshold):
        """
        Get the embed for the results of the polls.
        :param dummy_emoji: The dummy emoji to be used as the vote threshold option.
        :param vote_threshold: The number of votes required for a PingableVoteMenu to be successful.
        :return: A discord Embed object.
        """
        results = await self.get_results()
        if self.total_votes <= 0:
            string = NO_VOTES
        else:
            self.options[dummy_emoji.emoji_id] = {"emoji": dummy_emoji, "descriptor": "Vote Threshold"}
            dummy_react = Reaction(
                emoji=dummy_emoji.discord_emoji,
                message=self.message,
                data={
                    "count": vote_threshold,
                    "me": True
                }
            )
            if vote_threshold > results.get("winner_count"):
                results["winner_count"] = vote_threshold
            results["reactions"][vote_threshold].append(dummy_react)
            self.total_votes += vote_threshold
            string = self.generate_results_string(results)
            self.options.pop(dummy_emoji.emoji_id)
            self.total_votes -= vote_threshold

        title = self.title
        description = self.description

        embed = Embed(title=f"{title} Results", description=description)
        embed.add_field(name="Results", value=string, inline=False)

        return embed


class PingableRoleMenu(RoleReactMenu):
    """
    A reaction menu used in the PingableRoles. Is a modified RoleReactionMenu with a few extra attributes for storing cooldown
    and when it was last pinged.
    """
    def __init__(self, pingable_role: Role, ping_cooldown: int, **kwargs):
        super(PingableRoleMenu, self).__init__(**kwargs)
        self.role = pingable_role
        self.last_pinged = datetime.datetime.now()
        self.cooldown = ping_cooldown

    @classmethod
    async def from_dict(cls, bot, data) -> ReactableMenu:
        """
        Create a PingableRoleMenu from a dictionary representation of one.
        :param bot: The instance of the bot.
        :param data: The data of a saved EventReactMenu.
        :return: A PingableRoleMenu from the given data.
        """
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
        """
        Formats the incoming data to ensure it has the correct keys in kwargs.
        :param bot: The instance of the bot.
        :param data: The data of a saved EventReactMenu.
        :return: A formatted dictionary that can be passed to the constructor of a PingableRoleMenu.
        """
        kwargs = await super(PingableRoleMenu, cls).load_dict(bot, data)

        guild = bot.get_guild(data.get("guild_id"))
        pingable_role = guild.get_role(data.get("role_id"))
        await pingable_role.edit(mentionable=True)
        kwargs["pingable_role"] = pingable_role
        kwargs["ping_cooldown"] = int(data.get("cooldown_seconds"))

        return kwargs

    def to_dict(self):
        """
        Get the dictionary representation of a PingableRoleMenu.
        :return: A dictionary of the saveable attributes of a PingableRoleMenu.
        """
        kwargs = super(PingableRoleMenu, self).to_dict()
        kwargs["role_id"] = self.role.id
        kwargs["cooldown_seconds"] = self.cooldown
        return kwargs
