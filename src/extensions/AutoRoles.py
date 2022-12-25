from discord.ext.commands import Bot, Cog
from discord import Member

import logging
from common.io import load_cog_toml
from client import EsportsBot

COG_STRINGS = load_cog_toml(__name__)


class AutoRoles(Cog):

    def __init__(self, bot: EsportsBot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"{__name__} has been added as a Cog")

    @Cog.listener
    async def on_member_join(self, member: Member):
        pass

    @Cog.listener
    async def on_member_remove(self, member: Member):
        pass

    @Cog.listener
    async def on_member_update(self, before: Member, after: Member):
        pass


async def setup(bot: Bot):
    await bot.add_cog(AutoRoles(bot))
