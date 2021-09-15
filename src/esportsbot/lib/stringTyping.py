import re

MENTION_REGEX = re.compile(r"^<@!?[0-9]+>$")
ROLE_REGEX = re.compile(r"^<@&[0-9]+>$")
CHANNEL_REGEX = re.compile(r"^<#[0-9]+>$")
"""
The lib package was partially copied over from the BASED template project: https://github.com/Trimatix/BASED
It is modified and not actively synced with BASED, so will very likely be out of date.

.. codeauthor:: Trimatix
"""


def str_is_int(x) -> bool:
    """Decide whether or not something is either an integer, or is castable to integer.

    :param x: The object to type-check
    :return: True if x is an integer or if x can be casted to integer. False otherwise
    :rtype: bool
    """

    try:
        int(x)
    except TypeError:
        return False
    except ValueError:
        return False
    return True


def str_is_role_mention(mention: str) -> bool:
    """Decide whether the given string is a discord role mention, being <@&ROLEID> where ROLEID is an integer discord role id.

    :param str mention: The string to check
    :return: True if mention matches the formatting of a discord role mention, False otherwise
    :rtype: bool
    """
    return ROLE_REGEX.match(mention) is not None


def str_is_user_mention(mention: str) -> bool:
    """Decide whether the given string is a discord user mention, being <@USERID> where USERID is an integer discord user id.

    :param str mention: The string to check
    :return: True if mention matches the formatting of a discord user mention, False otherwise
    :rtype: bool
    """
    return MENTION_REGEX.match(mention) is not None


def str_is_channel_mention(mention: str) -> bool:
    """
    Decide whether the given string is a discord channel mention, being <@CHANNELID> where CHANNELID is an integer discord
    channel id.

    :param str mention: The string to check
    :return: True if mention matches the formatting of a discord channel mention, False otherwise
    :rtype: bool
    """
    return CHANNEL_REGEX.match(mention) is not None
