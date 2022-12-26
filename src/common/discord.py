from discord.app_commands import Transformer
from discord import Role, Interaction, Guild
from typing import List
import re

ROLE_REGEX = re.compile(r"(?<=\<\@\&)(\d)+(?=\>)")


def raw_role_string_to_id(role_str: str):
    if not role_str.startswith("<@&") or not role_str.endswith(">"):
        raise ValueError(f"The given string of `{role_str}` is not a valid raw role string!")

    role_id: str = role_str[role_str.index("<@&") + 3:role_str.index(">")]

    if not role_id.isdigit():
        raise ValueError(f"Unable to find a valid Role ID in raw role string `{role_str}`")

    return int(role_id)


async def get_role(guild: Guild, role_id: int):
    role = guild.get_role(role_id)
    if role is None:
        roles = await guild.fetch_roles()
        return list(filter(lambda x: x.id == role_id, roles))[0]

    return role


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
