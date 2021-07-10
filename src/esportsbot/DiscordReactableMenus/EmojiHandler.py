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


def partial_from_string(emoji_str: Union[str, Dict]) -> PartialEmoji:
    if isinstance(emoji_str, str):
        data = partial_data_from_string(emoji_str)
    elif isinstance(emoji_str, dict):
        data = emoji_str
    else:
        raise ValueError("The supplied emoji value was not of type dict or str!")
    return PartialEmoji.from_dict(data)


class MultiEmoji:
    def __init__(self, emoji_string: str = None, full_emoji: Emoji = None, partial_emoji: PartialEmoji = None):
        if emoji_string is None and full_emoji is None and partial_emoji is None:
            raise ValueError("There must be at least one value given that is not None")

        if full_emoji:
            self._partial = partial_from_emoji(full_emoji)
        elif emoji_string:
            self._partial = partial_from_string(emoji_string)
        elif partial_emoji:
            self._partial = partial_emoji
        else:
            raise ValueError("There must be at least one value given that is not None")

        self._name = self._partial.name
        self._emoji_id = self._partial.id
        self._animated = self._partial.animated

    @classmethod
    def get_emoji_from_input(cls, emoji_input):
        if isinstance(emoji_input, str):
            formatted_emoji = MultiEmoji(emoji_string=emoji_input)
        elif isinstance(emoji_input, PartialEmoji):
            formatted_emoji = MultiEmoji(partial_emoji=emoji_input)
        elif isinstance(emoji_input, Emoji):
            formatted_emoji = MultiEmoji(full_emoji=emoji_input)
        elif isinstance(emoji_input, MultiEmoji):
            return emoji_input
        else:
            raise ValueError(
                f"The supplied emoji must be of type: Union[Emoji, PartialEmoji, MultiEmoji, str]. "
                f"Given type was: {type(emoji_input).__name__}"
            )
        return formatted_emoji

    def __str__(self):
        return emoji.emojize(self.name, use_aliases=True)

    def __repr__(self):
        return emoji.demojize(self.name, use_aliases=True)

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
