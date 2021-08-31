from discord.ext import commands
from esportsbot.base_functions import role_id_from_mention
from esportsbot.db_gateway import DBGatewayActions
from esportsbot.models import Guild_info, Default_roles
from esportsbot.base_functions import role_id_from_mention


class DefaultRoleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.STRINGS = bot.STRINGS["default_role"]

    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = DBGatewayActions().get(Guild_info, guild_id=member.guild.id)
        if not guild:
            return
        # Get all the default role for the server from database
        guild_default_roles = DBGatewayActions().list(Default_roles, guild_id=member.guild.id)
        # Check to see if any roles exist
        if guild_default_roles:
            # Create list of roles from database response
            apply_roles = [member.guild.get_role(role.role_id) for role in guild_default_roles]
            # Add all the roles to the user, we don't check if they're valid as we do this on input
            await member.add_roles(*apply_roles)
            await self.bot.adminLog(
                None,
                {
                    "Cog":
                    str(type(self)),
                    "Message":
                    self.STRINGS['default_role_join'].format(
                        member_name=member.mention,
                        role_ids=(' '.join(f'<@&{x.id}>' for x in apply_roles))
                    )
                },
                guildID=member.guild.id
            )
        else:
            await self.bot.adminLog(
                None,
                {
                    "Cog": str(type(self)),
                    "Message": self.STRINGS['default_role_join_no_role'].format(member_name=member.mention)
                },
                guildID=member.guild.id
            )

    @commands.command(name="setdefaultroles")
    @commands.has_permissions(administrator=True)
    async def setdefaultroles(self, ctx, *, args: str):
        role_list = args.split(" ")
        if len(role_list) == 0:
            await ctx.channel.send(self.STRINGS['default_roles_set_empty'])
        else:
            checked_roles = []
            checking_error = False
            # Loop through the roles to check the input formatting is correct and that roles exist
            for role in role_list:
                try:
                    # Clean the inputted role to just the id
                    cleaned_role_id = role_id_from_mention(role)
                    # Obtain role object from the guild to check it exists
                    role_obj = ctx.author.guild.get_role(cleaned_role_id)
                    # Add role to array to add post checks
                    checked_roles.append(cleaned_role_id)
                except Exception as err:
                    print(err)
                    checking_error = True
            if not checking_error:
                for role in checked_roles:
                    DBGatewayActions().create(Default_roles(guild_id=ctx.author.guild.id, role_id=role))
                await ctx.channel.send(self.STRINGS['default_roles_set'].format(roles=args))
                await self.bot.adminLog(
                    ctx.message,
                    {
                        "Cog": str(type(self)),
                        "Message": self.STRINGS['default_roles_set_log'].format(author_mention=ctx.author.mention,
                                                                                roles=args)
                    }
                )
            else:
                await ctx.channel.send(self.STRINGS['default_roles_set_error'])

    @commands.command(name="getdefaultroles")
    @commands.has_permissions(administrator=True)
    async def getdefaultroles(self, ctx):
        # Get all the default role for the server from database
        guild_default_roles = DBGatewayActions().list(Default_roles, guild_id=ctx.author.guild.id)
        # Check to see if any roles exist
        if guild_default_roles:
            # Create list of roles from database response
            apply_roles = [ctx.author.guild.get_role(role.role_id) for role in guild_default_roles]
            # Return all the default roles to the user
            await ctx.channel.send(
                self.STRINGS['default_role_get'].format(role_ids=(' '.join(f'<@&{x.id}>' for x in apply_roles)))
            )
        else:
            await ctx.channel.send(self.STRINGS['default_role_missing'])

    @commands.command(name="removedefaultroles")
    @commands.has_permissions(administrator=True)
    async def removedefaultroles(self, ctx):
        # Get all the default role for the server from database
        guild_default_roles = DBGatewayActions().list(Default_roles, guild_id=ctx.author.guild.id)
        # Check to see if any roles exist
        if guild_default_roles:
            for default_role in guild_default_roles:
                # Remove the current role
                DBGatewayActions().delete(default_role)
            # Return a response to the user
            await ctx.channel.send(self.STRINGS['default_role_removed'])
            await self.bot.adminLog(
                ctx.message,
                {
                    "Cog": str(type(self)),
                    "Message": self.STRINGS['default_role_removed_log'].format(author_mention=ctx.author.mention)
                }
            )
        else:
            await ctx.channel.send(self.STRINGS['default_role_missing'])


def setup(bot):
    bot.add_cog(DefaultRoleCog(bot))
