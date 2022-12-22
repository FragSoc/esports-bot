from discord import Interaction
from discord.ext.commands import Bot, Cog
from discord.app_commands import command, default_permissions, checks, guild_only

import logging
from common.io import load_bot_version, load_cog_toml

COG_STRINGS = load_cog_toml(__name__)


class AdminTools(Cog):

    def __init__(self, bot: Bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        version = load_bot_version()
        if version is None:
            self.version_string = COG_STRINGS["admin_version_missing"]
        else:
            self.version_string = COG_STRINGS["admin_version_format"].format(version=version)

        self.logger.info(f"{__name__} has been added as a Cog")

    @command(name=COG_STRINGS["admin_members_name"], description=COG_STRINGS["admin_members_description"])
    @default_permissions(administrator=True)
    @checks.has_permssions(administrator=True)
    @guild_only()
    async def get_member_count(self, interaction: Interaction):
        pass

    @command(name=COG_STRINGS["admin_version_name"], description=COG_STRINGS["admin_version_description"])
    @default_permissions(administrator=True)
    @checks.has_permissions(administrator=True)
    @guild_only
    async def get_bot_version(self, interaction: Interaction):
        pass


async def setup(bot: Bot):
    await bot.add_cog(AdminTools(bot))
