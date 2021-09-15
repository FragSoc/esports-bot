from typing import Dict, List


def get_latest(all_menus):
    """
    Get the latest created menu from the give menus.
    :param all_menus: All menus to check through.
    :return: The ReactableMeu that was created last.
    """
    menus = list(all_menus.values())
    latest_menu = sorted(menus, key=lambda x: x.message.created_at)
    if latest_menu:
        return latest_menu[-1]
    return None


def get_option(message_line: str) -> Dict[str, str]:
    """
    Get a menu option from a string.
    :param message_line: A single line in a message, or just a string.
    :return: A dictionary of Emoji : descriptor of a ReactionMenu option.
    """
    split_message = message_line.split(" ")
    emoji_str = split_message[0]
    descriptor = " ".join(split_message[1:])
    return {emoji_str: descriptor}


def get_all_options(message: List[str]) -> Dict[str, str]:
    """
    Get all the ReactionMenu options from a multiline message.
    :param message: The list of strings representing the lines in a message.
    :return: A dictionary of Emoji : descriptor of all the ReactionMenu options.
    """
    options = {}
    for line in message:
        options = {**options, **get_option(line)}
    return options


def clean_mentioned_role(role: str) -> int:
    """
    Get the ID of a role from a role mention string.
    :param role: The role mention string.
    :return: An integer of the role ID or 0 if the ID given is not an int.
    """
    role = str(role)
    role = role.strip()
    try:
        return int(role.lstrip("<@&").rstrip(">"))
    except ValueError:
        return 0


def get_role_from_id(guild, role_id):
    """
    Get a Role in a guild from its an ID.
    :param guild: The guild to get the role from.
    :param role_id: The ID of the role to get.
    :return: A discord Role object if the role exists, else None.
    """
    for role in guild.roles:
        if role.id == role_id:
            return role
    return None


def get_menu(all_menus, menu_id):
    """
    Get a menu from the given `all_menus` given a menu ID.
    :param all_menus: All the menus to search in.
    :param menu_id: THe ID of the menu to get.
    :return: A ReactionMenu if there is a menu with that ID, else None
    """
    menu = None
    if menu_id is None:
        menu = get_latest(all_menus)
    elif menu_id.isdigit():
        menu = all_menus.get(int(menu_id), None)
    return menu
