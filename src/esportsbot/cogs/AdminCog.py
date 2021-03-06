from discord.ext import commands
from db_gateway import db_gateway
from base_functions import send_to_log_channel


class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=['cls', 'purge', 'delete', 'Cls', 'Purge', 'Delete', 'Clear'])
    @commands.has_permissions(manage_messages=True)
    async def clear(self, ctx, amount=5):
        await ctx.channel.purge(limit=int(amount)+1)
        await send_to_log_channel(self, ctx.author.guild.id, f"{ctx.author.mention} has cleared {amount} messages from {ctx.channel.mention}")

    @commands.command(aliases=['Members'])
    @commands.has_permissions(manage_messages=True)
    async def members(self, ctx):
        await ctx.channel.send(f"This server has {ctx.guild.member_count} members including me")


def setup(bot):
    bot.add_cog(AdminCog(bot))
