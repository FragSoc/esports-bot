from discord.ext import commands
from esportsbot.base_functions import send_to_log_channel


class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.STRINGS = bot.STRINGS["admin"]

    @commands.command(
        name="clear_messages",
        aliases=['cls',
                 'purge',
                 'delete',
                 'Cls',
                 'Purge',
                 'Delete'],
        usage="<number_of_messages>",
        help="Clears the specified number of messages from the channel. Default value of 5."
    )
    @commands.has_permissions(manage_messages=True)
    async def clear_messages(self, ctx, amount=5):
        await ctx.channel.purge(limit=int(amount) + 1)
        await send_to_log_channel(
            self,
            ctx.author.guild.id,
            self.STRINGS['channel_cleared'].format(author_mention=ctx.author.mention,
                                                   message_amount=amount)
        )

    @commands.command(
        name="members",
        aliases=['Members'],
        usage="",
        help="Calculates the number of members in the current server"
    )
    @commands.has_permissions(manage_messages=True)
    async def members(self, ctx):
        await ctx.channel.send(self.STRINGS['members'].format(member_count=ctx.guild.member_count))


def setup(bot):
    bot.add_cog(AdminCog(bot))
