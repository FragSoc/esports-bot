from discord.app_commands import guild_only, default_permissions
from discord.ext.commands import GroupCog, Bot
from common.io import load_cog_toml
import logging

COG_STRINGS = load_cog_toml(__name__)


@default_permissions(administrator=True)
@guild_only()
class UserRolesAdmin(GroupCog, name=COG_STRINGS["users_admin_group_name"]):

    def __init__(self, bot: Bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"{__name__}.{__class__.__name__} has been added as a Cog")


@default_permissions(administrator=True)
@guild_only()
class UserRoles(GroupCog, name=COG_STRINGS["users_group_name"]):

    def __init__(self, bot: Bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"{__name__}.{__class__.__name__} has been added as a Cog")


async def setup(bot: Bot):
    await bot.add_cog(UserRolesAdmin(bot))
    await bot.add_cog(UserRoles(bot))
