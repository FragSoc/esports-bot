import logging

from discord import Interaction
from discord.app_commands import (command, default_permissions, describe, guild_only, rename)
from discord.ext.commands import Bot, GroupCog

from client import EsportsBot
from common.io import load_bot_version, load_cog_toml

COG_STRINGS = load_cog_toml(__name__)


@default_permissions(administrator=True)
@guild_only()
class AdminTools(GroupCog, name=COG_STRINGS["admin_group_name"]):

    def __init__(self, bot: EsportsBot):
        """AdminTools cog is used to manage basic Administrator/Moderation tools.
        All commands in this cog require the user to have the administrator permission
        in a given guild/server.

        Args:
            bot (Bot): The instance of the bot to attach the cog to.
        """
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        version = load_bot_version()
        if version is None:
            self.version_string = COG_STRINGS["admin_version_missing"]
        else:
            self.version_string = COG_STRINGS["admin_version_format"].format(version=version)

        self.logger.info(f"{__name__} has been added as a Cog")

    @command(name=COG_STRINGS["admin_members_name"], description=COG_STRINGS["admin_members_description"])
    async def get_member_count(self, interaction: Interaction):
        """The command used to get the current member count in the current guild/server.

        Args:
            interaction (Interaction): The interaction that triggered the command.
        """
        await interaction.response.defer(ephemeral=True)

        member_count = interaction.guild.member_count
        await interaction.followup.send(COG_STRINGS["admin_members_format"].format(count=member_count), ephemeral=True)
        return True

    @command(name=COG_STRINGS["admin_version_name"], description=COG_STRINGS["admin_version_description"])
    async def get_bot_version(self, interaction: Interaction):
        """The command used to get the global current version of the Bot.

        Args:
            interaction (Interaction): The interaction that triggered the command.
        """
        await interaction.response.send_message(self.version_string, ephemeral=True)
        return True

    @command(name=COG_STRINGS["admin_clear_name"], description=COG_STRINGS["admin_clear_description"])
    @describe(count=COG_STRINGS["admin_clear_param_describe"])
    @rename(count=COG_STRINGS["admin_clear_param_rename"])
    async def clear_messages(self, interaction: Interaction, count: int = 5):
        """The command used to bulk delete messages in the current channel.
        Defaults to 5 messages if no value is given, and has a maximum value of 100.

        Args:
            interaction (Interaction): The interaction that triggered the command.
            count (int, optional): The number of messages to delete. Defaults to 5. Maximum 100.
        """
        if count > 100:
            await interaction.response.send_message(COG_STRINGS["admin_clear_warn_too_many"], ephemeral=True)
            return False

        await interaction.response.defer(ephemeral=True)
        messages = await interaction.channel.purge(limit=count, before=interaction.created_at)

        self.logger.info(
            f"{self.bot.logging_prefix}[{interaction.guild.id}] {interaction.user.mention} cleared {len(messages)} from {interaction.channel.mention}"
        )
        await interaction.followup.send(COG_STRINGS["admin_clear_success"].format(count=len(messages)), ephemeral=False)
        return True


async def setup(bot: Bot):
    await bot.add_cog(AdminTools(bot))
