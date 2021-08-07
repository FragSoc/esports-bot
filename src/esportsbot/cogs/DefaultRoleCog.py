import toml
from discord.ext import commands
from esportsbot.db_gateway import DBGatewayActions
from esportsbot.models import Guild_info, Default_roles
from esportsbot.base_functions import role_id_from_mention, send_to_log_channel


class DefaultRoleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.STRINGS = bot.STRINGS["default_role"]

    @commands.command(
        name="setdefaultroles",
        usage="<@role> <@role> <@role> ...",
        help="Sets the roles that the server gives to members when they join the server"
    )
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
            else:
                await ctx.channel.send(self.STRINGS['default_roles_set_error'])

    @commands.command(
        name="getdefaultroles",
        usage="",
        help="Gets the roles that the server gives to members when they join the server"
    )
    @commands.has_permissions(administrator=True)
    async def getdefaultroles(self, ctx):
        # Get all the default role for the server from database
        guild_default_roles = DBGatewayActions().list(Default_roles, guild_id=ctx.author.guild.id)
        # Check to see if any roles exist
        if guild_default_roles:
            # Create list of roles from database response
            apply_roles = [ctx.author.guild.get_role(role.role_id) for role in guild_default_roles]
            # Return all the default roles to the user
            await ctx.channel.send(self.STRINGS['default_role_get'].format(role_ids=(' '.join(f'<@&{x.id}>' for x in apply_roles))))
        else:
            await ctx.channel.send(self.STRINGS['default_role_missing'])

    @commands.command(
        name="removedefaultroles",
        usage="",
        help="Removes the roles that the server gives to members when they join the server"
    )
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
        else:
            await ctx.channel.send(self.STRINGS['default_role_missing'])


def setup(bot):
    bot.add_cog(DefaultRoleCog(bot))
