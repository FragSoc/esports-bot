from discord.ext.commands import Bot, Cog

import logging
from common.io import load_cog_toml

COG_STRINGS = load_cog_toml(__name__)


class AutoRoles(Cog):

    def __init__(self, bot: Bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"{__name__} has been added as a Cog")


async def setup(bot: Bot):
    await bot.add_cog(AutoRoles(bot))
