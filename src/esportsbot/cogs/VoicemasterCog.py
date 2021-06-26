from discord.ext import commands
from esportsbot.db_gateway_v1 import DBGatewayActions
from esportsbot.models import Voicemaster_master, Voicemaster_slave
from esportsbot.base_functions import send_to_log_channel


class VoicemasterCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
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
                await send_to_log_channel(
                    self,
                    ctx.author.guild.id,
                    f"{ctx.author.mention} has made {new_vm_master_channel.name} - {new_vm_master_channel.id} a VM master VC"
                )
            elif is_a_master:
                # This already exists as a master
                await ctx.channel.send("This VC is already set as a VM master")
            elif is_a_slave:
                # This is a slave VC
                await ctx.channel.send("This VC is already set as a VM slave")
            elif not is_voice_channel:
                # This is not a VC ID
                await ctx.channel.send("The ID entered is not a VC")

        else:
            # Invalid input
            if not given_channel_id:
                await ctx.channel.send("You need to provide a VC ID as well")
            else:
                await ctx.channel.send("The ID argument is not a valid Discord ID format")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def getvmmasters(self, ctx):
        master_vm_exists = DBGatewayActions().list(Voicemaster_master, guild_id=ctx.author.guild.id)

        if master_vm_exists:
            master_vm_str = str()
            for record in master_vm_exists:
                master_vm_str += f"{self.bot.get_channel(record.channel_id).name} - {record.channel_id}\n"
            await ctx.channel.send(f"Current VM master VCs in this server:\n{master_vm_str}")
        else:
            await ctx.channel.send("No VCs in this server currently set as VM masters")

    @commands.command()
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
                await ctx.channel.send("This VC is no longer a VM master")
                removed_vm_master = self.bot.get_channel(given_channel_id)
                await send_to_log_channel(
                    self,
                    ctx.author.guild.id,
                    f"{ctx.author.mention} has removed {removed_vm_master.name} - {removed_vm_master.id} from VM master VC"
                )
            else:
                await ctx.channel.send("This VC is not currently a VM master")
        else:
            await ctx.channel.send("You need to include the VC ID")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def removeallmasters(self, ctx):
        all_vm_masters = DBGatewayActions().list(Voicemaster_master, guild_id=ctx.author.guild.id)
        for vm_master in all_vm_masters:
            DBGatewayActions().delete(vm_master)
        await ctx.channel.send("Cleared all VM masters from this server")
        await send_to_log_channel(self, ctx.author.guild.id, f"{ctx.author.mention} has removed all VM masters")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def killallslaves(self, ctx):
        all_vm_slaves = DBGatewayActions().list(Voicemaster_slave, guild_id=ctx.author.guild.id)
        for vm_slave in all_vm_slaves:
            vm_slave_channel = self.bot.get_channel(vm_slave.channel_id)
            if vm_slave_channel:
                await vm_slave_channel.delete()
            DBGatewayActions().delete(vm_slave)
        await ctx.channel.send("Cleared all VM slaves from this server")
        await send_to_log_channel(self, ctx.author.guild.id, f"{ctx.author.mention} has removed all VM slaves")

    @commands.command()
    async def lockvm(self, ctx):
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
                    await ctx.channel.send("Your VM slave has been locked 🔒")
                    await send_to_log_channel(self, ctx.author.guild.id, f"{ctx.author.mention} has locked their VM slave")
                else:
                    await ctx.channel.send("Your VM slave is already locked")
            else:
                await ctx.channel.send("You are not the owner of this VM slave")
        else:
            await ctx.channel.send("You are not currently in a VM slave")

    @commands.command()
    async def unlockvm(self, ctx):
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
                    await ctx.channel.send("Your VM slave has been unlocked 🔓")
                    await send_to_log_channel(self, ctx.author.guild.id, f"{ctx.author.mention} has unlocked their VM slave")
                else:
                    await ctx.channel.send("Your VM slave is already unlocked")
            else:
                await ctx.channel.send("You are not the owner of this VM slave")
        else:
            await ctx.channel.send("You are not currently in a VM slave")


def setup(bot):
    bot.add_cog(VoicemasterCog(bot))
