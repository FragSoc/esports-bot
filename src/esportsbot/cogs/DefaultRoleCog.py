from discord.ext import commands, tasks
from discord import Embed
from esportsbot.db_gateway import DBGatewayActions
from esportsbot.models import GuildInfo, DefaultRoles
from esportsbot.base_functions import role_id_from_mention


class DefaultRoleCog(commands.Cog):
    """
    This module enables the functionality to automatically assign roles to new users when they join a server.
    """
    def __init__(self, bot):
        self.bot = bot
        self.pending_members = []
        self.STRINGS = bot.STRINGS["default_role"]

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """
        When a member joins the server, get the currently set list of default roles and give the new user that set of roles.
        :param member: The member that joined the server.
        """
        self.pending_members.append(member)
        if not self.check_pending_members.is_running() or self.check_pending_members.is_being_cancelled():
            self.check_pending_members.start()

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """
        When a member leaves, ensure that they are not a pending member, and if they were, remove them from the list.
        :param member: The member that left.
        """
        if member in self.pending_members:
            self.pending_members.remove(member)

    @tasks.loop(seconds=1)
    async def check_pending_members(self):
        """
        Check the members that have recently joined to see if they accepted the rules. If they have, give the roles. If the
        list of pending members is empty, this check won't run.
        """
        if not self.pending_members:
            self.check_pending_members.cancel()
            self.check_pending_members.stop()
            return

        members_to_remove = []

        for member in self.pending_members:
            if not member.pending:
                await self.apply_roles(member)
                members_to_remove.append(member)

        for member in members_to_remove:
            self.pending_members.remove(member)

    async def apply_roles(self, member):
        # Get all the default role for the server from database
        guild_default_roles = DBGatewayActions().list(DefaultRoles, guild_id=member.guild.id)
        # Check to see if any roles exist
        if guild_default_roles:
            # Create list of roles from database response
            apply_roles = [member.guild.get_role(role.role_id) for role in guild_default_roles]
            # Add all the roles to the user, we don't check if they're valid as we do this on input
            await member.add_roles(*apply_roles)
            await self.bot.admin_log(
                guild_id=member.guild.id,
                actions={
                    "Cog":
                    self.__class__.__name__,
                    "Action":
                    self.STRINGS["default_role_join"].format(
                        member_name=member.mention,
                        role_ids=" ".join(x.mention for x in apply_roles)
                    )
                }
            )
        else:
            await self.bot.admin_log(
                guild_id=member.guild.id,
                actions={
                    "Cog": self.__class__.__name__,
                    "Action": self.STRINGS["default_role_join_no_role"].format(member_name=member.mention)
                }
            )

    @commands.command(name="setdefaultroles")
    @commands.has_permissions(administrator=True)
    async def setdefaultroles(self, ctx, *, args: str):
        """
        Set the list of default roles. There must be a space between each role mention.
        :param ctx: The context of the command.
        :param args: The list of roles to set as default roles.
        """
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
                    ctx.author.guild.get_role(cleaned_role_id)
                    # Add role to array to add post checks
                    checked_roles.append(cleaned_role_id)
                except Exception as err:
                    print(err)
                    checking_error = True
            if not checking_error:
                for role in checked_roles:
                    DBGatewayActions().create(DefaultRoles(guild_id=ctx.author.guild.id, role_id=role))
                await ctx.channel.send(self.STRINGS['default_roles_set'].format(roles=args))
                await self.bot.admin_log(
                    responsible_user=ctx.author,
                    guild_id=ctx.guild.id,
                    actions={
                        "Cog": self.__class__.__name__,
                        "command": ctx.message,
                        "Message": self.STRINGS["default_roles_set_log"].format(author_mention=ctx.author.mention,
                                                                                roles=args)
                    }
                )
            else:
                await ctx.channel.send(self.STRINGS['default_roles_set_error'])

    @commands.command(name="getdefaultroles")
    @commands.has_permissions(administrator=True)
    async def getdefaultroles(self, ctx):
        """
        Get the current list of default roles.
        :param ctx: The context of the command.
        """
        # Get all the default role for the server from database
        guild_default_roles = DBGatewayActions().list(DefaultRoles, guild_id=ctx.author.guild.id)
        # Check to see if any roles exist
        if guild_default_roles:
            # Create list of roles from database response
            apply_roles = [ctx.author.guild.get_role(role.role_id) for role in guild_default_roles]
            # Return all the default roles to the user
            await ctx.channel.send(
                embed=Embed(title=self.STRINGS['default_role_get'], description="— "+('\n— '.join(f'<@&{x.id}>' for x in apply_roles)))
            )
        else:
            await ctx.channel.send(self.STRINGS['default_role_missing'])

    @commands.command(name="removedefaultroles")
    @commands.has_permissions(administrator=True)
    async def removedefaultroles(self, ctx):
        """
        Remove all of the currently set default roles in the current server.
        :param ctx: The context of the command.
        """
        # Get all the default role for the server from database
        guild_default_roles = DBGatewayActions().list(DefaultRoles, guild_id=ctx.author.guild.id)
        # Check to see if any roles exist
        if guild_default_roles:
            for default_role in guild_default_roles:
                # Remove the current role
                DBGatewayActions().delete(default_role)
            # Return a response to the user
            await ctx.channel.send(self.STRINGS['default_role_removed'])
            await self.bot.admin_log(
                responsible_user=ctx.author,
                guild_id=ctx.guild.id,
                actions={
                    "Cog": self.__class__.__name__,
                    "command": ctx.message,
                    "Message": self.STRINGS["default_role_removed_log"].format(author_mention=ctx.author.mention)
                }
            )
        else:
            await ctx.channel.send(self.STRINGS['default_role_missing'])


def setup(bot):
    bot.add_cog(DefaultRoleCog(bot))
