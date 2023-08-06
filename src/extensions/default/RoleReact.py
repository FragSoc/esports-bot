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
    RoleReactRoleTransformer,
    respond_or_followup
)
from common.io import load_cog_toml
from database.gateway import DBSession
from database.models import RoleReactMenus

COG_STRINGS = load_cog_toml(__name__)
ROLE_REACT_INTERACTION_PREFIX = f"{__name__}."
MAX_VIEW_ITEM_COUNT = 25


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
    """Check if a given message ID is a RoleReact menu message. If it is, return the message object
    for the given message ID.

    Args:
        interaction (Interaction): The interaction. Used to obtain the channel to then fetch the message.
        message_id (int): The ID of the message to check.

    Returns:
        Union[None, Message]: The message of the given ID if it is a RoleReact menu message. None otherwise.
    """
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
    """Generate a list of RoleOption from a discord View containing select menu(s).

    Args:
        view (View): The view to obtain the available options from.
        guild (Guild, optional): The guild in which the view/message exists in. Defaults to None.

    Returns:
        list[RoleOption]: The list of RoleOption that correspond to the available options in the given View.
    """
    if not view:
        return []

    guild_roles = {str(x.id): x for x in guild.roles}
    options = []
    for child in view.children:
        for option in child.options:
            if guild:
                option_role = guild_roles.get(option.value)
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
    """Generate a view with one or many Select menus given a list of RoleOption.

    Args:
        options (list[RoleOption]): The list of RoleOption to turn into Select menu(s)

    Raises:
        ValueError: If the number of options exceeds the number of items allowed in a single view.

    Returns:
        View: The view containing the select menu(s) with the RoleOptions as the selectable options.
    """
    if len(options) > MAX_VIEW_ITEM_COUNT * MAX_VIEW_ITEM_COUNT:
        raise ValueError(
            f"Too many options supplied to a single view. "
            f"Option count exceeds {MAX_VIEW_ITEM_COUNT} * {MAX_VIEW_ITEM_COUNT} ({len(options)})"
        )

    view = View(timeout=None)
    child_select = Select(custom_id=f"{ROLE_REACT_INTERACTION_PREFIX}{0}", min_values=0, max_values=0)
    for idx, option in enumerate(options):
        child_select.add_option(
            label=f"@{option.role.name}",
            value=str(option.role_id),
            description=option.description,
            emoji=option.emoji
        )
        child_select.max_values += 1

        if (idx + 1) % MAX_VIEW_ITEM_COUNT == 0:
            view.add_item(child_select)
            child_select = Select(
                custom_id=f"{ROLE_REACT_INTERACTION_PREFIX}{(idx+1)//MAX_VIEW_ITEM_COUNT}",
                min_values=0,
                max_values=0
            )
        elif idx == len(options) - 1:
            view.add_item(child_select)

    return view


def no_options_embed(menu_id: int = None, color: Color = Color.random()) -> Embed:
    """Create an embed for which there are no selectable roles currently available.

    Args:
        menu_id (int, optional): The ID of the menu. Defaults to None.
        color (Color, optional): The color of the embed. Defaults to Color.random().

    Returns:
        Embed: The embed generated with placeholder text.
    """
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
    """Create an embed or many given a list of RoleOption. If there are too many roles for a single embed, multiple
    embeds will be created to contain all roles.

    Args:
        options (list[RoleOption]): The options available that are selectable in the eventual message's View.
        menu_id (int, optional): The ID of the message in which the embed will be sent. Defaults to None.
        color (Color, optional): The color of the embed. Defaults to Color.random().

    Raises:
        ValueError: If there are too many options for the View, the embed would be invalid and thus raises a ValueError.

    Returns:
        list[Embed]: The embeds that contain the selectable options.
    """
    if len(options) > MAX_VIEW_ITEM_COUNT * MAX_VIEW_ITEM_COUNT:
        raise ValueError(
            f"Too many options supplied to a single message. "
            f"Option count exceeds {MAX_VIEW_ITEM_COUNT} * {MAX_VIEW_ITEM_COUNT} ({len(options)})"
        )

    if not options:
        return [no_options_embed(menu_id=menu_id, color=color)]

    embeds = []
    embed_item = Embed(title=COG_STRINGS["react_embed_title"], description="**__Active Roles__**", color=color)

    for idx, option in enumerate(options):
        embed_item.description += f"\n{option!s}"
        if (idx + 1) % MAX_VIEW_ITEM_COUNT == 0:
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


def get_roles_from_select(view: View, guild: Guild, child_index: int) -> list[Role]:
    """Get a list of Roles from a specific Select menu in a View using the index value.

    Args:
        view (View): The view in which the Select menu exists.
        guild (Guild): The guild in which the View/message exists.
        child_index (int): The index of the menu in the View's children list.

    Returns:
        list[Role]: The list of roles that a Select menu has as options.
    """
    try:
        select_menu = view.children[child_index]
    except IndexError:
        return []

    select_roles = []
    guild_roles = {str(x.id): x for x in guild.roles}
    for option in select_menu.options:
        role = guild_roles.get(option.value)
        if role:
            select_roles.append(role)

    return select_roles


@default_permissions(administrator=True)
@guild_only()
class RoleReact(GroupCog, name=COG_STRINGS["react_group_name"]):

    def __init__(self, bot: Bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"{__name__} has been added as a Cog")

    @GroupCog.listener()
    async def on_interaction(self, interaction: Interaction):
        """Listens for when a user has (de)selected options in a RoleReact Select menu and
        handles the changes to the requested roles.

        Args:
            interaction (Interaction): The interaction performed.
        """
        if not interaction.data or not interaction.data.get("custom_id"):
            return False

        if not interaction.data.get("custom_id").startswith(ROLE_REACT_INTERACTION_PREFIX):
            return False

        await interaction.response.defer()
        selected_role_ids = interaction.data.get("values")
        message_view = View.from_message(interaction.message)
        select_index = interaction.data.get("custom_id").split(".")[-1]
        select_roles = get_roles_from_select(message_view, interaction.guild, int(select_index))
        unselected_roles = []
        selected_roles = []

        for role in select_roles:
            if str(role.id) in selected_role_ids:
                selected_roles.append(role)
            else:
                unselected_roles.append(role)

        await interaction.user.remove_roles(*unselected_roles)
        await interaction.user.add_roles(*selected_roles)
        await respond_or_followup(COG_STRINGS["react_roles_updated"], interaction, ephemeral=True, delete_after=5)

    @command(name=COG_STRINGS["react_create_menu_name"], description=COG_STRINGS["react_create_menu_description"])
    @describe(color=COG_STRINGS["react_create_menu_embed_color_describe"])
    @rename(color=COG_STRINGS["react_create_menu_embed_color_rename"])
    @autocomplete(color=ColourTransformer.autocomplete)
    async def create_menu(self, interaction: Interaction, color: Transform[Color, ColourTransformer] = Color.random()):
        """The command to create a new RoleReact menu/message. This command must be used to initalise a message as it
        serves to ensure that not any message can be turned into a RoleReact message.

        Args:
            interaction (Interaction): The interaction of the command.
            color (Transform[Color, ColourTransformer], optional): The color of the embed. Defaults to Color.random().
        """
        await interaction.response.defer()

        message = await interaction.channel.send("​")
        db_item = RoleReactMenus(guild_id=interaction.guild.id, message_id=message.id)
        DBSession.create(db_item)

        message_embeds = embeds_from_options([], menu_id=message.id, color=color)
        await message.edit(embeds=message_embeds)

        await respond_or_followup(COG_STRINGS["react_create_menu_success"], interaction, ephemeral=True)

    @command(name=COG_STRINGS["react_delete_menu_name"], description=COG_STRINGS["react_delete_menu_description"])
    @describe(menu_id=COG_STRINGS["react_delete_menu_message_id_describe"])
    @rename(menu_id=COG_STRINGS["react_delete_menu_message_id_rename"])
    @autocomplete(menu_id=RoleReactMenuTransformer.autocomplete)
    async def delete_menu(self, interaction: Interaction, menu_id: str):
        """Deletes a menu from the database as well as the actual message containing the RoleReact menu. If a message
        is manually deleted, it will still appear in the RoleReactMenuTransformer autocomplete options.

        Args:
            interaction (Interaction): The interaction of the command.
            menu_id (str): The ID of the menu to delete.
        """
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
        menu_id=COG_STRINGS["react_add_item_message_id_describe"],
        role=COG_STRINGS["react_add_item_role_describe"],
        emoji=COG_STRINGS["react_add_item_emoji_describe"],
        description=COG_STRINGS["react_add_item_description_describe"]
    )
    @rename(
        menu_id=COG_STRINGS["react_add_item_message_id_rename"],
        role=COG_STRINGS["react_add_item_role_rename"],
        emoji=COG_STRINGS["react_add_item_emoji_rename"],
        description=COG_STRINGS["react_add_item_description_rename"]
    )
    @autocomplete(menu_id=RoleReactMenuTransformer.autocomplete)
    async def add_role(
        self,
        interaction: Interaction,
        menu_id: str,
        role: Role,
        emoji: Transform[PartialEmoji,
                         EmojiTransformer] = None,
        description: str = None
    ):
        """The command to add a role to a specific RoleReact menu. The emoji or description do not need to be unique,
        and are purely visual aids for users to better understand a role.

        Args:
            interaction (Interaction): The interaction of the command.
            menu_id (str): The ID of the menu to add to.
            role (Role): The role to add to the menu.
            emoji (Transform[PartialEmoji, EmojiTransformer], optional): The emoji to associate with the role. Defaults to None.
            description (str, optional): The description of the role. Defaults to None.
        """
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

    @command(name=COG_STRINGS["react_remove_item_name"], description=COG_STRINGS["react_remove_item_description"])
    @describe(
        menu_id=COG_STRINGS["react_remove_item_message_id_describe"],
        role_id=COG_STRINGS["react_remove_item_role_id_describe"]
    )
    @rename(
        menu_id=COG_STRINGS["react_remove_item_message_id_rename"],
        role_id=COG_STRINGS["react_remove_item_role_id_rename"]
    )
    @autocomplete(menu_id=RoleReactMenuTransformer.autocomplete, role_id=RoleReactRoleTransformer.autocomplete)
    async def remove_item(self, interaction: Interaction, menu_id: str, role_id: str):
        """The command to remove a role from a given menu ID. The role ID can either be given manually or selected
        from the autocompleted list of roles in the menu selected as the first argument.

        Args:
            interaction (Interaction): The interaction of the command.
            menu_id (str): The ID of the menu to remove the role from.
            role_id (str): The ID of the role to remove from the menu.
        """
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


async def setup(bot: Bot):
    await bot.add_cog(RoleReact(bot))
