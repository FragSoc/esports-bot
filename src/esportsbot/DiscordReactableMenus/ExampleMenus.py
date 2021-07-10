import datetime
from typing import Any, Union

from discord import Embed, PartialEmoji, Emoji, RawReactionActionEvent, Role

from esportsbot.DiscordReactableMenus.EmojiHandler import MultiEmoji
from esportsbot.DiscordReactableMenus.ReactableMenu import ReactableMenu
from esportsbot.DiscordReactableMenus.reactable_lib import clean_mentioned_role, get_role_from_id

BAR_LENGTH = 10
DEFAULT_ROLE_DESCRIPTION = "React with a specified emoji to receive a role!"
DEFAULT_ROLE_TITLE = "Role Reaction Menu"
AUTO_ENABLE_ROLE_REACT = True
DEFAULT_PING_DESCRIPTION = "React with the specified emoji to make a vote!"
DEFAULT_PING_TITLE = "Vote in This Poll"
NO_VOTES = "No votes received!"
AUTO_ENABLE_POLL_REACT = False


class RoleReactMenu(ReactableMenu):
    @classmethod
    async def from_dict(cls, bot, data) -> ReactableMenu:
        kwargs = await super().load_dict(bot, data)
        menu = RoleReactMenu(**kwargs)
        if menu.enabled:
            menu.enabled = False
            await menu.enable_menu(bot)
        return menu

    def __init__(self, **kwargs):
        if kwargs.get("title") is None:
            kwargs["title"] = DEFAULT_ROLE_TITLE

        if kwargs.get("description") is None:
            kwargs["description"] = DEFAULT_ROLE_DESCRIPTION

        if kwargs.get("add_func") is None:
            kwargs["add_func"] = self.react_add_func

        if kwargs.get("remove_func") is None:
            kwargs["remove_func"] = self.react_remove_func

        if kwargs.get("auto_enable") is None:
            kwargs["auto_enable"] = AUTO_ENABLE_ROLE_REACT

        super().__init__(**kwargs)

    async def react_add_func(self, payload: RawReactionActionEvent) -> bool:
        message_id: int = payload.message_id
        channel_id: int = payload.channel_id
        emoji_triggered: PartialEmoji = payload.emoji
        member = payload.member
        guild = self.message.guild

        if emoji_triggered in self:
            if isinstance(self[emoji_triggered]["descriptor"], Role):
                role_id = self[emoji_triggered]["descriptor"].id
            else:
                role_id = clean_mentioned_role(self[emoji_triggered]["descriptor"])
        else:
            role_id = 0

        if not role_id:
            channel = guild.get_channel(channel_id)
            message = await channel.fetch_message(message_id)
            await message.remove_reaction(emoji_triggered, member)
            return False

        role_to_add = get_role_from_id(guild, role_id)
        await member.add_roles(role_to_add, reason="Added With Role Reaction Menu")
        return True

    async def react_remove_func(self, payload: RawReactionActionEvent):
        emoji_triggered: PartialEmoji = payload.emoji
        guild = self.message.guild
        member = guild.get_member(payload.user_id)

        if member is None:
            member = await guild.fetch_member(payload.user_id)

        if emoji_triggered in self:
            if isinstance(self[emoji_triggered]["descriptor"], Role):
                role_id = self[emoji_triggered]["descriptor"].id
            else:
                role_id = clean_mentioned_role(self[emoji_triggered]["descriptor"])
        else:
            role_id = 0

        if not role_id:
            return False

        role_to_remove = get_role_from_id(guild, role_id)
        await member.remove_roles(role_to_remove, reason="Added With Role Reaction Menu")
        return True


class PollReactMenu(ReactableMenu):
    def __init__(self, **kwargs):
        if kwargs.get("title") is None:
            kwargs["title"] = DEFAULT_PING_TITLE

        if kwargs.get("description") is None:
            kwargs["description"] = DEFAULT_PING_DESCRIPTION

        if kwargs.get("add_func") is None:
            kwargs["add_func"] = self.react_add_func

        if kwargs.get("remove_func") is None:
            kwargs["remove_func"] = self.react_remove_func

        if kwargs.get("auto_enable") is None:
            kwargs["auto_enable"] = AUTO_ENABLE_POLL_REACT

        super().__init__(**kwargs)
        self.votes = {}
        self.total_votes = 0
        self.start_time = None

    def get_longest_option(self):
        longest = -1
        for option in self.options:
            if len(self.options.get(option).get("descriptor")) > longest:
                longest = len(self.options.get(option).get("descriptor"))
        return longest

    def get_winner(self):
        winner = ([None], -1)
        for option in self.votes:
            if self.votes.get(option).get("votes") > winner[-1]:
                winner = ([option], self.votes.get(option).get("votes"))
            elif self.votes.get(option).get("votes") == winner[-1]:
                winner = (winner[0] + [option], winner[-1])
        return winner

    def generate_results(self):
        if self.total_votes > 0:
            string = self.generate_results_string()
        else:
            string = NO_VOTES

        title = self.title
        description = self.description

        embed = Embed(title=f"{title} Results", description=description)
        embed.add_field(name="Results", value=string, inline=False)

        return embed

    def generate_results_string(self):
        max_length = self.get_longest_option()
        winner_ids, winner_votes = self.get_winner()
        winner_strings = "\n".join(self.make_bar(x, max_length, winner_votes, is_winner=True) for x in winner_ids)
        remaining_options = self.votes.copy()
        for winner in winner_ids:
            remaining_options.pop(winner)

        other_strings = ""
        for key, _ in sorted(remaining_options.items(), key=lambda x: x[1].get("votes"), reverse=True):
            other_strings += "\n" + self.make_bar(key, max_length, winner_votes)

        string = f"```\n{winner_strings}{other_strings}```"
        return string

    def make_bar(self, emoji_id, longest_descriptor, winning_votes, is_winner=False):
        num_votes = self.votes.get(emoji_id).get("votes")
        descriptor = self.options.get(emoji_id).get("descriptor")
        spacing = longest_descriptor - len(descriptor)
        bar_length = int((num_votes / winning_votes) * BAR_LENGTH)
        string = f"{descriptor}{' ' * spacing} | {'=' * bar_length}{'' if num_votes else ' '}" \
                 f"{'🏆' if is_winner else ''} +{num_votes} Vote{'' if num_votes == 1 else 's'}"

        return string

    async def enable_menu(self, bot) -> bool:
        if await super().enable_menu(bot):
            self.start_time = datetime.datetime.now()
            return True
        return False

    async def disable_menu(self, bot) -> bool:
        if await super().disable_menu(bot):
            self.start_time = None
            return True
        return False

    def add_option(self, emoji: Union[Emoji, PartialEmoji, MultiEmoji, str], descriptor: Any) -> bool:
        if super().add_option(emoji, descriptor):
            formatted_emoji = MultiEmoji.get_emoji_from_input(emoji)
            self.votes[formatted_emoji.emoji_id] = {"emoji": formatted_emoji, "votes": 0}
            return True
        return False

    def remove_option(self, emoji: Union[Emoji, PartialEmoji, str]) -> bool:
        if super().remove_option(emoji):
            formatted_emoji = MultiEmoji.get_emoji_from_input(emoji)
            return self.votes.pop(formatted_emoji.emoji_id, None) is not None
        return False

    async def react_add_func(self, payload: RawReactionActionEvent) -> bool:
        triggering_member = payload.member
        guild_from_react = payload.member.guild
        triggering_emoji = payload.emoji

        if triggering_emoji not in self:
            channel = guild_from_react.get_channel(payload.channel_id)
            message = await channel.fetch_message(payload.message_id)
            await message.remove_reaction(triggering_emoji, triggering_member)
            return False

        self.votes[triggering_emoji.id]["votes"] += 1
        self.total_votes += 1

        return True

    async def react_remove_func(self, payload: RawReactionActionEvent):
        triggering_emoji = payload.emoji

        if triggering_emoji not in self:
            return False

        self.votes[triggering_emoji.id]["votes"] -= 1
        self.total_votes -= 1
        return True
