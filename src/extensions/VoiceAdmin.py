from discord import Member, VoiceState
from discord.ext.commands import Bot, Cog

import logging
from common.io import load_cog_toml

COG_STRINGS = load_cog_toml(__name__)


class VoiceAdmin(Cog):

    def __init__(self, bot: Bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"{__name__} has been added as a Cog")

    @Cog.listener()
    async def on_voice_state_update(self, member: Member, before: VoiceState, after: VoiceState):
        if not member.guild.me.guild_permissions.move_members:
            self.logger.error(f"Missing perimssion `move_members` in guild {member.guild.name} (guildid - {member.guild.id})!")
            return

        if not before.channel and not after.channel:
            return

        if before.channel:
            pass

        if after.channel:
            pass


async def setup(bot: Bot):
    await bot.add_cog(VoiceAdmin(bot))
