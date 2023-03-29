from dataclasses import dataclass
from typing import Union

from discord import Role, Embed, Color, Guild, Interaction, NotFound, Message
from discord.ui import View, Select

from common.io import load_cog_toml
from common.discord import respond_or_followup
from database.gateway import DBSession
from database.models import RoleReactMenus

COG_STRINGS = load_cog_toml(__name__)
ROLE_REACT_INTERACTION_PREFIX = f"{__name__}.interaction"


@dataclass
class RoleOption:
    role_id: int
    role: Role = None
    emoji: str = None
    description: str = None

    def __str__(self):
        out = ""
        if self.emoji:
            out += COG_STRINGS["react_role_emoji"].format(emoji=self.emoji)

        if self.role:
            out += self.role.mention
        else:
            out += f"<&@{self.role_id}>"

        if self.description:
            out += COG_STRINGS["react_role_description"].format(description=self.description)

        return out


async def validate_message_id(interaction: Interaction, message_id: int) -> Union[None, Message]:
    try:
        message = await interaction.channel.fetch_message(message_id)
    except NotFound:
        await respond_or_followup(
            COG_STRINGS["react_warn_message_not_found"].format(message_id=message_id),
            interaction,
            ephemeral=True
        )
        return None

    valid_message = DBSession.get(RoleReactMenus, guild_id=message.guild.id, message_id=message.id)
    if not valid_message:
        await respond_or_followup(
            COG_STRINGS["react_warn_invalid_message_found"].format(message_id=message_id),
            interaction,
            ephemeral=True
        )
        return None

    return message


def options_from_view(view: View, guild: Guild = None) -> list[RoleOption]:
    options = []
    for child in view.children:
        for option in child.options:
            if guild:
                option_role = guild.get_role(int(option.value))
            else:
                option_role = None
            options.append(
                RoleOption(role_id=option.value,
                           role=option_role,
                           emoji=option.emoji,
                           description=option.description)
            )
    return options


def view_from_options(options: list[RoleOption]) -> View:
    if len(options) > 25 * 25:
        raise ValueError(f"Too many options supplied to a single view. Option count exceeds 25 * 25 ({len(options)})")

    view = View(timeout=None)
    child_select = Select(custom_id=ROLE_REACT_INTERACTION_PREFIX, min_values=0, max_values=0)
    for idx, option in enumerate(options):
        child_select.add_option(
            label=f"@{option.role.name}",
            value=str(option.role_id),
            description=option.description,
            emoji=option.emoji
        )
        child_select.max_values += 1

        if idx % 25 == 0:
            view.add_item(child_select)
            child_select = Select(custom_id=ROLE_REACT_INTERACTION_PREFIX, min_values=0, max_values=0)

    return view


def no_options_embed(menu_id: int = None, color: Color = Color.random()) -> Embed:
    description = COG_STRINGS["react_footer_no_id"] if not menu_id else COG_STRINGS["react_empty_menu"].format(
        message_id=menu_id
    )
    embed = Embed(title=COG_STRINGS["react_embed_title"], description=description, color=color)
    if menu_id:
        embed.set_footer(text=f"Menu ID: {menu_id}")
    else:
        embed.set_footer(text=COG_STRINGS["react_footer_no_id"])

    return embed


def embeds_from_options(options: list[RoleOption], menu_id: int = None, color: Color = Color.random()) -> list[Embed]:
    if len(options) > 25 * 25:
        raise ValueError(f"Too many options supplied to a single message. Option count exceeds 25 * 25 ({len(options)})")

    if not options:
        return [no_options_embed(menu_id=menu_id, color=color)]

    embeds = []
    embed_item = Embed(title=COG_STRINGS["react_embed_title"], description="**__Active Roles__**", color=color)

    for idx, option in enumerate(options):
        embed_item.description += f"\n{option!s}"
        if idx % 25 == 0:
            embeds.append(embed_item)
            embed_item = Embed(title="​", description="", color=color)
    if menu_id:
        footer_text = f"Menu ID: {menu_id}"
    else:
        footer_text = COG_STRINGS["react_footer_no_id"]

    embeds[-1].set_footer(text=footer_text)

    return embeds
