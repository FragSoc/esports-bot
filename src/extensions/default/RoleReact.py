import logging

from discord import Color, Embed, Interaction, Message, Role, PartialEmoji
from discord.app_commands import (Transform, autocomplete, command, default_permissions, describe, guild_only, rename)
from discord.ext.commands import Bot, GroupCog
from discord.ui import View, Select

from common.discord import ColourTransformer, primary_key_from_object, RoleReactMenuTransformer, EmojiTransformer
from common.io import load_cog_toml
from database.gateway import DBSession
from database.models import RoleReactMenus

COG_STRINGS = load_cog_toml(__name__)
ROLE_REACT_INTERACTION_PREFIX = f"{__name__}.interaction"
EMPTY_ROLE_MENU = COG_STRINGS["react_empty_menu"]


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
        embed = Embed(
            title="Role Menu",
            description="",
        )
        embed.set_footer(text="Not yet configured...")

        message: Message = await interaction.channel.send(embed=embed)
        p_key = primary_key_from_object(message)
        db_item = RoleReactMenus(primary_key=p_key, guild_id=interaction.guild.id, message_id=message.id)
        DBSession.create(db_item)

        embed.description = EMPTY_ROLE_MENU.format(message_id=message.id)
        embed.set_footer(text=f"Role menu ID: {message.id}")
        embed.color = embed_color
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
        message = await interaction.channel.fetch_message(message_id)
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
        menu.add_option(label=role.name, value=role.id, description=description, emoji=emoji)
        view.add_item(menu)
        message_embed.description += f"\n{emoji} {role.mention} - {description}"
        await message.edit(embed=message_embed, view=view)
        await interaction.followup.send("Role added!")

    @command(name=COG_STRINGS["react_remove_item_name"], description=COG_STRINGS["react_remove_item_description"])
    @describe()
    @rename()
    async def remove_item(self, interaction: Interaction):
        pass

    @command(name=COG_STRINGS["react_delete_menu_name"], description=COG_STRINGS["react_delete_menu_description"])
    @describe()
    @rename()
    async def delete_menu(self, interaction: Interaction):
        pass


async def setup(bot: Bot):
    await bot.add_cog(RoleReact(bot))
