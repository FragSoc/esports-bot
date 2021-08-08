from discord.ext import commands
from esportsbot.base_functions import (get_whether_in_vm_master, get_whether_in_vm_slave)
from esportsbot.db_gateway import DBGatewayActions
from esportsbot.lib.client import instance
from esportsbot.models import Voicemaster_master, Voicemaster_slave


class VoicemasterCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.STRINGS = bot.STRINGS['voicemaster']

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        before_channel_id = before.channel.id if before.channel else False
        after_channel_id = after.channel.id if after.channel else False

        if not member.guild.me.guild_permissions.move_members:
            this_instance = instance()
            await this_instance.adminLog(
                None,
                {"Message": "I need the permission `move members` in this guild to be able to perform Voicemaster"},
                guildID=member.guild.id
            )
            return

        if before_channel_id and get_whether_in_vm_slave(member.guild.id, before_channel_id):
            vm_slave = DBGatewayActions().get(Voicemaster_slave, guild_id=member.guild.id, channel_id=before_channel_id)
            # If you were in a slave VM VC
            if not before.channel.members:
                # Nobody else in VC
                await before.channel.delete()
                DBGatewayActions().delete(vm_slave)
                this_instance = instance()
                await this_instance.adminLog(
                    None,
                    {
                        "Cog": "VoiceMaster",
                        "Message": f"{member.mention} has deleted a VM slave"
                    },
                    guildID=member.guild.id
                )
            else:
                # Still others in VC
                await before.channel.edit(name=f"{before.channel.members[0].display_name}'s VC")
                vm_slave.owner_id = before.channel.members[0].id
                DBGatewayActions().update(vm_slave)
        elif after_channel_id and get_whether_in_vm_master(member.guild.id, after_channel_id):
            # Moved into a master VM VC
            slave_channel_name = f"{member.display_name}'s VC"
            new_slave_channel = await member.guild.create_voice_channel(slave_channel_name, category=after.channel.category)
            DBGatewayActions().create(
                Voicemaster_slave(guild_id=member.guild.id,
                                  channel_id=new_slave_channel.id,
                                  owner_id=member.id,
                                  locked=False)
            )
            await member.move_to(new_slave_channel)
            this_instance = instance()
            await this_instance.adminLog(
                None,
                {
                    "Cog": "VoiceMaster",
                    "Message": f"{member.mention} has created a VM slave"
                },
                guildID=member.guild.id
            )

    @commands.command(
        name="setvmmaster",
        usage="<channel_id>",
        help="Sets the passed voice channel to a Voicemaster master channel"
    )
    @commands.has_permissions(administrator=True)
    async def setvmmaster(self, ctx, given_channel_id=None):
        is_a_valid_id = given_channel_id and given_channel_id.isdigit() and len(given_channel_id) == 18

        if is_a_valid_id:
            is_a_master = DBGatewayActions().get(Voicemaster_master, guild_id=ctx.author.guild.id, channel_id=given_channel_id)
            is_voice_channel = hasattr(self.bot.get_channel(int(given_channel_id)), 'voice_states')
            is_a_slave = DBGatewayActions().get(Voicemaster_slave, guild_id=ctx.author.guild.id, channel_id=given_channel_id)

            if is_voice_channel and not (is_a_master or is_a_slave):
                # Not currently a Master and is voice channel, add it
                DBGatewayActions().create(Voicemaster_master(guild_id=ctx.author.guild.id, channel_id=given_channel_id))
                await ctx.channel.send("This VC has now been set as a VM master")
                new_vm_master_channel = self.bot.get_channel(int(given_channel_id))
                this_instance = instance()
                await this_instance.adminLog(
                    ctx.message,
                    {
                        "Cog":
                        "VoiceMaster",
                        "Message":
                        f"{ctx.author.mention} has made {new_vm_master_channel.name} - {new_vm_master_channel.id} a VM master VC"
                    },
                    None,
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

    @commands.command(name="getvmmasters", usage="", help="Gets all of the Voicemaster master channels from the server")
    @commands.has_permissions(administrator=True)
    async def getvmmasters(self, ctx):
        master_vm_exists = DBGatewayActions().list(Voicemaster_master, guild_id=ctx.author.guild.id)

        if master_vm_exists:
            master_vm_str = str()
            for record in master_vm_exists:
                master_vm_str += f"{self.bot.get_channel(record.channel_id).name} - {record.channel_id}\n"
            await ctx.channel.send(self.STRINGS['show_current_vcs'].format(master_vms=master_vm_str))
        else:
            await ctx.channel.send(self.STRINGS['error_no_vms'])

    @commands.command(
        name="removevmmaster",
        usage="<channel_id>",
        help="Removes the passed voice channel from being Voicemaster master channel"
    )
    @commands.has_permissions(administrator=True)
    async def removevmmaster(self, ctx, given_channel_id=None):
        if given_channel_id:
            channel_exists = DBGatewayActions().get(
                Voicemaster_master,
                guild_id=ctx.author.guild.id,
                channel_id=given_channel_id
            )
            if channel_exists:
                DBGatewayActions().delete(channel_exists)
                await ctx.channel.send(self.STRINGS['success_vm_unset'])
                removed_vm_master = self.bot.get_channel(given_channel_id)
                this_instance = instance()
                await this_instance.adminLog(
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
                    None,
                )
            else:
                await ctx.channel.send(self.STRINGS['error_not_vm'])
        else:
            await ctx.channel.send(self.STRINGS['error_no_id'])

    @commands.command(name="removeallmasters", usage="", help="Removes all the Voicemaster master channels from the server")
    @commands.has_permissions(administrator=True)
    async def removeallmasters(self, ctx):
        all_vm_masters = DBGatewayActions().list(Voicemaster_master, guild_id=ctx.author.guild.id)
        for vm_master in all_vm_masters:
            DBGatewayActions().delete(vm_master)
        await ctx.channel.send(self.STRINGS['success_vm_masters_cleared'])
        this_instance = instance()
        await this_instance.adminLog(
            ctx.message,
            {
                "Cog": "VoiceMaster",
                "Message": self.STRINGS['log_vm_masters_cleared'].format(mention=ctx.author.mention)
            },
            None
        )

    @commands.command(name="killallslaves", usage="", help="Deletes all Voicemaster slave channels from the server")
    @commands.has_permissions(administrator=True)
    async def killallslaves(self, ctx):
        all_vm_slaves = DBGatewayActions().list(Voicemaster_slave, guild_id=ctx.author.guild.id)
        for vm_slave in all_vm_slaves:
            vm_slave_channel = self.bot.get_channel(vm_slave.channel_id)
            if vm_slave_channel:
                await vm_slave_channel.delete()
            DBGatewayActions().delete(vm_slave)
        await ctx.channel.send(self.STRINGS['success_vm_slaves_cleared'])
        this_instance = instance()
        await this_instance.adminLog(
            ctx.message,
            {
                "Cog": "VoiceMaster",
                "Message": self.STRINGS['log_vm_slaves_cleared'].format(mention=ctx.author.mention)
            },
            None
        )

    @commands.command(name="lockvm", aliases=["lock"], usage="", help="Locks the Voicemaster slave that you are currently in")
    async def lockvm(self, ctx):
        if not ctx.author.voice:
            await ctx.channel.send(self.STRINGS['error_not_in_slave'])
            return
        in_vm_slave = DBGatewayActions().get(
            Voicemaster_slave,
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
                    this_instance = instance()
                    await this_instance.adminLog(
                        ctx.message,
                        {
                            "Cog": "VoiceMaster",
                            "Message": self.STRINGS['log_slave_locked'].format(mention=ctx.author.mention)
                        },
                        None
                    )
                else:
                    await ctx.channel.send(self.STRINGS['error_already_locked'])
            else:
                await ctx.channel.send(self.STRINGS['error_not_owned'])
        else:
            await ctx.channel.send(self.STRINGS['error_not_in_slave'])

    @commands.command(
        name="unlockvm",
        aliases=["unlock"],
        usage="",
        help="Unlocks the Voicemaster slave that you are currently in"
    )
    async def unlockvm(self, ctx):
        if not ctx.author.voice:
            await ctx.channel.send(self.STRINGS['error_not_in_slave'])
            return
        in_vm_slave = DBGatewayActions().get(
            Voicemaster_slave,
            guild_id=ctx.author.guild.id,
            channel_id=ctx.author.voice.channel.id
        )

        if in_vm_slave:
            if in_vm_slave.owner_id == ctx.author.id:
                if in_vm_slave.locked:
                    in_vm_slave.locked = False
                    DBGatewayActions().update(in_vm_slave)
                    await ctx.author.voice.channel.edit(user_limit=0)
                    this_instance = instance()
                    await this_instance.adminLog(
                        ctx.message,
                        {
                            "Cog": "VoiceMaster",
                            "Message": self.STRINGS['log_slave_unlocked'].format(mention=ctx.author.mention)
                        },
                        None
                    )
                else:
                    await ctx.channel.send(self.STRINGS['error_already_unlocked'])
            else:
                await ctx.channel.send(self.STRINGS['error_not_owned'])
        else:
            await ctx.channel.send(self.STRINGS['error_not_in_slave'])


def setup(bot):
    bot.add_cog(VoicemasterCog(bot))
