from esportsbot.db_gateway import DBGatewayActions
from esportsbot.models import VoicemasterMaster, VoicemasterSlave


def role_id_from_mention(pre_clean_data: str) -> int:
    """Extracts the ID of a role from a role mention.
    Will also accept strings containing a role ID, and will reject invalid integers with a ValueError.
    This does validate the ID further, e.g the size of the ID, or the existence of a role with the ID.

    :param str pre_clean_data: A string containing either a role mention or ID
    :return: The ID quoted in pre_clean_data
    :rtype: int
    :raise ValueError: When given an ID containing non-integer characters
    """
    return int(pre_clean_data.lstrip("<@&").rstrip(">"))


def channel_id_from_mention(pre_clean_data: str) -> int:
    """Extracts the ID of a channel from a channel mention.
    Will also accept strings containing a channel ID, and will reject invalid integers with a ValueError.
    This does validate the ID further, e.g the size of the ID, or the existence of a channel with the ID.

    :param str pre_clean_data: A string containing either a channel mention or ID
    :return: The ID quoted in pre_clean_data
    :rtype: int
    :raise ValueError: When given an ID containing non-integer characters
    """
    return int(pre_clean_data.lstrip("<#").rstrip(">"))


def user_id_from_mention(pre_clean_data: str) -> int:
    """Extracts the ID of a user from a user mention.
    Will also accept strings containing a user ID, and will reject invalid integers with a ValueError.
    This does validate the ID further, e.g the size of the ID, or the existence of a user with the ID.
    Accepting ! characters also accounts for member mentions where the member has a nickname.

    :param str pre_clean_data: A string containing either a user mention or ID
    :return: The ID quoted in pre_clean_data
    :rtype: int
    :raise ValueError: When given an ID containing non-integer characters
    """
    return int(pre_clean_data.lstrip("<@!").rstrip(">"))


def get_whether_in_vm_parent(guild_id, channel_id):
    """
    Get if the given channel is a voicemaster parent channel.
    :param guild_id: The ID of the guild to check in.
    :param channel_id: The ID of the channel to check if it is a parent channel.
    :return: True if the given channel ID is for a parent channel, False otherwise.
    """
    in_parent = DBGatewayActions().get(VoicemasterMaster, guild_id=guild_id, channel_id=channel_id)
    return bool(in_parent)


def get_whether_in_vm_child(guild_id, channel_id):
    """
    Get if the given channel is a voicemaster child channel.
    :param guild_id: The ID of the guild to check in.
    :param channel_id: The ID of the channel to check if it is a child channel.
    :return: True if the given channel ID is for a child channel, False otherwise.
    """
    in_child = DBGatewayActions().get(VoicemasterSlave, guild_id=guild_id, channel_id=channel_id)
    return bool(in_child)
