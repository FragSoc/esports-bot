import toml
from discord.ext import commands
from ..db_gateway import db_gateway
from ..base_functions import get_cleaned_id
from ..base_functions import send_to_log_channel


class DefaultRoleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.STRINGS = toml.load("../user_strings.toml")["default_role"]

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setdefaultrole(self, ctx, given_role_id=None):
        cleaned_role_id = get_cleaned_id(
            given_role_id) if given_role_id else False
        if cleaned_role_id:
            db_gateway().update('guild_info', set_params={
                'default_role_id': cleaned_role_id}, where_params={'guild_id': ctx.author.guild.id})
            await ctx.channel.send(self.STRINGS['default_role_set'].format(role_id=cleaned_role_id))
            default_role = ctx.author.guild.get_role(cleaned_role_id)
            await send_to_log_channel(
                self, 
                ctx.author.guild.id, 
                self.STRINGS['default_role_set_log'].format(author=ctx.author.mention, role_mention=default_role.mention)
            )
        else:
            await ctx.channel.send(self.STRINGS['default_role_set_missing_params'])

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def getdefaultrole(self, ctx):
        default_role_exists = db_gateway().get(
            'guild_info', params={'guild_id': ctx.author.guild.id})

        if default_role_exists[0]['default_role_id']:
            await ctx.channel.send(self.STRINGS['default_role_get'].format(role_id=default_role_exists[0]['default_role_id']))
        else:
            await ctx.channel.send(self.STRINGS['default_role_missing'])

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def removedefaultrole(self, ctx):
        default_role_exists = db_gateway().get(
            'guild_info', params={'guild_id': ctx.author.guild.id})

        if default_role_exists[0]['default_role_id']:
            db_gateway().update('guild_info', set_params={
                'default_role_id': 'NULL'}, where_params={'guild_id': ctx.author.guild.id})
            await ctx.channel.send(self.STRINGS['default_role_removed'])
            await send_to_log_channel(self, ctx.author.guild.id, self.STRINGS['default_role_removed_log'].format(author_mention=ctx.author.mention))
        else:
            await ctx.channel.send(self.STRINGS['default_role_missing'])


def setup(bot):
    bot.add_cog(DefaultRoleCog(bot))
