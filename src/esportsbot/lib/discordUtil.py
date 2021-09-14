import shlex

from discord import Forbidden, RawReactionActionEvent, Message, Member, User, Client, DMChannel, GroupChannel, TextChannel
from typing import List, Tuple, Union
from . import emotes, exceptions

# Link to an empty image, to allow for an author name in embeds without providing an icon.
from .stringTyping import strIsChannelMention

EMPTY_IMAGE = "https://i.imgur.com/sym17F7.png"


async def reactionFromRaw(client: Client,
                          payload: RawReactionActionEvent) -> Tuple[Message,
                                                                    Union[User,
                                                                          Member],
                                                                    emotes.Emote]:
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


def load_discord_hooks(prefix_to_filter, guild_hooks, bot_user_id: int):
    """
    Loads the list of Discord Webhooks which are where the Event Notifications are sent to.
    :param prefix_to_filter: The Prefix to use to filter Webhooks to just the specific cog.
    :param guild_hooks: The list of lists of Webhooks, where each index is for a different Guild.
    :param bot_user_id: The Discord user ID of the bot that is running.
    """

    hooks = {}

    for guild in guild_hooks:
        # For each guild in the list...
        for g_hook in guild:
            # And for each Webhook in the guild...
            if prefix_to_filter in g_hook.name and g_hook.user.id == bot_user_id:
                # Only if the Webhook was created for the TwitterCog and by the bot.
                hooks[g_hook.id] = {"token": g_hook.token, "name": g_hook.name, "guild_id": g_hook.guild_id}

    return hooks


async def channel_from_mention(bot, c_id):
    """
    Gets an instance of a channel when the channel was mentioned in the message.
    :param bot: The instance of the bot to access discord with.
    :param c_id: The mentioned channel.
    :return: An instance of a channel or None if there is no channel with the given mention.
    """

    if not strIsChannelMention(c_id):
        # The string was not a mentioned channel.
        return None

    # Gets just the ID of the channel.
    cleaned_id = c_id[2:-1]
    channel = bot.get_channel(cleaned_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(cleaned_id)
        except Forbidden:
            # self.logger.error("Unable to access channel with id %s due to permission errors: %s", cleaned_id, e.text)
            return None
    return channel


def get_webhook_by_name(current_hooks, name, guild_id, prefix_to_filter):
    """
    Gets the information about a Discord Webhook given its name.
    :param current_hooks: The current known webhooks to search through.
    :param name: The name of the Webhook.
    :param guild_id: The ID of the guild where the Webhook is in.
    :param prefix_to_filter: The prefix used to ensure that the webhook belongs to the cog.
    :return: A Tuple of hook ID and hook information.
    """

    # current_hooks = self._twitch_app.hooks
    if prefix_to_filter not in name:
        # Only find webhooks created for this cog.
        name = prefix_to_filter + name
    for hook in current_hooks:
        if current_hooks.get(hook).get("name") == name:
            if current_hooks.get(hook).get("guild_id") == guild_id:
                return hook, current_hooks.get(hook)

    return None, None


def get_attempted_arg(message: str, arg_index: int) -> [str, List]:
    command_args = shlex.split(message)
    command_args.pop(0)
    attempted_arg = command_args[arg_index]
    return attempted_arg, command_args
