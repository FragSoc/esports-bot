from discord.ext import commands
from db_gateway import db_gateway
from base_functions import get_cleaned_id


class LogChannelCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    async def send_to_log_channel(self, guild_id, msg):
        db_logging_call = db_gateway().get('guild_info', params={'guild_id': guild_id})
        if db_logging_call and db_logging_call[0]['log_channel_id']:
            await self.bot.get_channel(db_logging_call[0]['log_channel_id']).send(msg)

    
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setlogchannel(self, ctx, given_channel_id=None):
        cleaned_channel_id = get_cleaned_id(given_channel_id) if given_channel_id else ctx.channel.id
        log_channel_exists = db_gateway().get('guild_info', params={'guild_id': ctx.author.guild.id})
        if bool(log_channel_exists):
            if log_channel_exists[0]['log_channel_id'] != cleaned_channel_id:
                db_gateway().update('guild_info', set_params={'log_channel_id': cleaned_channel_id}, where_params={'guild_id': ctx.author.guild.id})
                mention_log_channel = self.bot.get_channel(cleaned_channel_id).mention
                await ctx.channel.send(f"Logging channel has been set to {mention_log_channel}")
                await self.send_to_log_channel(ctx.author.guild.id, f"{ctx.author.mention} has set this channel as the logging channel")
            else:
                await ctx.channel.send("Logging channel already set to this channel")
        else:
            db_gateway().insert('guild_info', params={'guild_id': ctx.author.guild.id, 'log_channel_id': cleaned_channel_id})
            mention_log_channel = self.bot.get_channel(cleaned_channel_id).mention
            await ctx.channel.send(f"Logging channel has been set to {mention_log_channel}")
            await self.send_to_log_channel(ctx.author.guild.id, f"{ctx.author.mention} has set this channel as the logging channel")


    @commands.command()
    @commands.has_permissions(administrator=True)
    async def getlogchannel(self, ctx):
        log_channel_exists = db_gateway().get('guild_info', params={'guild_id': ctx.author.guild.id})

        if log_channel_exists[0]['log_channel_id']:
            mention_log_channel = self.bot.get_channel(log_channel_exists[0]['log_channel_id']).mention
            await ctx.channel.send(f"Logging channel is set to {mention_log_channel}")
        else:
            await ctx.channel.send("Logging channel has not been set")


    @commands.command()
    @commands.has_permissions(administrator=True)
    async def removelogchannel(self, ctx):
        log_channel_exists = db_gateway().get('guild_info', params={'guild_id': ctx.author.guild.id})

        if log_channel_exists[0]['log_channel_id']:
            db_gateway().update('guild_info', set_params={'log_channel_id': 'NULL'}, where_params={'guild_id': ctx.author.guild.id})
            await ctx.channel.send("Log channel has been removed")
        else:
            await ctx.channel.send("Log channel has not been set")


    
def setup(bot):
    bot.add_cog(LogChannelCog(bot))