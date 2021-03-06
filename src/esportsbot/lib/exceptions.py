class UnrecognisedEmoji(Exception):
    """Exception raised when creating an Emote instance, but the client could not match an emoji to the given ID.

    :var id: The ID that coult not be matched
    :vartype id: int
    """

    def __init__(self, comment: str, id: int):
        """
        :param str comment: Description of the exception
        :param int id: The ID that coult not be matched
        """
        super().__init__(comment)
        self.id = id


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
