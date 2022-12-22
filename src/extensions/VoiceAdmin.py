from discord import Interaction, Member, VoiceChannel, VoiceState
from discord.ext.commands import Bot, Cog
from discord.app_commands import command, describe, rename, default_permissions, checks, guild_only

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

    @command(name=COG_STRINGS["vc_set_parent_name"], description=COG_STRINGS["vc_set_parent_description"])
    @describe(channel=COG_STRINGS["vc_set_parent_param_describe"])
    @rename(channel=COG_STRINGS["vc_set_parent_param_rename"])
    @default_permissions(administrator=True)
    @checks.has_permssions(administrator=True)
    @guild_only()
    async def set_parent_channel(self, interaction: Interaction, channel: VoiceChannel):
        pass

    @command(name=COG_STRINGS["vc_remove_parent_name"], description=COG_STRINGS["vc_remove_parent_description"])
    @describe(channel=COG_STRINGS["vc_remove_parent_param_describe"])
    @rename(channel=COG_STRINGS["vc_remove_parent_param_rename"])
    @default_permissions(administrator=True)
    @checks.has_permissions(administrator=True)
    @guild_only()
    async def remove_parent_channel(self, interaction: Interaction, channel: VoiceChannel):
        pass

    @command(name=COG_STRINGS["vc_get_parents_name"], description=COG_STRINGS["vc_get_parents_description"])
    @guild_only()
    async def get_parent_channels(self, interaction: Interaction):
        pass


async def setup(bot: Bot):
    await bot.add_cog(VoiceAdmin(bot))
