from discord.ext import commands
from db_gateway import db_gateway
from base_functions import get_cleaned_id


class DefaultRoleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    async def send_to_log_channel(self, guild_id, msg):
        db_logging_call = db_gateway().get('guild_info', params={'guild_id': guild_id})
        if db_logging_call:
            await self.bot.get_channel(db_logging_call[0]['log_channel_id']).send(msg)


    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setdefaultrole(self, ctx, given_role_id=None):
        cleaned_role_id = get_cleaned_id(given_role_id) if given_role_id else False
        if cleaned_role_id:
            db_gateway().update('guild_info', set_params={'default_role_id': cleaned_role_id}, where_params={'guild_id': ctx.author.guild.id})
            await ctx.channel.send(f"Default role has been set to {cleaned_role_id}")
            default_role = ctx.author.guild.get_role(cleaned_role_id)
            await self.send_to_log_channel(ctx.author.guild.id, f"{ctx.author.mention} has set the default role to {default_role.mention}")
        else:
            await ctx.channel.send("You need to either @ a role or paste the ID")


    @commands.command()
    @commands.has_permissions(administrator=True)
    async def getdefaultrole(self, ctx):
        default_role_exists = db_gateway().get('guild_info', params={'guild_id': ctx.author.guild.id})

        if default_role_exists[0]['default_role_id']:
            await ctx.channel.send(f"Default role is set to {default_role_exists[0]['default_role_id']}")
        else:
            await ctx.channel.send("Default role has not been set")


    @commands.command()
    @commands.has_permissions(administrator=True)
    async def removedefaultrole(self, ctx):
        default_role_exists = db_gateway().get('guild_info', params={'guild_id': ctx.author.guild.id})

        if default_role_exists[0]['default_role_id']:
            db_gateway().update('guild_info', set_params={'default_role_id': 'NULL'}, where_params={'guild_id': ctx.author.guild.id})
            await ctx.channel.send("Default role has been removed")
            await self.send_to_log_channel(ctx.author.guild.id, f"{ctx.author.mention} has removed the default role")
        else:
            await ctx.channel.send("Default role has not been set")

    
def setup(bot):
    bot.add_cog(DefaultRoleCog(bot))