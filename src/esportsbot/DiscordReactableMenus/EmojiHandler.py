from typing import Dict, Union

import emoji
from discord import PartialEmoji, Emoji


def partial_from_emoji(full_emoji: Emoji) -> PartialEmoji:
    """
    Create a partial emoji from a full emoji.
    :param full_emoji: The full emoji to create a partial from.
    :return: A Partial Emoji with the data from the full one.
    """
    data = {"name": full_emoji.name, "id": full_emoji.id, "animated": full_emoji.animated}
    return PartialEmoji.from_dict(data)


def partial_data_from_string(emoji_str: str) -> Dict:
    """
    Get the dictionary representation of a partial emoji from a string representation of an emoji. This string will most
    likely have come from the contents of a message.
    :param emoji_str: The string of an emoji to convert.
    :return: A dictionary that can be used to create a Partial Emoji.
    """
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
    """
    Create a partial emoji from a string.This string will most likely have come from the contents of a message.
    :param emoji_str: The string representation of an emoji.
    :return: A Partial Emoji.
    """
    data = None
    if isinstance(emoji_str, str):
        data = partial_data_from_string(emoji_str)

    if not data:
        raise ValueError("Unable to form emoji from given string")
    return PartialEmoji.from_dict(data)


class MultiEmoji:
    """
    This class is used to unify every kind of emoji to a generic class. Including Unicode Emojis, Discord Emojis, Static Custom
    Discord Emojis and Animated Custom Discord Emojis.
    """
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
        """
        Create a MultiEmoji from a dictionary.
        :param data: A MultiEmoji in the form of a dictionary.
        :return: A MultiEmoji from the given data.
        """
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
        """
        Get the name of the emoji.
        """
        return self._name

    @property
    def emoji_id(self):
        """
        Get the ID of the emoji.
        """
        return self._emoji_id

    @property
    def animated(self):
        """
        Get whether or not the emoji is an animated emoji.
        :return: True if the emoji is animated, False otherwise.
        """
        return self._animated

    @property
    def discord_emoji(self):
        """
        Get a discord compatible version of the emoji. Can be used in things such as reactions.
        :return: A discord Partial Emoji.
        """
        return self._partial

    def to_dict(self):
        """
        Get the dictionary representation of a MultiEmoji.
        :return:
        """
        return self._partial.to_dict()

    def __hash__(self):
        return self._emoji_id


class EmojiKeyError(Exception):
    """
    An error raised when the same emoji is used in a dictionary.
    """
    def __init__(self, emoji_id, *args):
        super().__init__(*args)
        self.message = f"There is already an emoji with the ID {emoji_id} as an option."
        self.emoji = emoji_id
