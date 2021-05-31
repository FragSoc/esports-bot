"""
The lib package was partially copied over from the BASED template project: https://github.com/Trimatix/BASED
It is modified and not actively synced with BASED, so will very likely be out of date.

.. codeauthor:: Trimatix
"""

import traceback

class UnrecognisedCustomEmoji(Exception):
    """Exception raised when creating an Emote instance, but the client could not match an emoji to the given ID.

    :var id: The ID that could not be matched
    :vartype id: int
    """

    def __init__(self, comment: str, id: int):
        """
        :param str comment: Description of the exception
        :param int id: The ID that could not be matched
        """
        super().__init__(comment)
        self.id = id


class InvalidStringEmoji(Exception):
    """Exception raised when creating an Emote instance from a string, but the string did not match any valid emote formats.

    :var val: The string that could not be matched
    :vartype val: str
    """

    def __init__(self, comment: str, val: str):
        """
        :param str comment: Description of the exception
        :param int val: The string that could not be matched
        """
        super().__init__(comment)
        self.val = val


class UnrecognisedReactionMenuMessage(Exception):
    """Exception to indicate that a reaction menu failed to initialize as its message could not be fetched from discord.
    This could be for a number of reasons, for example a change in permissions, or the message was deleted.
    """

    def __init__(self, guild: int, channel: int, msg: int):
        """
        :param int guild: The id of the guild containing the requested message
        :param int channel: The id of the channel containing the requested message
        :param int msg: The id of the requested message
        """
        self.guild = guild
        self.channel = channel
        self.msg = msg
        super().__init__("Failed to fetch message for reaction menu: guild " + str(guild) + " channel " + str(channel) + " message " + str(msg))


def print_exception_trace(e: Exception):
    """Prints the trace for an exception into stdout.
    Great for debugging errors that are swallowed by the event loop.

    :param Exception e: The exception whose stack trace to print
    """
    traceback.print_exception(type(e), e, e.__traceback__)
