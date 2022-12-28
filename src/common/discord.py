from discord.app_commands import Transformer
from discord import Role, Interaction, Guild
from discord.abc import GuildChannel
from typing import List, Union
import re
from datetime import datetime

ROLE_REGEX = re.compile(r"(?<=\<\@\&)(\d)+(?=\>)")


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


def primary_key_from_object(object: Union[Role, GuildChannel]):
    return int(f"{object.guild.id % 1000}{object.id % 1000}")


class RoleListTransformer(Transformer):

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
