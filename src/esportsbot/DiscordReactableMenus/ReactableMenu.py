import ast
from typing import Dict, List, Any, Union

import discord
from discord import Embed, HTTPException, Message, Emoji, PartialEmoji, Role, TextChannel
from emoji import emojize

from esportsbot.DiscordReactableMenus.EmojiHandler import MultiEmoji, partial_from_emoji, partial_from_string

DISABLED_STRING = " (Currently Disabled)"


class ReactableMenu:
    def __init__(self, add_func=None, remove_func=None, show_ids=True, auto_enable=False, **kwargs):
        self.react_add_func = add_func
        self.react_remove_func = remove_func
        self.id = kwargs.pop("id", None)
        self.message = kwargs.pop("message", None)
        self.guild = None if not self.message else self.message.guild
        self.channel = None if not self.message else self.message.channel
        self.options = kwargs.pop("options", {})
        self.enabled = kwargs.pop("enabled", False)
        self.use_inline = kwargs.pop("use_inline", False)
        self.title = kwargs.pop("title", "Reactable Menu")
        self.description = kwargs.pop("description", "")
        self.title_suffix = "" if self.enabled else DISABLED_STRING
        self.colour = discord.Colour.green() if self.enabled else discord.Colour.red()
        self.show_ids = show_ids
        self.auto_enable = auto_enable

    def __str__(self) -> str:
        __str = f"Title:{self.title} | Description: {self.description}"
        for emoji, descriptor in self.options.items():
            if isinstance(emoji, str):
                __str += f"\nEmoji: {emojize(emoji)} | Descriptor: {descriptor}"
            else:
                __str += f"\nEmoji: {emoji.name} | Descriptor: {descriptor}"
        return __str

    def __repr__(self):
        return repr(self.options)

    def __contains__(self, item):
        return self.__getitem__(item) is not None

    def __getitem__(self, item: Union[Emoji, PartialEmoji, str]):
        if isinstance(item, str):
            p_emoji = partial_from_string(item)
        elif isinstance(item, PartialEmoji):
            p_emoji = item
        elif isinstance(item, Emoji):
            p_emoji = partial_from_emoji(item)
        else:
            return None

        emoji_id = p_emoji.id if p_emoji.id else p_emoji.name

        return self.options.get(emoji_id)

    def to_dict(self):
        data = {
            "id": self.id,
            "title": self.title,
            "guild_id": self.message.guild.id,
            "channel_id": self.message.channel.id,
            "options": self.serialize_options(),
            "enabled": self.enabled,
            "show_ids": self.show_ids
        }
        return data

    def serialize_options(self):
        data = {}
        for option in self.options:
            option_data = self.options.get(option)
            emoji_data = option_data.get("emoji").to_dict()
            descriptor = option_data.get("descriptor")
            data[option] = {"emoji": emoji_data, "descriptor": descriptor}
        return data

    @staticmethod
    def deserialize_options(options) -> Dict[Union[Emoji, str], Any]:
        data = {}
        if isinstance(options, str):
            options = ast.literal_eval(options)
        for option in options:
            option_data = options.get(option)
            emoji = MultiEmoji(emoji_string=option_data.get("emoji"))
            descriptor = option_data.get("descriptor")
            data[option] = {"emoji": emoji, "descriptor": descriptor}
        return data

    @classmethod
    async def from_dict(cls, bot, data):
        kwargs = await cls.load_dict(bot, data)
        return ReactableMenu(**kwargs)

    @classmethod
    async def load_dict(cls, bot, data) -> Dict:
        kwargs = {"id": int(data.get("id"))}

        guild_id = int(data.get("guild_id"))
        channel_id = int(data.get("channel_id"))
        guild = bot.get_guild(guild_id)
        channel = guild.get_channel(channel_id)
        kwargs["message"] = await channel.fetch_message(kwargs["id"])
        if kwargs["message"] is None:
            raise ValueError("The message for this reaction menu has been deleted!")

        if not kwargs["message"].embeds:
            raise ValueError("The message for this reaction menu has no menu in it!")

        embed = kwargs["message"].embeds[0]
        kwargs["description"] = embed.description
        kwargs["title"] = data.get("title")
        kwargs["options"] = cls.deserialize_options(data.get("options"))
        kwargs["enabled"] = bool(data.get("enabled"))
        kwargs["show_ids"] = bool(data.get("show_ids"))

        return kwargs

    def add_option(self, emoji: Union[Emoji, PartialEmoji, MultiEmoji, str], descriptor: Any) -> bool:
        if isinstance(descriptor, Role):
            descriptor = descriptor.mention

        try:
            formatted_emoji = MultiEmoji.get_emoji_from_input(emoji)

            emoji_id = formatted_emoji.emoji_id if formatted_emoji.emoji_id else formatted_emoji.name

            if emoji_id in self.options:
                return False

            self.options[emoji_id] = {"emoji": formatted_emoji, "descriptor": descriptor}
            return True
        except ValueError:
            return False

    def remove_option(self, emoji: Union[Emoji, PartialEmoji, MultiEmoji, str]) -> bool:
        try:
            formatted_emoji = MultiEmoji.get_emoji_from_input(emoji)
            return self.options.pop(formatted_emoji.emoji_id, None) is not None
        except ValueError:
            return False

    def add_many(self, options: Dict[Union[Emoji, PartialEmoji, str], Any]) -> List[Dict[str, str]]:
        failed = []
        for emoji, descriptor in options.items():
            if not self.add_option(emoji, descriptor):
                failed.append({emoji: descriptor})
        return failed

    def remove_many(self, emojis: List[Union[Emoji, PartialEmoji, str]]) -> List[str]:
        failed = []
        for emoji in emojis:
            if not self.remove_option(emoji):
                failed.append(str(emoji))
        return failed

    def generate_embed(self) -> Embed:
        embed = Embed(title=f"{self.title} {self.title_suffix}", description=self.description, colour=self.colour)
        for emoji_id in self.options:
            emoji = self.options.get(emoji_id).get("emoji").discord_emoji
            descriptor = self.options.get(emoji_id).get("descriptor")
            embed.add_field(name=emoji, value=descriptor, inline=self.use_inline)

        return embed

    def add_footer(self, embed):
        if self.show_ids and self.id:
            embed.set_footer(text=f"Menu message id: {self.id}")

    def toggle_footer(self):
        self.show_ids = not self.show_ids

    async def update_visuals(self):
        if self.enabled:
            self.title_suffix = ""
            self.colour = discord.Colour.green()
        else:
            self.title_suffix = DISABLED_STRING
            self.colour = discord.Colour.red()
        await self.update_message()

    async def enable_menu(self, bot) -> bool:
        if not self.enabled:
            self.enabled = True
            await self.update_visuals()
            bot.add_listener(self.on_react_add, "on_raw_reaction_add")
            bot.add_listener(self.on_react_remove, "on_raw_reaction_remove")
            return True
        return False

    async def disable_menu(self, bot) -> bool:
        if self.enabled:
            await self.message.clear_reactions()
            self.enabled = False
            await self.update_visuals()
            bot.remove_listener(self.on_react_add, "on_raw_reaction_add")
            bot.remove_listener(self.on_react_remove, "on_raw_reaction_remove")
            return True
        return False

    async def toggle_menu(self, bot) -> bool:
        if not self.enabled:
            return await self.enable_menu(bot)
        else:
            return await self.disable_menu(bot)

    async def finalise_and_send(self, bot, channel: TextChannel):
        embed = self.generate_embed()
        self.add_footer(embed)
        await self.send_to_channel(channel, embed)
        await self.message.edit(embed=embed)
        if self.auto_enable:
            await self.enable_menu(bot)

    async def update_message(self):
        embed = self.generate_embed()
        self.add_footer(embed)
        await self.message.edit(embed=embed)
        if self.enabled:
            await self.add_reactions()

    async def send_to_channel(self, channel: TextChannel, embed: Embed = None) -> Message:
        if embed is None:
            embed = self.generate_embed()
        self.message: Message = await channel.send(embed=embed)
        self.guild = self.message.guild
        self.channel = self.message.channel
        self.id = self.message.id
        return self.message

    async def add_reactions(self, message: Message = None):
        if message is None:
            message = self.message

        if message is None:
            raise ValueError("There is no message to add reactions to")

        await message.clear_reactions()

        for emoji_id in self.options:
            emoji = self.options.get(emoji_id).get("emoji")
            try:
                await message.add_reaction(emoji.discord_emoji)
            except HTTPException:
                pass

    async def on_react_add(self, payload):
        if payload is None:
            return None
        if self.enabled and self.react_add_func and not payload.member.bot and payload.message_id == self.id:
            return await self.react_add_func(payload)
        return None

    async def on_react_remove(self, payload):
        if payload is None:
            return None
        if self.enabled and self.react_remove_func and payload.message_id == self.id:
            return await self.react_remove_func(payload)
        return None
