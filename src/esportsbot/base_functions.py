from .db_gateway import db_gateway


async def send_to_log_channel(self, guild_id, msg):
    db_logging_call = db_gateway().get(
        'guild_info', params={'guild_id': guild_id})
    if db_logging_call and db_logging_call[0]['log_channel_id']:
        await self.bot.get_channel(db_logging_call[0]['log_channel_id']).send(msg)


def role_id_from_mention(pre_clean_data: str) -> int:
    """Extracts the ID of a role from a role mention.
    Will also accept strings containing a role ID, and will reject invalid integers with a ValueError.
    This does validate the ID further, e.g the size of the ID, or the existence of a role with the ID.

    :param str pre_clean_data: A string containing either a role mention or ID
    :return: The ID quoted in pre_clean_data
    :rtype: int
    :raise ValueError: When given an ID containing non-integer characters
    """
    return int(pre_clean_data.lstrip("<&").rstrip(">"))


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


def get_whether_in_vm_master(guild_id, channel_id):
    in_master = db_gateway().get('voicemaster_master', params={
        'guild_id': guild_id, 'channel_id': channel_id})
    return bool(in_master)


def get_whether_in_vm_slave(guild_id, channel_id):
    in_slave = db_gateway().get('voicemaster_slave', params={
        'guild_id': guild_id, 'channel_id': channel_id})
    return bool(in_slave)
