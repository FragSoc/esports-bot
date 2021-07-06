from discord.ext import commands
from esportsbot.db_gateway import DBGatewayActions
from esportsbot.models import Guild_info
from esportsbot.base_functions import role_id_from_mention, send_to_log_channel


class DefaultRoleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.STRINGS = bot.STRINGS["default_role"]

    @commands.Cog.listener
    async def on_member_join(self, member):
        guild = DBGatewayActions().get(Guild_info, guild_id=member.guild.id)
        default_role_exists = guild.default_role_id is not None

        if default_role_exists:
            default_role = member.guild.get_role(guild.default_role_id)
            await member.add_roles(default_role)
            await send_to_log_channel(
                    self,
                    member.guild.id,
                    f"{member.mention} has joined the server and received the {default_role.mention} role"
            )
        else:
            await send_to_log_channel(self, member.guild.id, f"{member.mention} has joined the server")

    @commands.command(
        name="setdefaultrole",
        usage="<role_id> or <@role>",
        help="Sets the role that the server gives to members when they join the server"
    )
    @commands.has_permissions(administrator=True)
    async def setdefaultrole(self, ctx, given_role_id=None):
        cleaned_role_id = role_id_from_mention(given_role_id) if given_role_id else False
        if cleaned_role_id:
            guild = DBGatewayActions().get(Guild_info, guild_id=ctx.author.guild.id)
            guild.default_role_id = cleaned_role_id
            DBGatewayActions().update(guild)
            await ctx.channel.send(self.STRINGS['default_role_set'].format(role_id=cleaned_role_id))
            default_role = ctx.author.guild.get_role(cleaned_role_id)
            await send_to_log_channel(
                self,
                ctx.author.guild.id,
                self.STRINGS['default_role_set_log'].format(author=ctx.author.mention,
                                                            role_mention=default_role.mention)
            )
        else:
            await ctx.channel.send(self.STRINGS['default_role_set_missing_params'])

    @commands.command(
        name="getdefaultrole",
        usage="",
        help="Gets the role that the server gives to members when they join the server"
    )
    @commands.has_permissions(administrator=True)
    async def getdefaultrole(self, ctx):
        guild = DBGatewayActions().get(Guild_info, guild_id=ctx.author.guild.id)
        default_role_exists = guild.default_role_id is not None

        if default_role_exists:
            await ctx.channel.send(self.STRINGS['default_role_get'].format(role_id=guild.default_role_id))
        else:
            await ctx.channel.send(self.STRINGS['default_role_missing'])

    @commands.command(
        name="removedefaultrole",
        usage="",
        help="Removes the role that the server gives to members when they join the server"
    )
    @commands.has_permissions(administrator=True)
    async def removedefaultrole(self, ctx):
        guild = DBGatewayActions().get(Guild_info, guild_id=ctx.author.guild.id)
        default_role_exists = guild.default_role_id is not None

        if default_role_exists:
            guild.default_role_id = None
            DBGatewayActions().update(guild)
            await ctx.channel.send(self.STRINGS['default_role_removed'])
            await send_to_log_channel(
                self,
                ctx.author.guild.id,
                self.STRINGS['default_role_removed_log'].format(author_mention=ctx.author.mention)
            )
        else:
            await ctx.channel.send(self.STRINGS['default_role_missing'])


def setup(bot):
    bot.add_cog(DefaultRoleCog(bot))
