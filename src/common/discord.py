from discord.app_commands import Transformer
from discord import Role, Interaction, Guild
from discord.abc import GuildChannel
from typing import List, Union
import re

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
