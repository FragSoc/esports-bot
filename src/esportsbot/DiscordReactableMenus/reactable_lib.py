from typing import Dict, List


def get_latest(all_menus):
    menus = list(all_menus.values())
    latest_menu = sorted(menus, key=lambda x: x.message.created_at)
    if latest_menu:
        return latest_menu[-1]
    return None


def get_option(message_line: str) -> Dict[str, str]:
    split_message = message_line.split(" ")
    emoji_str = split_message[0]
    descriptor = " ".join(split_message[1:])
    return {emoji_str: descriptor}


def get_all_options(message: List[str]) -> Dict[str, str]:
    options = {}
    for line in message:
        options = {**options, **get_option(line)}
    return options


def clean_mentioned_role(role: str) -> int:
    role = str(role)
    role = role.strip()
    try:
        return int(role.lstrip("<@&").rstrip(">"))
    except ValueError:
        return 0


def get_role_from_id(guild, role_id):
    for role in guild.roles:
        if role.id == role_id:
            return role
    return None


def get_menu(all_menus, menu_id):
    menu = None
    if menu_id is None:
        menu = get_latest(all_menus)
    elif menu_id.isdigit():
        menu = all_menus.get(int(menu_id), None)
    return menu
