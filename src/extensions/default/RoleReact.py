import logging

from discord.ext.commands import Bot, GroupCog

from common.io import load_cog_toml

COG_STRINGS = load_cog_toml(__name__)


class RoleReact(GroupCog, name=COG_STRINGS["react_group_name"]):

    def __init__(self, bot: Bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"{__name__} has been added as a Cog")


async def setup(bot: Bot):
    await bot.add_cog(RoleReact(bot))
