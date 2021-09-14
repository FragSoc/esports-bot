from typing import Dict, Union

import emoji
from discord import PartialEmoji, Emoji


def partial_from_emoji(full_emoji: Emoji) -> PartialEmoji:
    data = {"name": full_emoji.name, "id": full_emoji.id, "animated": full_emoji.animated}
    return PartialEmoji.from_dict(data)


def partial_data_from_string(emoji_str: str) -> Dict:
    converted_emoji = emoji.demojize(emoji_str, use_aliases=True)
    if converted_emoji != emoji_str:
        return {"name": emoji_str, "id": None, "animated": False}

    if emoji_str.count(":") < 2:
        return {}

    animated = "<a:" in emoji_str
    first_colon_index = emoji_str.index(":")
    second_colon_index = emoji_str.index(":", first_colon_index + 1)

    name = emoji_str[first_colon_index + 1:second_colon_index]
    emoji_id = emoji_str[second_colon_index + 1:-1]

    return {"name": name, "id": emoji_id, "animated": animated}


def partial_from_string(emoji_str: str) -> PartialEmoji:
    data = None
    if isinstance(emoji_str, str):
        data = partial_data_from_string(emoji_str)

    if not data:
        raise ValueError("Unable to form emoji from given string")
    return PartialEmoji.from_dict(data)


class MultiEmoji:
    def __init__(self, emoji_input: Union[str, dict, Emoji, PartialEmoji, "MultiEmoji"]):

        if isinstance(emoji_input, str):
            self._partial = partial_from_string(emoji_input)
        elif isinstance(emoji_input, Emoji):
            self._partial = partial_from_emoji(emoji_input)
        elif isinstance(emoji_input, PartialEmoji):
            self._partial = emoji_input
        elif isinstance(emoji_input, MultiEmoji):
            self._partial = emoji_input._partial
        elif isinstance(emoji_input, dict):
            self._partial = PartialEmoji.from_dict(emoji_input)
        else:
            raise ValueError("The given emoji input must of type str, discord.Emoji or discord.PartialEmoji")

        self._name = str(self._partial.name)
        self._emoji_id = self._partial.id if self._partial.id else self._name
        self._emoji_id = str(self._emoji_id)
        self._animated = self._partial.animated

    @classmethod
    def from_dict(cls, data):
        return MultiEmoji(PartialEmoji.from_dict(data))

    def __str__(self):
        return emoji.emojize(self.name, use_aliases=True)

    def __repr__(self):
        return emoji.demojize(self.name, use_aliases=True)

    def __eq__(self, other):
        if not isinstance(other, MultiEmoji):
            return False
        else:
            return self._emoji_id == other._emoji_id

    def __dict__(self):
        return self.to_dict()

    @property
    def name(self):
        return self._name

    @property
    def emoji_id(self):
        return self._emoji_id

    @property
    def animated(self):
        return self._animated

    @property
    def discord_emoji(self):
        return self._partial

    def to_dict(self):
        return self._partial.to_dict()

    def __hash__(self):
        return self._emoji_id


class EmojiKeyError(Exception):
    def __init__(self, emoji_id, *args):
        super().__init__(*args)
        self.message = f"There is already an emoji with the ID {emoji_id} as an option."
        self.emoji = emoji_id
