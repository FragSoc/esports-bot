from discord.ext import commands
from db_gateway import db_gateway

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    async def send_to_log_channel(self, guild_id, msg):
        db_logging_call = db_gateway().get('guild_info', params={'guild_id': guild_id})
        if db_logging_call and db_logging_call[0]['log_channel_id']:
            await self.bot.get_channel(db_logging_call[0]['log_channel_id']).send(msg)


    @commands.command(aliases=['cls', 'purge', 'delete', 'Cls', 'Purge', 'Delete', 'Clear'])
    @commands.has_permissions(manage_messages=True)
    async def clear(self, ctx, amount=5):
        await ctx.channel.purge(limit=int(amount)+1)
        await self.send_to_log_channel(ctx.author.guild.id, f"{ctx.author.mention} has cleared {amount} messages from {ctx.channel.mention}")


    @commands.command(aliases=['Members'])
    @commands.has_permissions(manage_messages=True)
    async def members(self, ctx):
        await ctx.channel.send(f"This server has {ctx.guild.member_count} members including me")


def setup(bot):
    bot.add_cog(AdminCog(bot))