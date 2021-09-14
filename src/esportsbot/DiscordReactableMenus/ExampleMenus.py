import datetime
import inspect
from collections import defaultdict
from typing import Dict

import discord
from discord import Embed, PartialEmoji, RawReactionActionEvent, Role

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
DATE_FORMAT = "%m-%d-%Y %H:%M:%S"

CONFIRM_EMOJI = MultiEmoji("✅")
# CANCEL_EMOJI = MultiEmoji("❎")
CANCEL_EMOJI = MultiEmoji("❌")
CONFIRM_DESC = "Confirm"
CANCEL_DESC = "Cancel"


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
        emoji_triggered = payload.emoji
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
            await message.clear_reaction(emoji_triggered)
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

        if kwargs.get("auto_enable") is None:
            kwargs["auto_enable"] = AUTO_ENABLE_POLL_REACT

        super().__init__(**kwargs)
        self.total_votes = 0
        self.poll_length = kwargs["poll_length"]
        self.end_time = kwargs.get("end_time", datetime.datetime.now() + datetime.timedelta(seconds=self.poll_length))
        self.author = kwargs["author"]

    @classmethod
    async def load_dict(cls, bot, data) -> Dict:
        kwargs = await super(PollReactMenu, cls).load_dict(bot, data)
        kwargs["poll_length"] = data.get("length")
        kwargs["end_time"] = datetime.datetime.strptime(data.get("end_time"), DATE_FORMAT)
        kwargs["author"] = bot.get_user(data.get("author_id"))
        return kwargs

    @classmethod
    async def from_dict(cls, bot, data):
        kwargs = await cls.load_dict(bot, data)
        menu = PollReactMenu(**kwargs)
        if menu.enabled:
            menu.enabled = False
            await menu.enable_menu(bot)
        return menu

    def to_dict(self) -> Dict:
        kwargs = super(PollReactMenu, self).to_dict()
        kwargs["end_time"] = self.end_time.strftime(DATE_FORMAT)
        kwargs["length"] = self.poll_length
        kwargs["author_id"] = self.author.id
        return kwargs

    async def generate_results(self):
        results = await self.get_results()
        if self.total_votes > 0:
            string = self.generate_results_string(results)
        else:
            string = NO_VOTES

        title = self.title
        description = self.description

        embed = Embed(title=f"{title} Results", description=description)
        embed.add_field(name="Results", value=string, inline=False)

        return embed

    def get_longest_option(self):
        longest = -1
        for option in self.options:
            if len(self.options.get(option).get("descriptor")) > longest:
                longest = len(self.options.get(option).get("descriptor"))
        return longest

    def get_winner(self):
        winner = ([None], -1)
        for react in self.message.reaction:
            self.total_votes += react.count
            if react.count > winner[-1]:
                winner = ([react.emoji], react.count)
            elif react.count == winner[-1]:
                winner = (winner[0] + [react.emoji], winner[-1])
        return winner

    async def get_results(self):
        await self.get_total_votes()
        results = {"winner": [], "winner_count": -1, "reactions": defaultdict(list)}
        """
        winner_count : count,
        reactions : {
            0 : [reactions],
            1 : [reactions],
            ...
        }
        """
        sorted_reactions = sorted(self.message.reactions, key=lambda x: x.count, reverse=True)
        for reaction in sorted_reactions:
            if reaction.count - 1 > results.get("winner_count"):
                results["winner_count"] = reaction.count - 1
            results["reactions"][reaction.count - 1].append(reaction)

        return results

    def generate_results_string(self, results):
        max_length = self.get_longest_option()
        winning_votes = results.get("winner_count")
        res_string = ""
        for i in range(0, max(results.get("reactions").keys()) + 1):
            reacts = results.get("reactions").get(i)
            if reacts:
                res_string = "\n".join(self.make_bar(x, max_length, winning_votes, i) for x in reacts) + "\n" + res_string
        return f"```{res_string}```"

    async def get_total_votes(self):
        updated_message = await self.message.channel.fetch_message(self.id)
        self.total_votes = 0
        self.message = updated_message
        for reaction in updated_message.reactions:
            self.total_votes += reaction.count - 1
        return self.total_votes

    def make_bar(self, reaction, longest_descriptor, winning_votes, num_votes):
        winner = winning_votes == num_votes
        react_as_emoji = MultiEmoji(reaction.emoji)
        descriptor = self.options.get(react_as_emoji.emoji_id).get("descriptor")
        spacing = longest_descriptor - len(descriptor)
        bar_length = int((num_votes / winning_votes) * BAR_LENGTH)
        string = f"{descriptor}{' ' * spacing} | {'=' * bar_length}{'' if num_votes else ' '}" \
                 f"{'🏆' if winner else ''} +{num_votes} Vote{'' if num_votes == 1 else 's'}"
        return string

    async def enable_menu(self, bot) -> bool:
        if await super().enable_menu(bot):
            if not self.end_time:
                self.end_time = datetime.datetime.now() + datetime.timedelta(seconds=self.poll_length)
            return True
        return False

    async def disable_menu(self, bot) -> bool:
        if await super().disable_menu(bot):
            self.end_time = None
            return True
        return False

    async def react_add_func(self, payload: RawReactionActionEvent) -> bool:
        guild_from_react = payload.member.guild
        triggering_emoji = payload.emoji

        if triggering_emoji not in self:
            channel = guild_from_react.get_channel(payload.channel_id)
            message = await channel.fetch_message(payload.message_id)
            await message.clear_reaction(triggering_emoji)
            return False

        return True


class ActionConfirmationMenu(ReactableMenu):
    def __init__(self, **kwargs):
        if not kwargs.get("use_inline"):
            kwargs["use_inline"] = True

        if not kwargs.get("add_func"):
            kwargs["add_func"] = self.react_add_func

        super().__init__(**kwargs)

        self.confirm_func = None
        self.confirm_args = None
        self.confirm_kwargs = None
        self.confirm_is_coro = False

        self.cancel_func = None
        self.cancel_args = None
        self.cancel_kwargs = None
        self.cancel_is_coro = False

        self.was_confirmed = False
        self.delete_after = kwargs.get("delete_after", False)
        self.add_option(CONFIRM_EMOJI, CONFIRM_DESC)
        self.add_option(CANCEL_EMOJI, CANCEL_DESC)

    async def update_visuals(self):
        if self.enabled:
            self.title_suffix = ""
            self.colour = discord.Colour.green()
        else:
            self.title_suffix = "(Action Confirmed)" if self.was_confirmed else "(Action Cancelled)"
            self.colour = discord.Colour.red()
        await self.update_message()

    def set_confirm_func(self, func, *args, **kwargs):
        self.confirm_func = func
        self.confirm_is_coro = inspect.iscoroutinefunction(func)
        self.confirm_args = args
        self.confirm_kwargs = kwargs

    def set_cancel_func(self, func, *args, **kwargs):
        self.cancel_func = func
        self.cancel_is_coro = inspect.iscoroutinefunction(func)
        self.cancel_args = args
        self.cancel_kwargs = kwargs

    async def react_add_func(self, payload):
        triggering_member = payload.member
        guild_from_react = payload.member.guild
        triggering_emoji = payload.emoji

        formatted_emoji = MultiEmoji(triggering_emoji)

        if formatted_emoji not in self:
            channel = guild_from_react.get_channel(payload.channel_id)
            message = await channel.fetch_message(payload.message_id)
            await message.clear_reaction(triggering_emoji)
            return False

        if formatted_emoji == CONFIRM_EMOJI:
            if self.confirm_is_coro:
                await self.confirm_func(*self.confirm_args, **self.confirm_kwargs)
            else:
                self.confirm_func(*self.confirm_args, **self.confirm_kwargs)
            self.description = f"Event deletion confirmed by {triggering_member.name}#{triggering_member.discriminator}"
            self.was_confirmed = True
        elif formatted_emoji == CANCEL_EMOJI:
            if self.cancel_is_coro:
                await self.cancel_func(*self.cancel_args, **self.cancel_kwargs)
            else:
                self.cancel_func(*self.cancel_args, **self.cancel_kwargs)
            self.description = f"Event deletion cancelled by {triggering_member.name}#{triggering_member.discriminator}"
            self.was_confirmed = False

        if self.delete_after:
            await self.message.delete()
        else:
            await self.update_visuals()
