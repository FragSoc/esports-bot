import logging

from typing import Union

from discord import Color, Embed, Interaction, Message, Role, PartialEmoji, NotFound
from discord.app_commands import (Transform, autocomplete, command, default_permissions, describe, guild_only, rename)
from discord.ext.commands import Bot, GroupCog
from discord.ui import View, Select

from common.discord import ColourTransformer, get_roles_from_select, primary_key_from_object, RoleReactMenuTransformer, EmojiTransformer, respond_or_followup, RoleReactRoleTransformer
from common.io import load_cog_toml
from database.gateway import DBSession
from database.models import RoleReactMenus

COG_STRINGS = load_cog_toml(__name__)
ROLE_REACT_INTERACTION_PREFIX = f"{__name__}.interaction"
EMPTY_ROLE_MENU = COG_STRINGS["react_empty_menu"]


async def validate_message_id(interaction: Interaction, message_id: int) -> Union[None, Message]:
    try:
        message = await interaction.channel.fetch_message(message_id)
    except NotFound:
        await respond_or_followup(f"Unable to find message with ID `{message_id}`", interaction, ephemeral=True)
        return None

    valid_message = DBSession.get(RoleReactMenus, guild_id=message.guild.id, message_id=message.id)
    if not valid_message:
        await respond_or_followup(f"The given ID of `{message_id}` is not a role react menu", interaction, ephemeral=True)
        return None

    return message


def no_roles_embed(title: str = "Role Menu", embed_color: Color = Color.default(), message_id: int = None) -> Embed:
    description = "" if not message_id else EMPTY_ROLE_MENU.format(message_id=message_id)
    embed = Embed(title=title, description=description, color=embed_color)
    if message_id:
        embed.set_footer(text=f"Menu ID: {message_id}")
    else:
        embed.set_footer(text="Not yet configured...")

    return embed


def exclude_roles_from_select(role_exclude_list: list[str], menu: Select) -> Select:
    exisiting_options = menu.options
    menu.options = []

    for option in exisiting_options:
        if option.value not in role_exclude_list:
            menu.add_option(label=option.label, value=option.value, description=option.description, emoji=option.emoji)

    return menu


@default_permissions(administrator=True)
@guild_only()
class RoleReact(GroupCog, name=COG_STRINGS["react_group_name"]):

    def __init__(self, bot: Bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"{__name__} has been added as a Cog")

    @GroupCog.listener()
    async def on_interaction(self, interaction: Interaction):
        pass

    @command(name=COG_STRINGS["react_create_menu_name"], description=COG_STRINGS["react_create_menu_description"])
    @describe(embed_color=COG_STRINGS["react_create_menu_embed_color_describe"])
    @rename(embed_color=COG_STRINGS["react_create_menu_embed_color_rename"])
    @autocomplete(embed_color=ColourTransformer.autocomplete)
    async def create_menu(
        self,
        interaction: Interaction,
        embed_color: Transform[Color,
                               ColourTransformer] = Color.random(),
    ):
        embed = no_roles_embed(embed_color=embed_color)

        message: Message = await interaction.channel.send(embed=embed)
        p_key = primary_key_from_object(message)
        db_item = RoleReactMenus(primary_key=p_key, guild_id=interaction.guild.id, message_id=message.id)
        DBSession.create(db_item)

        embed = no_roles_embed(embed_color=embed_color, message_id=message.id)
        await message.edit(embed=embed)
        await interaction.response.send_message("Menu created!", ephemeral=True)

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
    async def add_item(
        self,
        interaction: Interaction,
        message_id: str,
        role: Role,
        emoji: Transform[PartialEmoji,
                         EmojiTransformer] = None,
        description: str = None
    ):
        await interaction.response.defer(ephemeral=True)
        message = await validate_message_id(interaction, message_id)
        if not message:
            return
        message_embed = message.embeds[0]
        no_roles = not message.components

        if no_roles:
            message_embed.description = "**__Active Roles__**\n"
            view = View(timeout=None)
            menu = Select(custom_id=ROLE_REACT_INTERACTION_PREFIX, min_values=0, max_values=1)
        else:
            view = View.from_message(message, timeout=None)
            menu = view.children[0]
            view = view.clear_items()

        menu.max_values = len(menu.options) + 1
        menu.add_option(label=f"@{role.name}", value=str(role.id), description=description, emoji=emoji)
        view.add_item(menu)
        message_embed.description += f"\n{emoji if emoji else ''} {role.mention} - {description if description else ''}"
        await message.edit(embed=message_embed, view=view)
        await respond_or_followup("Role added!", interaction, ephemeral=True)

    @command(name=COG_STRINGS["react_remove_item_name"], description=COG_STRINGS["react_remove_item_description"])
    @describe(
        message_id=COG_STRINGS["react_remove_item_message_id_describe"],
        role_id=COG_STRINGS["react_remove_item_role_id_describe"]
    )
    @rename(
        message_id=COG_STRINGS["react_remove_item_message_id_rename"],
        role_id=COG_STRINGS["react_remove_item_role_id_rename"]
    )
    @autocomplete(message_id=RoleReactMenuTransformer.autocomplete, role_id=RoleReactRoleTransformer.autocomplete)
    async def remove_item(self, interaction: Interaction, message_id: str, role_id: str):
        await interaction.response.defer(ephemeral=True)
        message = await validate_message_id(interaction, message_id)
        if not message:
            return

        message_embed = message.embeds[0]
        no_roles = not message.components
        if no_roles:
            await respond_or_followup("No roles to remove!", interaction, ephemeral=True)
            return

        view = View.from_message(message, timeout=None)
        menu = view.children[0]
        view = view.clear_items()
        menu = exclude_roles_from_select(role_id, menu)
        if not menu.options:
            message_embed = no_roles_embed(embed_color=message_embed.color, message_id=message_id)
        else:
            new_description = "**__Active Roles__**\n"
            for option in menu.options:
                new_description += f"\n{option.emoji if option.emoji else ''} <&@{option.value}> - {option.description if option.description else ''}"
            view.add_item(menu)
            message_embed.description = new_description

        await message.edit(embed=message_embed, view=view)
        await respond_or_followup("Successfully removed role!", interaction, ephemeral=True)

    @command(name=COG_STRINGS["react_delete_menu_name"], description=COG_STRINGS["react_delete_menu_description"])
    @describe(message_id=COG_STRINGS["react_delete_menu_message_id_describe"])
    @rename(message_id=COG_STRINGS["react_delete_menu_message_id_rename"])
    @autocomplete(message_id=RoleReactMenuTransformer.autocomplete)
    async def delete_menu(self, interaction: Interaction, message_id: str):
        await interaction.response.defer(ephemeral=True)
        message = await validate_message_id(interaction, message_id)
        if not message:
            return

        db_item = DBSession.get(RoleReactMenus, guild_id=interaction.guild.id, message_id=message.id)
        DBSession.delete(db_item)
        await message.delete()
        await respond_or_followup(f"Role menu with id `{message.id}` deleted!", interaction, ephemeral=True)


async def setup(bot: Bot):
    await bot.add_cog(RoleReact(bot))
