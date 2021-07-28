from discord.ext import commands
from esportsbot.db_gateway import DBGatewayActions
from esportsbot.models import Guild_info
from esportsbot.base_functions import channel_id_from_mention, send_to_log_channel


class LogChannelCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.STRINGS = bot.STRINGS["logging"]

    @commands.command(
        name="setlogchannel",
        usage="<channel_id> or <@channel>",
        help="Sets the server logging channel for bot actions"
    )
    @commands.has_permissions(administrator=True)
    async def setlogchannel(self, ctx, given_channel_id=None):
        cleaned_channel_id = channel_id_from_mention(given_channel_id) if given_channel_id else ctx.channel.id
        guild = DBGatewayActions().get(Guild_info, guild_id=ctx.author.guild.id)
        if not guild:
            db_item = Guild_info(guild_id=ctx.guild.id, log_channel_id=cleaned_channel_id)
            DBGatewayActions().create(db_item)
            await ctx.channel.send(self.STRINGS["channel_set"].format(channel_id=cleaned_channel_id))
            await send_to_log_channel(
                self,
                ctx.author.guild.id,
                self.STRINGS["channel_set_notify_in_channel"].format(author_mention=ctx.author.mention),
            )
            return

        current_log_channel_id = guild.log_channel_id
        if current_log_channel_id == cleaned_channel_id:
            await ctx.channel.send(self.STRINGS["channel_set_already"])
            return

        guild.log_channel_id = cleaned_channel_id
        DBGatewayActions().update(guild)
        await ctx.channel.send(self.STRINGS["channel_set"].format(channel_id=cleaned_channel_id))
        await send_to_log_channel(
            self,
            ctx.author.guild.id,
            self.STRINGS["channel_set_notify_in_channel"].format(author_mention=ctx.author.mention),
        )

    @commands.command(name="getlogchannel", usage="", help="Gets the server logging channel for bot actions")
    @commands.has_permissions(administrator=True)
    async def getlogchannel(self, ctx):
        guild = DBGatewayActions().get(Guild_info, guild_id=ctx.author.guild.id)
        if not guild:
            await ctx.channel.send(self.STRINGS["channel_get_notfound"])
            return

        if guild.log_channel_id:
            await ctx.channel.send(self.STRINGS["channel_get"].format(channel_id=guild.log_channel_id))
        else:
            await ctx.channel.send(self.STRINGS["channel_get_notfound"])

    @commands.command(name="removelogchannel", usage="", help="Removes the server logging channel for bot actions")
    @commands.has_permissions(administrator=True)
    async def removelogchannel(self, ctx):
        guild = DBGatewayActions().get(Guild_info, guild_id=ctx.author.guild.id)
        if not guild:
            await ctx.channel.send(self.STRINGS["channel_get_notfound"])
            return

        if guild.log_channel_id:
            guild.log_channel_id = None
            DBGatewayActions().update(guild)
            await ctx.channel.send(self.STRINGS["channel_removed"])
        else:
            await ctx.channel.send(self.STRINGS["channel_get_notfound"])


def setup(bot):
    bot.add_cog(LogChannelCog(bot))
