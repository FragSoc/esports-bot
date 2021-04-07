from __future__ import annotations
import emoji
from . import client
from . import exceptions, stringTyping

from typing import Union, TYPE_CHECKING
if TYPE_CHECKING:
    from discord import PartialEmoji, Emoji


err_UnknownEmoji = "❓"
# True to raise an UnrecognisedCustomEmoji exception when requesting an unknown custom emoji
raiseUnkownEmojis = False
logUnknownEmojis = True
MAX_EMOJI_LEN = 10


def strIsUnicodeEmoji(c: str) -> bool:
    """Decide whether a given string contrains a single unicode emoji.

    :param str c: The string to test
    :return: True if c contains exactly one character, and that character is a unicode emoji. False otherwise.
    :rtype: bool
    """
    return len(c) <= MAX_EMOJI_LEN and emoji.emoji_count(c) == 1


def strIsCustomEmoji(s: str) -> bool:
    """Decide whether the given string matches the formatting of a discord custom emoji,
    being <:NAME:ID> where NAME is the name of the emoji, and ID is the integer ID.

    :param str c: The string to test
    :return: True if s 'looks like' a discord custom emoji, matching their structure. False otherwise.
    :rtype: bool
    """
    if s.startswith("<") and s.endswith(">"):
        try:
            first = s.index(":")
            second = first + s[first + 1:].index(":") + 1
        except ValueError:
            return False
        return stringTyping.strIsInt(s[second + 1:-1])
    return False


class Emote:
    """A class that really shouldnt be necessary, acting as a union over the str (unicode) and Emoji type emojis used
    and returned by discord. To instance this class, provide exactly one of the constructor's keyword arguments.

    :var id: The ID of the Emoji that this object represents, if isID
    :vartype id: int
    :var unicode: The string unicode emoji that this object represents, if isUnicode
    :vartype unicode: 
    :var isID: True if this object represents a custom emoji, False if it represents a unicode emoji.
    :vartype isID: bool
    :var isUnicode: False if this object represents a custom emoji, True if it represents a unicode emoji.
    :vartype isUnicode: bool
    :var sendable: A string sendable in a discord message that discord will render an emoji over.
    :vartype sendable: str
    :var EMPTY: static class variable representing an empty emoji
    :vartype EMPTY: Emote
    """
    EMPTY: "Emote" = None

    def __init__(self, id: int = -1, unicode: str = "", rejectInvalid: bool = False):
        """
        :param int id: The ID of the custom emoji that this object should represent.
        :param str unicode: The unicode emoji that this object should represent.
        :param bool rejectInvalid: When true, an exception is guaranteed to raise if an invalid emoji is requested,
                                    regardless of raiseUnknownEmojis (Default False)
        :raise exceptions.UnrecognisedCustomEmoji: When rejectInvalid=True is present in kwargs, and a custom emoji
                                                    is given that does not exist or the client cannot access.                                   
        """

        if id == -1 and unicode == "":
            raise ValueError("At least one of id or unicode is required")
        elif id != -1 and unicode != "":
            raise ValueError("Can only accept one of id or unicode, not both")
        if type(id) != int:
            raise TypeError("Given incorrect type for Emote ID: " + type(id).__name__)
        if type(unicode) != str:
            raise TypeError("Given incorrect type for Emote unicode: " + type(unicode).__name__)

        self.id = id
        self.unicode = unicode
        self.isID = id != -1
        self.isUnicode = not self.isID
        self.sendable = self.unicode if self.isUnicode else str(client.instance().get_emoji(self.id))
        if self.sendable == "None":
            if logUnknownEmojis:
                print("Unrecognised custom emoji ID in Emote constructor: " + str(self.id))
            if raiseUnkownEmojis or rejectInvalid:
                raise exceptions.UnrecognisedCustomEmoji("Unrecognised custom emoji ID in Emote constructor: " + str(self.id), self.id)
            self.sendable = err_UnknownEmoji


    def toDict(self, **kwargs) -> dict:
        """Serialize this emoji to dictionary format for saving to file.

        :return: A dictionary containing all information needed to reconstruct this emoji.
        :rtype: dict
        """
        if self.isUnicode:
            return {"unicode": self.unicode}
        return {"id": self.id}


    def __repr__(self) -> str:
        """Get a string uniquely identifying this object, specifying what type of emoji it represents and the emoji itself.

        :return: A string identifying this object.
        :rtype: str
        """
        return "<Emote-" + ("id" if self.isID else "unicode") + ":" + (str(self.id) if self.isID else self.unicode) + ">"


    def __hash__(self) -> int:
        """Calculate a hash of this emoji, based on its repr string.
        Two Emote objects representing the same emoji will have the same repr and hash.

        :return: A hash of this emoji
        :rtype: int
        """
        return hash(repr(self))


    def __eq__(self, other: Emote) -> bool:
        """Decide if this Emote is equal to another.
        Two Emotes are equal if they represent the same emoji (i.e ID/unicode) of the same type (custom/unicode)

        :param Emote other: the emoji to compare this one to
        :return: True of this emoji is semantically equal to the given emoji, False otherwise
        :rtype: bool
        """
        return type(other) == Emote and self.sendable == other.sendable


    def __str__(self) -> str:
        """Get the object's 'sendable' string.

        :return: A string sendable to discord that will be translated into an emoji by the discord client.
        :rtype: str
        """
        return self.sendable


    @classmethod
    def fromDict(cls, emojiDict: dict, **kwargs) -> Emote:
        """Construct a Emote object from its dictionary representation.
        If both an ID and a unicode representation are provided, the emoji ID will be used.

        TODO: If ID is -1, use unicode. If unicode is "", use ID.

        :param dict emojiDict: A dictionary containing either an ID (for custom emojis) or
                                a unicode emoji string (for unicode emojis)
        :param bool rejectInvalid: When true, an exception is guaranteed to raise if an invalid emoji is requested,
                                    regardless of raiseUnknownEmojis (Default False)
        :raise exceptions.UnrecognisedCustomEmoji: When rejectInvalid=True is present in kwargs, and a custom emoji
                                                    is given that does not exist or the client cannot access.                                   
        :return: A new Emote object as described in emojiDict
        :rtype: Emote
        """
        rejectInvalid = kwargs["rejectInvalid"] if "rejectInvalid" in kwargs else False

        if type(emojiDict) == Emote:
            return emojiDict
        if "id" in emojiDict:
            return Emote(id=emojiDict["id"], rejectInvalid=rejectInvalid)
        else:
            return Emote(unicode=emojiDict["unicode"], rejectInvalid=rejectInvalid)


    @classmethod
    def fromPartial(cls, e: PartialEmoji, rejectInvalid: bool = False) -> Emote:
        """Construct a new Emote object from a given discord.PartialEmoji.

        :param bool rejectInvalid: When true, an exception is guaranteed to raise if an invalid emoji is requested,
                                    regardless of raiseUnknownEmojis (Default False)
        :raise exceptions.UnrecognisedCustomEmoji: When rejectInvalid=True is present in kwargs, and a custom emoji
                                                    is given that does not exist or the client cannot access.                                   
        :return: A Emote representing e
        :rtype: Emote
        """
        if type(e) == Emote:
            return e
        if e.is_unicode_emoji():
            return Emote(unicode=e.name, rejectInvalid=rejectInvalid)
        else:
            return Emote(id=e.id, rejectInvalid=rejectInvalid)


    @classmethod
    def fromReaction(cls, e: Union[Emoji, PartialEmoji, str], rejectInvalid: bool = False) -> Emote:
        """Construct a new Emote object from a given discord.PartialEmoji, discord.Emoji, or string.

        :param e: The reaction emoji to convert to Emote
        :type e: Union[Emoji, PartialEmoji, str]
        :param bool rejectInvalid: When true, an exception is guaranteed to raise if an invalid emoji is requested,
                                    regardless of raiseUnknownEmojis (Default False)
        :raise exceptions.UnrecognisedCustomEmoji: When rejectInvalid=True is present in kwargs, and a custom emoji
                                                    is given that does not exist or the client cannot access.                                   
        :return: A Emote representing e
        :rtype: Emote
        """
        if type(e) == Emote:
            return e
        if type(e) == str:
            if strIsUnicodeEmoji(e):
                return Emote(unicode=e, rejectInvalid=rejectInvalid)
            elif strIsCustomEmoji(e):
                return Emote.fromStr(e, rejectInvalid=rejectInvalid)
            else:
                raise exceptions.InvalidStringEmoji("Given a string that does not match any emoji format: " + e, e)
        if type(e) == PartialEmoji:
            return Emote.fromPartial(e, rejectInvalid=rejectInvalid)
        else:
            return Emote(id=e.id, rejectInvalid=rejectInvalid)


    @classmethod
    def fromStr(cls, s: str, rejectInvalid: bool = False) -> Emote:
        """Construct a Emote object from a string containing either a unicode emoji or a discord custom emoji.
        
        s may also be a Emote (returns s), a dictionary-serialized Emote (returns Emote.fromDict(s)), or
        only an ID of a discord custom emoji (may be either str or int)

        If 

        :param str s: A string containing only one of: A unicode emoji, a discord custom emoji, or
                        the ID of a discord custom emoji.
        :param bool rejectInvalid: When true, an exception is guaranteed to raise if an invalid emoji is requested,
                                    regardless of raiseUnknownEmojis (Default False)
        :raise exceptions.UnrecognisedCustomEmoji: When rejectInvalid=True is present in kwargs, and a custom emoji
                                                is given that does not exist or the client cannot access.                                   
        :return: A Emote representing the given string emoji
        :rtype: Emote
        """
        if type(s) == Emote:
            return s
        if type(s) == dict:
            return Emote.fromDict(s, rejectInvalid=rejectInvalid)
        elif type(s) == str:
            if strIsUnicodeEmoji(s):
                return Emote(unicode=s, rejectInvalid=rejectInvalid)
            elif strIsCustomEmoji(s):
                return Emote(id=int(s[s[s.index(":") + 1:].index(":") + 3:-1]), rejectInvalid=rejectInvalid)
            elif stringTyping.strIsInt(s):
                return Emote(id=int(s), rejectInvalid=rejectInvalid)
            else:
                raise exceptions.InvalidStringEmoji("Given a string that does not match any emoji format: " + s, s)
        else:
            raise TypeError("Expected s of type str, dict or Emote, got " + type(s).__name__)


# 'static' object representing an empty/lack of emoji
Emote.EMPTY = Emote(unicode=" ")
Emote.EMPTY.isUnicode = False
Emote.EMPTY.unicode = ""
Emote.EMPTY.sendable = ""
