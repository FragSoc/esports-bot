from discord.ext import commands
from esportsbot.base_functions import (get_whether_in_vm_master, get_whether_in_vm_slave)
from esportsbot.db_gateway import DBGatewayActions
from esportsbot.models import VoicemasterMaster, VoicemasterSlave


class VoicemasterCog(commands.Cog):
    """
    Voicemaster is used as a way to have a dynamic number of voice channels. By having a single parent voice channel, users can
    easily create their own room/channel by joining, allowing them to easily talk with just the people they want to.

    This module implements commands used to manage the parent and child channels, all commands require the administrator
    permission in a server.
    """
    def __init__(self, bot):
        self.bot = bot
        self.STRINGS = bot.STRINGS['voicemaster']

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """
        When any users voice state changes, such as joining, leaving or moving voice channels, check if the voice channel they
        are in is a parent or child, and if so perform the necessary actions.

        - If the user was the last to leave a child voice channel, delete it.
        - If the user was the owner of the child voice channel, transfer the ownership to another user in the channel.
        - If the user joined the parent voice channel, create a new child channel that they own.
        :param member: The member whose voice state has changed.
        :param before: The member's voice state before the change.
        :param after: The member's voice state after the change.
        """
        if not member.guild.me.guild_permissions.move_members:
            await self.bot.admin_log(
                None,
                {"Message": "I need the permission `move members` in this guild to be able to perform Voicemaster"},
                guild_id=member.guild.id
            )
            return

        if not before.channel and not after.channel:
            return

        if before.channel:
            # The user has either disconnected or moved voice channels.
            if get_whether_in_vm_slave(before.channel.guild.id, before.channel.id):
                # If the user was in a VM slave.
                vm_slave = DBGatewayActions().get(VoicemasterSlave, guild_id=member.guild.id, channel_id=before.channel.id)
                if not before.channel.members:
                    # The VM is empty, delete it.
                    await before.channel.delete()
                    DBGatewayActions().delete(vm_slave)
                elif vm_slave.owner_id == member.id:
                    # It was the owner of the channel that left, transfer ownership.
                    await before.channel.edit(name=f"{before.channel.members[0].display_name}'s VC")
                    vm_slave.owner_id = before.channel.members[0].id
                    DBGatewayActions().update(vm_slave)

        if after.channel and get_whether_in_vm_master(after.channel.guild.id, after.channel.id):
            slave_channel = await member.guild.create_voice_channel(
                f"{member.display_name}'s VC",
                category=after.channel.category
            )
            slave_db_entry = VoicemasterSlave(
                guild_id=member.guild.id,
                channel_id=slave_channel.id,
                owner_id=member.id,
                locked=False
            )
            DBGatewayActions().create(slave_db_entry)
            await member.move_to(slave_channel)

    @commands.command(name="setvmparent")
    @commands.has_permissions(administrator=True)
    async def setvmmaster(self, ctx, given_channel_id=None):
        """
        Set the given voice channel as a parent voice channel. There can be more than one parent voice channel in a server.
        :param ctx: The context of the command.
        :param given_channel_id: The ID of the voice channel to set as the parent voice channel.
        """
        is_a_valid_id = given_channel_id and given_channel_id.isdigit() and len(given_channel_id) == 18

        if is_a_valid_id:
            is_a_master = DBGatewayActions().get(VoicemasterMaster, guild_id=ctx.author.guild.id, channel_id=given_channel_id)
            is_voice_channel = hasattr(self.bot.get_channel(int(given_channel_id)), 'voice_states')
            is_a_slave = DBGatewayActions().get(VoicemasterSlave, guild_id=ctx.author.guild.id, channel_id=given_channel_id)

            if is_voice_channel and not (is_a_master or is_a_slave):
                # Not currently a Master and is voice channel, add it
                DBGatewayActions().create(VoicemasterMaster(guild_id=ctx.author.guild.id, channel_id=given_channel_id))
                await ctx.channel.send("This VC has now been set as a VM master")
                new_vm_master_channel = self.bot.get_channel(int(given_channel_id))
                await self.bot.admin_log(
                    ctx.message,
                    {
                        "Cog":
                        "VoiceMaster",
                        "Message":
                        f"{ctx.author.mention} has made {new_vm_master_channel.name} - {new_vm_master_channel.id} "
                        f"a VM master VC"
                    },
                )
            elif is_a_master:
                # This already exists as a master
                await ctx.channel.send(self.STRINGS['error_already_setm'])
            elif is_a_slave:
                # This is a slave VC
                await ctx.channel.send(self.STRINGS['error_already_sets'])
            elif not is_voice_channel:
                # This is not a VC ID
                await ctx.channel.send(self.STRINGS['error_bad_id'])

        else:
            # Invalid input
            if not given_channel_id:
                await ctx.channel.send(self.STRINGS['error_no_id'])
            else:
                await ctx.channel.send(self.STRINGS['error_bad_id_format'])

    @commands.command(name="getvmparents")
    @commands.has_permissions(administrator=True)
    async def getvmmasters(self, ctx):
        """
        Get a list of the current voice channels set as parent voice channels.
        :param ctx: The context of the command.
        """
        master_vm_exists = DBGatewayActions().list(VoicemasterMaster, guild_id=ctx.author.guild.id)

        if master_vm_exists:
            master_vm_str = str()
            for record in master_vm_exists:
                master_vm_str += f"{self.bot.get_channel(record.channel_id).name} - {record.channel_id}\n"
            await ctx.channel.send(self.STRINGS['show_current_vcs'].format(master_vms=master_vm_str))
        else:
            await ctx.channel.send(self.STRINGS['error_no_vms'])

    @commands.command(name="removevmparent")
    @commands.has_permissions(administrator=True)
    async def removevmmaster(self, ctx, given_channel_id=None):
        """
        Remove a voice channel from being a parent voice channel.
        :param ctx: The context of the command.
        :param given_channel_id: The ID of the voice channel to remove from being a parent voice channel.
        """
        if given_channel_id:
            channel_exists = DBGatewayActions().get(
                VoicemasterMaster,
                guild_id=ctx.author.guild.id,
                channel_id=given_channel_id
            )
            if channel_exists:
                DBGatewayActions().delete(channel_exists)
                await ctx.channel.send(self.STRINGS['success_vm_unset'])
                removed_vm_master = self.bot.get_channel(given_channel_id)
                await self.bot.admin_log(
                    ctx.message,
                    {
                        "Cog":
                        "VoiceMaster",
                        "Message":
                        self.STRINGS['log_vm_master_removed'].format(
                            mention=ctx.author.guild.id,
                            channel_name=removed_vm_master.name,
                            channel_id=removed_vm_master.id
                        )
                    },
                )
            else:
                await ctx.channel.send(self.STRINGS['error_not_vm'])
        else:
            await ctx.channel.send(self.STRINGS['error_no_id'])

    @commands.command(name="removeallparents")
    @commands.has_permissions(administrator=True)
    async def removeallmasters(self, ctx):
        """
        Remove all the current parent voice channels from the current server.
        :param ctx: The context of the command.
        """
        all_vm_masters = DBGatewayActions().list(VoicemasterMaster, guild_id=ctx.author.guild.id)
        for vm_master in all_vm_masters:
            DBGatewayActions().delete(vm_master)
        await ctx.channel.send(self.STRINGS['success_vm_masters_cleared'])
        await self.bot.admin_log(
            ctx.message,
            {
                "Cog": str(type(self)),
                "Message": self.STRINGS['log_vm_masters_cleared'].format(mention=ctx.author.mention)
            },
        )

    @commands.command(name="removeallchildren")
    @commands.has_permissions(administrator=True)
    async def killallslaves(self, ctx):
        """
        Delete all the child voice channels, no matter if there are users in them or not.
        :param ctx: THe context of the command.
        """
        all_vm_slaves = DBGatewayActions().list(VoicemasterSlave, guild_id=ctx.author.guild.id)
        for vm_slave in all_vm_slaves:
            vm_slave_channel = self.bot.get_channel(vm_slave.channel_id)
            if vm_slave_channel:
                await vm_slave_channel.delete()
            DBGatewayActions().delete(vm_slave)
        await ctx.channel.send(self.STRINGS['success_vm_slaves_cleared'])
        await self.bot.admin_log(
            ctx.message,
            {
                "Cog": str(type(self)),
                "Message": self.STRINGS['log_vm_slaves_cleared'].format(mention=ctx.author.mention)
            },
        )

    @commands.command(name="lockvm", aliases=["lock"])
    async def lockvm(self, ctx):
        """
        Locks a child voice channel to the current number of users. This command can only be run by the owner of the child
        voice channel.
        :param ctx: The context of the command.
        """
        if not ctx.author.voice:
            await ctx.channel.send(self.STRINGS['error_not_in_slave'])
            return
        in_vm_slave = DBGatewayActions().get(
            VoicemasterSlave,
            guild_id=ctx.author.guild.id,
            channel_id=ctx.author.voice.channel.id
        )

        if in_vm_slave:
            if in_vm_slave.owner_id == ctx.author.id:
                if not in_vm_slave.locked:
                    in_vm_slave.locked = True
                    DBGatewayActions().update(in_vm_slave)
                    await ctx.author.voice.channel.edit(user_limit=len(ctx.author.voice.channel.members))
                    await ctx.channel.send(self.STRINGS['success_slave_locked'])
                    await self.bot.admin_log(
                        ctx.message,
                        {
                            "Cog": str(type(self)),
                            "Message": self.STRINGS['log_slave_locked'].format(mention=ctx.author.mention)
                        },
                    )
                else:
                    await ctx.channel.send(self.STRINGS['error_already_locked'])
            else:
                await ctx.channel.send(self.STRINGS['error_not_owned'])
        else:
            await ctx.channel.send(self.STRINGS['error_not_in_slave'])

    @commands.command(name="unlockvm", aliases=["unlock"])
    async def unlockvm(self, ctx):
        """
        Stops the restriction on the number of users allowed in a child voice channel. This command can only be run by the
        owner of the child voice channel.
        :param ctx: The context of the command.
        """
        if not ctx.author.voice:
            await ctx.channel.send(self.STRINGS['error_not_in_slave'])
            return
        in_vm_slave = DBGatewayActions().get(
            VoicemasterSlave,
            guild_id=ctx.author.guild.id,
            channel_id=ctx.author.voice.channel.id
        )

        if in_vm_slave:
            if in_vm_slave.owner_id == ctx.author.id:
                if in_vm_slave.locked:
                    in_vm_slave.locked = False
                    DBGatewayActions().update(in_vm_slave)
                    await ctx.author.voice.channel.edit(user_limit=0)
                    await self.bot.admin_log(
                        ctx.message,
                        {
                            "Cog": str(type(self)),
                            "Message": self.STRINGS['log_slave_unlocked'].format(mention=ctx.author.mention)
                        },
                    )
                else:
                    await ctx.channel.send(self.STRINGS['error_already_unlocked'])
            else:
                await ctx.channel.send(self.STRINGS['error_not_owned'])
        else:
            await ctx.channel.send(self.STRINGS['error_not_in_slave'])


def setup(bot):
    bot.add_cog(VoicemasterCog(bot))
