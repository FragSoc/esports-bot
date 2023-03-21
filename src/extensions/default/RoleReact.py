import logging

from discord import Interaction
from discord.app_commands import (command, default_permissions, describe, guild_only, rename)
from discord.ext.commands import Bot, GroupCog

from common.io import load_cog_toml

COG_STRINGS = load_cog_toml(__name__)
ROLE_REACT_INTERACTION_PREFIX = f"{__name__}.interaction"


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
    @describe()
    @rename()
    async def create_menu(self, interaction: Interaction):
        pass

    @command(name=COG_STRINGS["react_add_item_name"], description=COG_STRINGS["react_add_item_description"])
    @describe()
    @rename()
    async def add_item(self, interaction: Interaction):
        pass

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
