import toml
from discord.ext import commands
from ..db_gateway import db_gateway
from ..base_functions import channel_id_from_mention
from ..base_functions import send_to_log_channel

class LogChannelCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.STRINGS = toml.load("../user_strings.toml")["logging"]

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setlogchannel(self, ctx, given_channel_id=None):
        cleaned_channel_id = channel_id_from_mention(
            given_channel_id) if given_channel_id else ctx.channel.id
        log_channel_exists = db_gateway().get(
            'guild_info', params={'guild_id': ctx.author.guild.id})
        if bool(log_channel_exists):
            if log_channel_exists[0]['log_channel_id'] != cleaned_channel_id:
                db_gateway().update('guild_info', set_params={
                    'log_channel_id': cleaned_channel_id}, where_params={'guild_id': ctx.author.guild.id})
                await ctx.channel.send(self.STRINGS["channel_set"].format(channel_id=cleaned_channel_id))
                await send_to_log_channel(
                    self, 
                    ctx.author.guild.id, 
                    self.STRINGS["channel_set_notify_in_channel"].format(author_mention=ctx.author.mention),
                )
            else:
                await ctx.channel.send(self.STRINGS["channel_set_already"])
        else:
            db_gateway().insert('guild_info', params={
                'guild_id': ctx.author.guild.id, 'log_channel_id': cleaned_channel_id})
            await ctx.channel.send(self.STRINGS["channel_set"].format(channel_id=cleaned_channel_id))
            await send_to_log_channel(
                self, 
                ctx.author.guild.id, 
                self.STRINGS["channel_set_notify_in_channel"].format(author_mention=ctx.author.mention),
            )

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def getlogchannel(self, ctx):
        log_channel_exists = db_gateway().get(
            'guild_info', params={'guild_id': ctx.author.guild.id})

        if (channel_id := log_channel_exists[0]['log_channel_id']) is not None:
            await ctx.channel.send(self.STRINGS["channel_get"].format(channel_id=channel_id))
        else:
            await ctx.channel.send(self.STRINGS["channel_get_notfound"])

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def removelogchannel(self, ctx):
        log_channel_exists = db_gateway().get(
            'guild_info', params={'guild_id': ctx.author.guild.id})

        if log_channel_exists[0]['log_channel_id']:
            db_gateway().update('guild_info', set_params={
                'log_channel_id': 'NULL'}, where_params={'guild_id': ctx.author.guild.id})
            await ctx.channel.send(self.STRINGS["channel_removed"])
        else:
            await ctx.channel.send(self.STRINGS["channel_get_notfound"])


def setup(bot):
    bot.add_cog(LogChannelCog(bot))
