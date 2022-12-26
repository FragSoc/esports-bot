from discord.errors import Forbidden
from discord import Interaction, Member, VoiceChannel, VoiceState
from discord.ext.commands import Bot, Cog
from discord.app_commands import command, describe, rename, default_permissions, checks, guild_only

import logging
from common.discord import primary_key_from_object
from common.io import load_cog_toml
from database.models import VoiceAdminParent, VoiceAdminChild
from database.gateway import DBSession
from client import EsportsBot

COG_STRINGS = load_cog_toml(__name__)


def channel_is_child(channel: VoiceChannel):
    if not channel:
        return False
    db_result = DBSession.get(VoiceAdminChild, guild_id=channel.guild.id, channel_id=channel.id)
    return not not db_result


def channel_is_parent(channel: VoiceChannel):
    if not channel:
        return False
    db_result = DBSession.get(VoiceAdminParent, guild_id=channel.guild.id, channel_id=channel.id)
    return not not db_result


def member_is_owner(member: Member, channel: VoiceChannel, db_entry: VoiceAdminChild = None):
    if not channel:
        return False

    if db_entry is None:
        db_entry: VoiceAdminChild = DBSession.get(VoiceAdminChild, guild_id=channel.guild.id, channel_id=channel.id)
        if db_entry is None:
            return False
    return db_entry.owner_id == member.id


class VoiceAdmin(Cog):

    def __init__(self, bot: EsportsBot):
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

            if not before.channel.category.permissions_for(before.channel.guild.me).manage_channels:
                self.logger.error(
                    f"Missing permission `manage_channels` for category {before.channel.category.name} "
                    f"(channelid - {before.channel.category.id}) in guild {before.channel.guild.name} "
                    f"(guildid - {before.channel.guild.id})"
                )
                return

            db_entry: VoiceAdminChild = DBSession.get(
                VoiceAdminChild,
                guild_id=before.channel.guild.id,
                channel_id=before.channel.id
            )

            if not before.channel.members:
                await before.channel.delete()
                DBSession.delete(db_entry)
                if not channel_is_parent(after.channel):
                    return

            if member_is_owner(member, before.channel, db_entry):
                new_owner = before.channel.members[0]
                db_entry.owner_id = new_owner.id
                DBSession.update(db_entry)
                self.logger.info(
                    f"Deleted child Voice Channel - "
                    f"{before.channel.name} (guildid - {before.channel.guild.id} | channelid - {before.channel.id}"
                )
                await before.channel.edit(name=f"{new_owner.display_name}'s VC")

        if after.channel:
            if not channel_is_parent(after.channel):
                return

            if not after.channel.category.permissions_for(after.channel.guild.me).manage_channels:
                self.logger.error(
                    f"Missing permission `manage_channels` for category {after.channel.category.name} "
                    f"(channelid - {after.channel.category.id}) in guild {after.channel.guild.name} "
                    f"(guildid - {after.channel.guild.id})"
                )
                return

            new_child_channel: VoiceChannel = await after.channel.category.create_voice_channel(
                name=f"{member.display_name}'s VC"
            )
            db_entry: VoiceAdminChild = VoiceAdminChild(
                primary_key=primary_key_from_object(new_child_channel),
                guild_id=new_child_channel.guild.id,
                channel_id=new_child_channel.id,
                owner_id=member.id,
                is_locked=False,
                is_limited=False,
                has_custom_name=False
            )
            DBSession.create(db_entry)
            self.logger.info(
                f"Created new child Voice Channel - "
                f"{new_child_channel.name} (guildid - {new_child_channel.guild.id} | channelid - {new_child_channel.id})"
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
        await interaction.response.defer()

        if channel_is_parent(channel):
            await interaction.followup.send(COG_STRINGS["vc_set_parent_warn_already_parent"], ephemeral=True)
            return False

        if channel_is_child(channel):
            await interaction.followup.send(COG_STRINGS["vc_set_parent_warn_already_child"], ephemeral=True)
            return False

        db_entry: VoiceAdminParent = VoiceAdminParent(
            primary_key=primary_key_from_object(channel),
            guild_id=interaction.guild.id,
            channel_id=channel.id
        )
        DBSession.create(db_entry)
        self.logger.info(
            f"Successfully added {channel.name} (guildid - {channel.guild.id} | channelid - {channel.id}) "
            f"to Parent Voice Channel DB Table!"
        )
        await interaction.followup.send(
            COG_STRINGS["vc_set_parent_success"].format(channel=channel),
            ephemeral=self.bot.only_ephemeral
        )
        return True

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
        await interaction.response.defer()

        if not channel_is_parent(channel):
            await interaction.followup.send(COG_STRINGS["vc_remove_parent_warn_not_parent"], ephemeral=True)
            return False

        db_entry = DBSession.get(VoiceAdminParent, guild_id=channel.guild.id, channel_id=channel.id)
        DBSession.delete(db_entry)
        await interaction.followup.send(
            COG_STRINGS["vc_remove_parent_success"].format(channel=channel.name),
            ephemeral=self.bot.only_ephemeral
        )
        return True

    @command(name=COG_STRINGS["vc_get_parents_name"], description=COG_STRINGS["vc_get_parents_description"])
    @guild_only()
    async def get_parent_channels(self, interaction: Interaction):
        """The command used to get a list of the currently set parent Voice Channels in the current guild/server.

        Args:
            interaction (Interaction): The interaction that triggered the command.
        """
        await interaction.response.defer()

        db_items = DBSession.list(VoiceAdminParent)

        fetched_channels = [await interaction.guild.fetch_channel(x.channel_id) for x in db_items]

        if len(fetched_channels) == 0:
            await interaction.followup.send(COG_STRINGS["vc_get_parents_empty"], ephemeral=self.bot.only_ephemeral)
            return False

        response_string = "\n".join([f"- {x.name}" for x in fetched_channels])

        await interaction.followup.send(
            COG_STRINGS["vc_get_parents_format"].format(channels=response_string),
            ephemeral=self.bot.only_ephemeral
        )
        return True

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
        await interaction.response.defer()

        voice_state = interaction.user.voice

        if voice_state is None:
            await interaction.followup.send(COG_STRINGS["vc_rename_warn_no_voice"], ephemeral=True)
            return False

        voice_channel = voice_state.channel
        db_entry = DBSession.get(VoiceAdminChild, guild_id=voice_channel.guild.id, channel_id=voice_channel.id)

        if not member_is_owner(interaction.user, voice_channel, db_entry):
            await interaction.followup.send(COG_STRINGS["vc_rename_warn_not_owner"], ephemeral=True)
            return False

        name_set = new_name if new_name else f"{interaction.user.display_name}'s VC"

        if not new_name:
            if db_entry.has_custom_name:
                await voice_channel.edit(name=f"{interaction.user.display_name}'s VC")
                db_entry.has_custom_name = False
                DBSession.update(db_entry)
        else:
            await voice_channel.edit(name=new_name)
            if not db_entry.has_custom_name:
                db_entry.has_custom_name = True
                DBSession.update(db_entry)

        self.logger.info(
            f"Updated child Voice Channel of {interaction.user.display_name} "
            f"(guildid - {interaction.guild.id} | channelid - {voice_channel.id}) to {name_set}"
        )
        await interaction.followup.send(
            COG_STRINGS["vc_rename_success"].format(name=name_set),
            ephemeral=self.bot.only_ephemeral
        )
        return True

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
        await interaction.response.defer()

        voice_state = interaction.user.voice

        if voice_state is None:
            await interaction.followup.send(COG_STRINGS["vc_lock_warn_no_voice"], ephemeral=True)
            return False

        voice_channel = voice_state.channel
        db_entry = DBSession.get(VoiceAdminChild, guild_id=voice_channel.guild.id, channel_id=voice_channel.id)

        if not member_is_owner(interaction.user, voice_channel, db_entry):
            await interaction.followup.send(COG_STRINGS["vc_lock_warn_not_owner"], ephemeral=True)
            return False

        current_perms = voice_channel.overwrites

        try:
            await voice_channel.set_permissions(
                voice_channel.guild.me.top_role,
                connect=True,
                view_channel=True,
                manage_channels=True,
                manage_permissions=True
            )
        except Forbidden:
            self.logger.error(
                f"Unable to change permissions for {voice_channel.guild.me.top_role.name} Role for child Voice channel "
                f"(guildid - {voice_channel.guild.id} | channelid - {voice_channel.id}, "
                f"as it is the bot's top role and it is not an admin in {voice_channel.guild.name} guild"
            )

        for group, permission in current_perms.items():
            permission.connect = False
            permission.speak = False
            try:
                await voice_channel.set_permissions(group, overwrite=permission)
            except Forbidden:
                self.logger.error(
                    f"Unable to change permissions for {voice_channel.guild.me.top_role.name} Role for child Voice channel "
                    f"(guildid - {voice_channel.guild.id} | channelid - {voice_channel.id}"
                )

        members = voice_channel.members
        for member in members:
            try:
                await voice_channel.set_permissions(member, connect=True, speak=True, view_channel=True)
            except Forbidden:
                self.logger.error(
                    f"Unable to change permissions for {member.display_name} member for child Voice channel "
                    f"(guildid - {voice_channel.guild.id} | channelid - {voice_channel.id}"
                )

        if not db_entry.is_locked:
            db_entry.is_locked = True
            DBSession.update(db_entry)

        await interaction.followup.send(COG_STRINGS["vc_lock_success"], ephemeral=self.bot.only_ephemeral)

        return True

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
        await interaction.response.defer()

        voice_state = interaction.user.voice

        if voice_state is None:
            await interaction.followup.send(COG_STRINGS["vc_unlock_warn_no_voice"], ephemeral=True)
            return False

        voice_channel = voice_state.channel
        db_entry = DBSession.get(VoiceAdminChild, guild_id=voice_channel.guild.id, channel_id=voice_channel.id)

        if not member_is_owner(interaction.user, voice_channel, db_entry):
            await interaction.followup.send(COG_STRINGS["vc_unlock_warn_not_owner"], ephemeral=True)
            return False

        if not db_entry.is_locked:
            if not voice_channel.permissions_synced:
                await voice_channel.edit(sync_permissions=True)
            await interaction.followup.send(COG_STRINGS["vc_unlock_warn_not_locked"], ephemeral=True)
            return False

        db_entry.is_locked = False
        DBSession.update(db_entry)
        await voice_channel.edit(sync_permissions=True)

        await interaction.followup.send(COG_STRINGS["vc_unlock_success"], ephemeral=self.bot.only_ephemeral)
        return True

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
        await interaction.response.defer()

        voice_state = interaction.user.voice

        if not voice_state:
            await interaction.followup.send(COG_STRINGS["vc_limit_warn_no_voice"], ephemeral=True)
            return False

        voice_channel = voice_state.channel
        db_entry = DBSession.get(VoiceAdminChild, guild_id=voice_channel.guild.id, channel_id=voice_channel.id)

        if not member_is_owner(interaction.user, voice_channel, db_entry):
            await interaction.followup.send(COG_STRINGS["vc_limit_warn_not_owner"], ephemeral=True)
            return False

        if user_limit <= 0:
            user_limit = len(voice_channel.members)
        elif user_limit > 99:
            await interaction.followup.send(COG_STRINGS["vc_limit_warn_too_many"], ephemeral=True)
            return False

        await voice_channel.edit(user_limit=user_limit)
        if not db_entry.is_limited:
            db_entry.is_limited = True
            DBSession.update(db_entry)

        await interaction.followup.send(
            COG_STRINGS["vc_limit_success"].format(count=user_limit),
            ephemeral=self.bot.only_ephemeral
        )
        return True

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
        await interaction.response.defer()

        voice_state = interaction.user.voice

        if not voice_state:
            await interaction.followup.send(COG_STRINGS["vc_unlimit_warn_no_voice"], ephemeral=True)
            return False

        voice_channel = voice_state.channel
        db_entry = DBSession.get(VoiceAdminChild, guild_id=voice_channel.guild.id, channel_id=voice_channel.id)

        if not member_is_owner(interaction.user, voice_channel, db_entry):
            await interaction.followup.send(COG_STRINGS["vc_unlimit_warn_not_owner"], ephemeral=True)
            return False

        if not db_entry.is_limited:
            await interaction.followup.send(COG_STRINGS["vc_unlimit_warn_not_limited"], ephemeral=True)
            return False

        db_entry.is_limited = False
        DBSession.update(db_entry)
        await voice_channel.edit(user_limit=None)

        await interaction.followup.send(COG_STRINGS["vc_unlimit_success"], ephemeral=self.bot.only_ephemeral)
        return True


async def setup(bot: Bot):
    await bot.add_cog(VoiceAdmin(bot))
