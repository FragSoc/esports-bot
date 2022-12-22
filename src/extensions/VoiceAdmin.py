from discord import Interaction, Member, VoiceChannel, VoiceState
from discord.ext.commands import Bot, Cog
from discord.app_commands import command, describe, rename, default_permissions, checks, guild_only

import logging
from common.io import load_cog_toml

COG_STRINGS = load_cog_toml(__name__)


def channel_is_child(channel: VoiceChannel):
    return False


def channel_is_parent(channel: VoiceChannel):
    return False


def member_is_owner(member: Member, channel: VoiceChannel, db_entry=None):
    return False


class VoiceAdmin(Cog):

    def __init__(self, bot: Bot):
        """VoiceAdmin cog is used to dynamically create and manage Voice Channels,
        by assigning specific channels to act as parent channels.

        When users join parent Voice Channels, a new chil Voice Channel is created,
        and the user moved to it. The user has control over the child Voice Channel name,
        and can limit how many/who can join.

        Args:
            bot (Bot): The instance of the bot to attach the cog to.
        """
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"{__name__} has been added as a Cog")

    @Cog.listener()
    async def on_voice_state_update(self, member: Member, before: VoiceState, after: VoiceState):
        """The listener used to track when users join/leave Voice Channels that the Bot has access to.

        Is used to create child Voice Channels when users join parent Voice Channels. It is also used
        to transfer ownership of a child Voice Channel when it's owner leaves, or delete a child Voice Channel
        if the last member in the Voice Channel leaves.

        Args:
            member (Member): The member who's Voice State was updated.
            before (VoiceState): The Voice State prior to the update.
            after (VoiceState): The new Voice State after the update.
        """
        if not member.guild.me.guild_permissions.move_members:
            self.logger.error(f"Missing perimssion `move_members` in guild {member.guild.name} (guildid - {member.guild.id})!")
            return

        if not before.channel and not after.channel:
            return

        if before.channel:
            if not channel_is_child(before.channel):
                return

            if not before.channel.members:
                await before.channel.delete()
                if not channel_is_parent(after.channel):
                    return

            if member_is_owner(member, before.channel):
                new_owner = before.channel.members[0]
                await before.channel.edit(name=f"{new_owner.display_name}'s VC")

        if after.channel:
            if not channel_is_parent(after.channel):
                return

            new_child_channel: VoiceChannel = await after.channel.category.create_voice_channel(
                name=f"{member.display_name}'s VC"
            )
            await member.move_to(new_child_channel)

    @command(name=COG_STRINGS["vc_set_parent_name"], description=COG_STRINGS["vc_set_parent_description"])
    @describe(channel=COG_STRINGS["vc_set_parent_param_describe"])
    @rename(channel=COG_STRINGS["vc_set_parent_param_rename"])
    @default_permissions(administrator=True)
    @checks.has_permissions(administrator=True)
    @guild_only()
    async def set_parent_channel(self, interaction: Interaction, channel: VoiceChannel):
        """The command used to set a given Voice Channel to be a parent Voice Channel.

        This means that when users join the given Voice Channel, the Bot will create child Voice Channels.

        Args:
            interaction (Interaction): The interaction that triggered the command.
            channel (VoiceChannel): The Voice Channel to set as a parent Voice Channel.
        """
        pass

    @command(name=COG_STRINGS["vc_remove_parent_name"], description=COG_STRINGS["vc_remove_parent_description"])
    @describe(channel=COG_STRINGS["vc_remove_parent_param_describe"])
    @rename(channel=COG_STRINGS["vc_remove_parent_param_rename"])
    @default_permissions(administrator=True)
    @checks.has_permissions(administrator=True)
    @guild_only()
    async def remove_parent_channel(self, interaction: Interaction, channel: VoiceChannel):
        """The command used to stop a channel from being a parent Voice Channel.

        This means that when users join the given Voice Channel, child Voice Channels will no longer be created.

        Args:
            interaction (Interaction): The interaction that triggered the command.
            channel (VoiceChannel): The Voice Channel to stop behaving as a parent Voice Channel.
        """
        pass

    @command(name=COG_STRINGS["vc_get_parents_name"], description=COG_STRINGS["vc_get_parents_description"])
    @guild_only()
    async def get_parent_channels(self, interaction: Interaction):
        """The command used to get a list of the currently set parent Voice Channels in the current guild/server.

        Args:
            interaction (Interaction): The interaction that triggered the command.
        """
        pass

    @command(
        name=COG_STRINGS["vc_rename_name"],
        description=f"{COG_STRINGS['vc_rename_description']} {COG_STRINGS['vc_must_be_owner']}"
    )
    @describe(new_name=COG_STRINGS["vc_rename_param_describe"])
    @rename(new_name=COG_STRINGS["vc_rename_param_rename"])
    @guild_only()
    async def rename_channel(self, interaction: Interaction, new_name: str = ""):
        """The command users can use to rename their child Voice Channels.

        Only the owner of the child Voice Channel is allowed to use this command to rename a child Voice Channel. If
        no new name is provided, the Voice Channel's name is reset to the child Voice Channel default name.

        Args:
            interaction (Interaction): The interaction that triggered the command.
            new_name (str, optional): The new name to set the Voice Channel to.
            Defaults to the default child Voice Channel string.
        """
        pass

    @command(
        name=COG_STRINGS["vc_lock_name"],
        description=f"{COG_STRINGS['vc_lock_description']} {COG_STRINGS['vc_must_be_owner']}"
    )
    @guild_only()
    async def lock_channel(self, interaction: Interaction):
        """The command that allows users to lock who can join their child Voice Channels.
        It will set the members who are allowed to join the child Voice Channel to those who are
        currently in the child Voice Channel.

        Only the owner of the child Voice Channel is allowed to lock who can join.

        Args:
            interaction (Interaction): The interaction that triggered the command.
        """
        pass

    @command(
        name=COG_STRINGS["vc_unlock_name"],
        description=f"{COG_STRINGS['vc_unlock_description']} {COG_STRINGS['vc_must_be_owner']}"
    )
    @guild_only()
    async def unlock_channel(self, interaction: Interaction):
        """The command users can use to re-allow anyone to join their child Voice Channels.

        Only the owner of the child Voice Channel is allowed to remove the lock.

        Args:
            interaction (Interaction): The interaction that triggered the command.
        """
        pass

    @command(
        name=COG_STRINGS["vc_limit_name"],
        description=f"{COG_STRINGS['vc_limit_description']} {COG_STRINGS['vc_must_be_owner']}"
    )
    @describe(user_limit=COG_STRINGS["vc_limit_param_describe"])
    @rename(user_limit=COG_STRINGS["vc_limit_param_rename"])
    @guild_only()
    async def limit_channel(self, interaction: Interaction, user_limit: int = 0):
        """The command that allows users to set a member count limit on their child Voice Channels.
        If no user limit is provided, the current number of members in the channel is set as the limit.

        Only the owner of the child voice Channel can limit the number of members allowed in the child Voice Channel.

        Args:
            interaction (Interaction): The interaction that triggered the command.
            user_limit (int, optional): The number of members to limit the child Voice Channel to.
            Defaults to the number of members in the child Voice Channel.
        """
        pass

    @command(
        name=COG_STRINGS["vc_unlimit_name"],
        description=f"{COG_STRINGS['vc_unlimit_description']} {COG_STRINGS['vc_must_be_owner']}"
    )
    @guild_only()
    async def unlimit_channel(self, interaction: Interaction):
        """The command that allows users to remove the member count limit on their child Voice Channels.

        Only the owner of the chid Voice Channel can remove the member limit on the child Voice Channel.

        Args:
            interaction (Interaction): The interaction that triggered the command.
        """
        pass


async def setup(bot: Bot):
    await bot.add_cog(VoiceAdmin(bot))
