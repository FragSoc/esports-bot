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
    def __init__(self, guild: int, channel: int, msg: int):
        self.guild = guild
        self.channel = channel
        self.msg = msg
        super().__init__()
