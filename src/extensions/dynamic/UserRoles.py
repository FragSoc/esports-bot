from discord.app_commands import guild_only, default_permissions
from discord.ext.commands import GroupCog, Bot
from discord import Role
from common.io import load_cog_toml
from asyncio import sleep as async_sleep, create_task
import logging

COG_STRINGS = load_cog_toml(__name__)


def timeout_role_mention(role: Role, duration: float):

    async def timeout():
        await role.edit(mentionable=False)
        await async_sleep(duration)
        await role.edit(mentionable=True)

    create_task(timeout())


@default_permissions(administrator=True)
@guild_only()
class UserRolesAdmin(GroupCog, name=COG_STRINGS["users_admin_group_name"]):

    def __init__(self, bot: Bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"{__name__}.{__class__.__name__} has been added as a Cog")


@guild_only()
class UserRoles(GroupCog, name=COG_STRINGS["users_group_name"]):

    def __init__(self, bot: Bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"{__name__}.{__class__.__name__} has been added as a Cog")


async def setup(bot: Bot):
    await bot.add_cog(UserRolesAdmin(bot))
    await bot.add_cog(UserRoles(bot))
