from discord.ext.commands import Bot, Cog

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


async def setup(bot: Bot):
    await bot.add_cog(AdminTools(bot))
