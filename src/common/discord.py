import re
from datetime import datetime
from typing import List, Union

from discord import Colour, Guild, Interaction, Role, ScheduledEvent, Message, PartialEmoji
from discord.abc import GuildChannel
from discord.app_commands import Choice, Transformer
from discord.ui import View

from database.models import UserRolesConfig, RoleReactMenus
from database.gateway import DBSession

ROLE_REGEX = re.compile(r"(?<=\<\@\&)(\d)+(?=\>)")


async def respond_or_followup(
    message: str,
    interaction: Interaction,
    ephemeral: bool = False,
    delete_after: float = 10,
    **kwargs
):
    if interaction.response.is_done():
        message = await interaction.followup.send(content=message, ephemeral=ephemeral, **kwargs)
        if delete_after:
            await message.delete(delay=delete_after)
        return False
    else:
        await interaction.response.send_message(message, ephemeral=ephemeral, delete_after=delete_after, **kwargs)
        return True


def make_colour_list():
    all_vars = dir(Colour)
    colour_vars = dir(Colour)

    def valid_key(string: str):
        starts_with = ["_", "from_", "to_"]
        ends_with = ["_gray"]
        start_end_with = [{"start": "__", "end": "__"}]

        for req in start_end_with:
            if string.startswith(req["start"]) and string.endswith(req["end"]):
                return False

        for req in starts_with:
            if string.startswith(req):
                return False

        for req in ends_with:
            if string.endswith(req):
                return False

        return True

    for key in all_vars:
        if not valid_key(key) or key in ["value", "r", "g", "b"]:
            colour_vars.remove(key)
    return colour_vars


VALID_COLOUR_NAMES = make_colour_list()


def raw_role_string_to_id(role_str: str):
    role_found = re.search(ROLE_REGEX, role_str)
    if not role_found:
        return 0

    try:
        return int(role_found.group())
    except ValueError:
        return 0


async def get_role(guild: Guild, role_id: int):
    role = guild.get_role(role_id)
    if role is None:
        roles = await guild.fetch_roles()
        return list(filter(lambda x: x.id == role_id, roles))[0]

    return role


def primary_key_from_object(object: Union[Role, GuildChannel, ScheduledEvent, Message]):
    return int(f"{object.guild.id % 1000}{object.id % 1000}")


def check_interaction_prefix(interaction: Interaction, prefix: str):
    if not interaction.data or not interaction.data.get("custom_id"):
        return False

    if not interaction.data.get("custom_id").startswith(prefix):
        return False

    return True


class RoleListTransformer(Transformer):
    """The transformer class to transform a list of Roles given in a ccommand string to a list of discord.Role objects.

    Returns:
        List[Role]: A list of Role objects that were contained in the string that were also valid roles.
    """

    async def transform(self, interaction: Interaction, roles: str) -> List[Role]:
        roles_found = re.finditer(ROLE_REGEX, roles)
        parsed_roles = []
        for _, role_match in enumerate(roles_found):
            role_id = role_match.group()
            try:
                role = await get_role(interaction.guild, int(role_id))
                parsed_roles.append(role)
            except ValueError:
                continue

        return parsed_roles


class DatetimeTransformer(Transformer):
    """The transformer class to convert a datetime string into a datetime object.

    Raises:
        ValueError: When the given string does not fit a datetime format.

    Returns:
        datetime: The given string as a datetime object.
    """
    DATE_REGEX = re.compile(r"(?P<Day>\d{2})\/(?P<Month>\d{2})\/(?P<Year>\d{4}|\d{2})")
    TIME_REGEX = re.compile(
        r"(?P<Hour>\d{2}):"
        r"(?P<Minute>\d{2})"
        r"(:(?P<Second>\d{2}))?"
        r"(?P<AMPMGap>\s)?(?P<AMPM>\w{2})?"
    )

    async def transform(self, interaction: Interaction, date_string: str) -> datetime:
        date_matches = re.search(self.DATE_REGEX, date_string)

        if date_matches is None or not all(date_matches.groupdict().values()):
            raise ValueError("The given string did not contain a valid date component.")

        date_values = date_matches.groupdict()
        day_format = "%-d" if len(date_values.get("Day")) == 1 else "%d"
        month_format = "%-m" if len(date_values.get("Month")) == 1 else "%m"
        year_format = "%y" if len(date_values.get("Year")) == 2 else "%Y"

        date_format = f"{day_format}/{month_format}/{year_format}"

        time_matches = re.search(self.TIME_REGEX, date_string)

        if time_matches is None or not any(date_matches.groupdict().values()):
            raise ValueError("The given string did not contain a valid time component.")

        time_values = time_matches.groupdict()

        is_24_hr = time_values.get("AMPM") is None

        if is_24_hr:
            hour_format = "%-H" if len(time_values.get("Hour")) == 1 else "%H"
        else:
            hour_format = "%-I" if len(time_values.get("Hour")) == 1 else "%I"

        minute_format = "%-M" if len(time_values.get("Minute")) == 1 else "%M"
        if time_values.get("Second"):
            second_format = "%-S" if len(time_values.get("Second")) == 1 else "%S"
        else:
            second_format = ""

        gap = " " if time_values.get("AMPMGap") else ""

        time_format = (
            f"{hour_format}:"  # Hours
            f"{minute_format}"  # Minutes
            f"{':'+second_format if second_format else ''}"  # Seconds
            f"{gap}{''if is_24_hr else '%p'}"  # 12/24hr clock
        )

        full_format = f"{date_format} {time_format}"

        return datetime.strptime(date_string, full_format)


class ColourTransformer(Transformer):
    """The transformer that provides named colour autocompletion and converts the corresponding Color object.
    Also provides the ability to convert a hex colour string to a Color object from the given string.

    Returns:
        Color: The Color object of the colour string or hex string given.
    """

    async def autocomplete(self, interaction: Interaction, current_str: str) -> List[Choice[str]]:
        return [
            Choice(name=colour.replace("_",
                                       " ").capitalize(),
                   value=colour) for colour in VALID_COLOUR_NAMES if current_str.lower() in colour.lower()
        ][:25]

    async def transform(self, interaction: Interaction, input_string: str) -> Colour:
        if input_string.startswith("#"):
            try:
                return Colour.from_str(input_string)
            except ValueError:
                return Colour.default()
        elif input_string in VALID_COLOUR_NAMES:
            return getattr(Colour, input_string)()
        else:
            try:
                manual_name = input_string.replace(" ", "_").strip().lower()
                colour = getattr(Colour, manual_name)
                return colour()
            except AttributeError:
                return Colour.default()


class EmojiTransformer(Transformer):

    async def transform(self, interaction: Interaction, value: str) -> PartialEmoji:
        return PartialEmoji.from_str(value)


def get_events(guild: Guild, event_dict: dict, value: str) -> List[Choice[str]]:
    filtered_events = []
    guild_events = [event_dict.get(x) for x in event_dict if event_dict.get(x).guild_id == guild.id]
    if value.isdigit():
        filtered_events = [x for x in guild_events if value in str(x.event_id)]
    else:
        filtered_events = [x for x in guild_events if value.lower() in x.name.lower()]

    choices = [Choice(name=f"{x.name} ({x.event_id})", value=str(x.event_id)) for x in filtered_events][:25]
    return choices


class EventTransformer(Transformer):
    """The transformer that provides autocompletion for exisiting events. Either using a partial name or a partial ID value.

    Returns:
        List[Choice[str]]: The list of choices that map a user readable string of available events to their ID as the value.
    """

    async def autocomplete(self, interaction: Interaction, value: str) -> List[Choice[str]]:
        return get_events(interaction.guild, self.events | self.archived_events, value)


class ActiveEventTransformer(Transformer):
    """The event trasnformer that only provides autocompletion for events that are not archived
    (ie. scheduled or active events).

    Returns:
        List[Choice[str]]: The list of choices that map a user readable string of non-archived events to their ID as the value.
    """

    async def autocomplete(self, interaction: Interaction, value: str) -> List[Choice[str]]:
        return get_events(interaction.guild, self.events, value)


class ArchivedEventTransformer(Transformer):
    """The event trasnformer that only provides autocompletion for events that are archived.

    Returns:
        List[Choice[str]]: The list of choices that map a user readable string of archived events to their ID as the value.
    """

    async def autocomplete(self, interaction: Interaction, value: str) -> List[Choice[str]]:
        return get_events(interaction.guild, self.archived_events, value)


def get_roles_from_view(view: View, guild: Guild) -> list[Role]:
    """Get a list of roles from a View for a RoleReact message.

    Args:
        view (View): The view containing the Select items with role options.
        guild (Guild): The guild in which the view/message exist.

    Returns:
        list[Role]: A list of roles that are the options in the select menu(s).
    """
    if not view:
        return []

    roles = []
    guild_roles = {str(x.id): x for x in guild.roles}
    for child in view.children:
        for option in child.options:
            roles.append(guild_roles.get(option.value))
    return roles


def get_menu_id_from_args(interaction: Interaction) -> int:
    """Get the given menu ID from the already supplied arguments of an interaction.

    Args:
        interaction (Interaction): The interaction containing the already given menu ID

    Returns:
        int: The menu ID of the menu given.
    """
    interaction_options = {"options": []}
    for item in interaction.data.get("options"):
        if item.get("type") == 1:
            interaction_options = item
            break

    for argument in interaction_options.get("options"):
        if argument.get("name") == "menu-id":
            return argument.get("value")
    return 0


class RoleReactMenuTransformer(Transformer):
    """The autocomplete transformer to provide a list of RoleReact menu IDs for a given guild.

    Returns:
        List[Choice[str]]: A list of exisitng menu IDs in a guild.
    """

    async def autocomplete(self, interaction: Interaction, value: Union[int, float, str]) -> List[Choice[str]]:
        guild_role_menus = DBSession.list(RoleReactMenus, guild_id=interaction.guild.id)
        if value:
            choices = [
                Choice(name=f"Role menu ID: {x.message_id}",
                       value=str(x.message_id)) for x in guild_role_menus if value in str(x.message_id)
            ]
        else:
            choices = [Choice(name=f"Role menu ID: {x.message_id}", value=str(x.message_id)) for x in guild_role_menus]
        return choices[:25]


class RoleReactRoleTransformer(Transformer):
    """The autocomplete transformer to provide a list of Roles that are in the already provided RoleReact menu.

    Returns:
        List[Choice[str]]: A list of Roles for the RoleReact menu currently chosen.
    """

    async def autocomplete(self, interaction: Interaction, value: str) -> List[Choice[str]]:
        menu_id = get_menu_id_from_args(interaction)
        if not DBSession.get(RoleReactMenus, guild_id=interaction.guild.id, message_id=menu_id):
            return []

        message = await interaction.channel.fetch_message(menu_id)
        view = View.from_message(message)
        menu_roles = get_roles_from_view(view, interaction.guild)
        if value:
            choices = [
                Choice(name=f"{'' if x.name.startswith('@') else '@'}{x.name}",
                       value=str(x.id)) for x in menu_roles if value.replace("@",
                                                                             "") in x.name
            ]
        else:
            choices = [Choice(name=f"{'' if x.name.startswith('@') else '@'}{x.name}", value=str(x.id)) for x in menu_roles]

        return choices[:25]


class TwitterWebhookIDTransformer(Transformer):

    async def autocomplete(self, interaction: Interaction, value: Union[int, str]) -> List[Choice[str]]:
        guild_webhooks = self.webhooks.get(interaction.guild.id)
        if value:
            choices = [
                Choice(name=f"{guild_webhooks.get(x).name} ({x})",
                       value=str(x)) for x in guild_webhooks if value.lower() in guild_webhooks.get(x).name.lower()
            ]
        else:
            choices = [Choice(name=f"{guild_webhooks.get(x).name} ({x})", value=str(x)) for x in guild_webhooks]

        return choices[:25]


class UserRolesConfigTransformer(Transformer):

    async def autocomplete(self, interaction: Interaction, value: str) -> List[Choice[str]]:
        attributes = [x for x in UserRolesConfig.__dict__.keys() if not x.startswith("_") and "guild" not in x.lower()]
        choices = [
            Choice(name=" ".join(j.capitalize() for j in x.split("_")),
                   value=x) for x in attributes if value.lower() in x.lower()
        ]
        return choices[:25]
