from discord import RawReactionActionEvent, Message, Member, User, Client, DMChannel, GroupChannel, TextChannel
from typing import Tuple, Union
from . import emotes, exceptions


# Link to an empty image, to allow for an author name in embeds without providing an icon.
EMPTY_IMAGE = "https://i.imgur.com/sym17F7.png"


async def reactionFromRaw(client: Client, payload: RawReactionActionEvent) -> Tuple[Message, Union[User, Member], emotes.Emote]:
    """Retrieve complete Reaction and user info from a RawReactionActionEvent payload.

    :param RawReactionActionEvent payload: Payload describing the reaction action
    :return: The message whose reactions changed, the user who completed the action, and the emoji that changed.
    :rtype: Tuple[Message, Union[User, Member], Emote]
    """
    emoji = None
    user = None
    message = None

    if payload.member is None:
        # Get the channel containing the reacted message
        if payload.guild_id is None:
            channel = client.get_channel(payload.channel_id)
        else:
            guild = client.get_guild(payload.guild_id)
            if guild is None:
                return None, None, None
            channel = guild.get_channel(payload.channel_id)

        # Individual handling for each channel type for efficiency
        if isinstance(channel, DMChannel):
            if channel.recipient.id == payload.user_id:
                user = channel.recipient
            else:
                user = channel.me
        elif isinstance(channel, GroupChannel):
            # Group channels should be small and far between, so iteration is fine here.
            for currentUser in channel.recipients:
                if currentUser.id == payload.user_id:
                    user = currentUser
                if user is None:
                    user = channel.me
        # Guild text channels
        elif isinstance(channel, TextChannel):
            user = channel.guild.get_member(payload.user_id)
        else:
            return None, None, None

        # Fetch the reacted message (api call)
        message = await channel.fetch_message(payload.message_id)

    # If a reacting member was given, the guild can be inferred from the member.
    else:
        user = payload.member
        message = await payload.member.guild.get_channel(payload.channel_id).fetch_message(payload.message_id)

    if message is None:
        return None, None, None

    # Convert reacted emoji to BasedEmoji
    try:
        emoji = emotes.Emote.fromPartial(payload.emoji, rejectInvalid=True)
    except exceptions.UnrecognisedCustomEmoji:
        return None, None, None

    return message, user, emoji


async def send_timed_message(channel: TextChannel, *args, timer: int = 15, **kwargs):
    """Sends a message to a specific channel that gets deleted after a given amount of seconds.

    :param TextChannel channel: The channel to send the message to.
    :param int timer: The number of seconds to wait until deleting the message (Default 15)
    """
    timed_message = await channel.send(*args, **kwargs)
    await timed_message.delete(delay=timer)
