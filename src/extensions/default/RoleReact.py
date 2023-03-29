import logging
from dataclasses import dataclass
from typing import Union

from discord import (Color, Embed, Guild, Interaction, Message, NotFound, PartialEmoji, Role)
from discord.app_commands import (Transform, autocomplete, command, default_permissions, describe, guild_only, rename)
from discord.ext.commands import Bot, GroupCog
from discord.ui import Select, View

from common.discord import (
    ColourTransformer,
    EmojiTransformer,
    RoleReactMenuTransformer,
    primary_key_from_object,
    respond_or_followup
)
from common.io import load_cog_toml
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
    if not view:
        return []

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
        elif idx == len(options) - 1:
            view.add_item(child_select)

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
        elif idx == len(options) - 1:
            embeds.append(embed_item)

    if menu_id:
        footer_text = f"Menu ID: {menu_id}"
    else:
        footer_text = COG_STRINGS["react_footer_no_id"]

    embeds[-1].set_footer(text=footer_text)

    return embeds


@default_permissions(administrator=True)
@guild_only()
class RoleReact(GroupCog, name=COG_STRINGS["react_group_name"]):

    def __init__(self, bot: Bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"{__name__} has been added as a Cog")

    @GroupCog.listener()
    async def on_interaction(self, interaction: Interaction):
        if not interaction.data or not interaction.data.get("custom_id"):
            return False

        if not interaction.data.get("custom_id").startswith(ROLE_REACT_INTERACTION_PREFIX):
            return False

        await interaction.response.defer()
        selected_role_ids = interaction.data.get("values")
        message_view = View.from_message(interaction.message)
        view_options = options_from_view(message_view, interaction.guild)
        unselected_roles = []
        selected_roles = []

        for option in view_options:
            if str(option.role.id) in selected_role_ids:
                selected_roles.append(option.role)
            else:
                unselected_roles.append(option.role)

        await interaction.user.remove_roles(*unselected_roles)
        await interaction.user.add_roles(*selected_roles)
        await respond_or_followup(COG_STRINGS["react_roles_updated"], interaction, ephemeral=True, delete_after=5)

    @command(name=COG_STRINGS["react_create_menu_name"], description=COG_STRINGS["react_create_menu_description"])
    @describe(embed_color=COG_STRINGS["react_create_menu_embed_color_describe"])
    @rename(embed_color=COG_STRINGS["react_create_menu_embed_color_rename"])
    @autocomplete(embed_color=ColourTransformer.autocomplete)
    async def create_menu(self, interaction: Interaction, color: Transform[Color, ColourTransformer] = Color.random()):
        await interaction.response.defer()

        message = await interaction.channel.send("​")
        db_primary_key = primary_key_from_object(message)
        db_item = RoleReactMenus(primary_key=db_primary_key, guild_id=interaction.guild.id, message_id=message.id)
        DBSession.create(db_item)

        message_embeds = embeds_from_options([], menu_id=message.id, color=color)
        await message.edit(embeds=message_embeds)

        await respond_or_followup(COG_STRINGS["react_create_menu_success"], ephemeral=self.bot.only_ephemeral)

    @command(name=COG_STRINGS["react_delete_menu_name"], description=COG_STRINGS["react_delete_menu_description"])
    @describe(message_id=COG_STRINGS["react_delete_menu_message_id_describe"])
    @rename(message_id=COG_STRINGS["react_delete_menu_message_id_rename"])
    @autocomplete(message_id=RoleReactMenuTransformer.autocomplete)
    async def delete_menu(self, interaction: Interaction, menu_id: str):
        await interaction.response.defer()

        message = await validate_message_id(interaction, menu_id)
        if not message:
            return

        db_item = DBSession.get(RoleReactMenus, guild_id=interaction.guild.id, message_id=message.id)
        if db_item:
            DBSession.delete(db_item)

        await message.delete()
        await respond_or_followup(
            COG_STRINGS["react_delete_menu_success"].format(menu_id=message.id),
            interaction,
            ephemeral=True
        )

    @command(name=COG_STRINGS["react_add_item_name"], description=COG_STRINGS["react_add_item_description"])
    @describe(
        message_id=COG_STRINGS["react_add_item_message_id_describe"],
        role=COG_STRINGS["react_add_item_role_describe"],
        emoji=COG_STRINGS["react_add_item_emoji_describe"],
        description=COG_STRINGS["react_add_item_description_describe"]
    )
    @rename(
        message_id=COG_STRINGS["react_add_item_message_id_rename"],
        role=COG_STRINGS["react_add_item_role_rename"],
        emoji=COG_STRINGS["react_add_item_emoji_rename"],
        description=COG_STRINGS["react_add_item_description_rename"]
    )
    @autocomplete(message_id=RoleReactMenuTransformer.autocomplete)
    async def add_role(
        self,
        interaction: Interaction,
        menu_id: str,
        role: Role,
        emoji: Transform[PartialEmoji,
                         EmojiTransformer] = None,
        description: str = None
    ):
        await interaction.response.defer()

        message = await validate_message_id(interaction, menu_id)
        if not message:
            return

        embed_color = message.embeds[0].color
        message_view = View.from_message(message)
        current_options = options_from_view(message_view, interaction.guild)
        current_options.append(RoleOption(role_id=role.id, role=role, emoji=emoji, description=description))

        updated_view = view_from_options(current_options)
        updated_embeds = embeds_from_options(current_options, menu_id, embed_color)

        await message.edit(view=updated_view, embeds=updated_embeds)
        await respond_or_followup(
            COG_STRINGS["react_add_item_success"].format(role=role.name,
                                                         menu_id=menu_id),
            interaction,
            ephemeral=True
        )

    async def remove_item(self, interaction: Interaction, menu_id: str, role_id: str):
        await interaction.response.defer()

        message = await validate_message_id(interaction, menu_id)
        if not message:
            return

        embed_color = message.embeds[0].color
        message_view = View.from_message(message)
        current_options = options_from_view(message_view, interaction.guild)

        if not current_options:
            await respond_or_followup(COG_STRINGS["react_remove_item_warn_no_items"], interaction, ephemeral=True)
            return

        option_to_remove = None
        for option in current_options:
            if str(option.role_id) == role_id:
                option_to_remove = option
                break

        if option_to_remove:
            current_options.remove(option_to_remove)

        updated_view = view_from_options(current_options)
        updated_embeds = embeds_from_options(current_options, menu_id, embed_color)

        await message.edit(view=updated_view, embeds=updated_embeds)
        await respond_or_followup(
            COG_STRINGS["react_remove_item_success"].format(role_id=role_id,
                                                            menu_id=menu_id),
            interaction,
            ephemeral=True
        )