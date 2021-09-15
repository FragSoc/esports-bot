import shlex

from discord import TextChannel
from typing import List


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
