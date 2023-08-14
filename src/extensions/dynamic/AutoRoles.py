import logging
from typing import List

from discord import Color, Embed, Interaction, Member, Role
from discord.app_commands import (Transform, command, default_permissions, describe, guild_only, rename)
from discord.ext.commands import Bot, GroupCog

from client import EsportsBot
from common.discord import RoleListTransformer, get_role
from common.io import load_cog_toml
from database.gateway import DBSession
from database.models import AutoRolesConfig

COG_STRINGS = load_cog_toml(__name__)


@default_permissions(administrator=True)
@guild_only()
class AutoRoles(GroupCog, name=COG_STRINGS["roles_group_name"]):

    def __init__(self, bot: EsportsBot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"{__name__} has been added as a Cog")

    @GroupCog.listener()
    async def on_member_join(self, member: Member):
        if not member.pending:
            await self.assign_roles(member)

    @GroupCog.listener()
    async def on_member_update(self, before: Member, after: Member):
        if before.pending and not after.pending:
            self.assign_roles(after)

    async def assign_roles(self, member: Member):
        guild_roles = DBSession.list(AutoRolesConfig, guild_id=member.guild.id)

        parsed_roles = []
        if guild_roles:
            parsed_roles = [member.guild.get_role(x.role_id) for x in guild_roles]
            await member.add_roles(*parsed_roles)

        self.logger.info(
            f"{self.bot.logger_prefix}[{member.guild.id}] Member ({member.mention}) joined and received the following roles: [{','.join([x.mention for x in parsed_roles])}]"
        )

    @command(name=COG_STRINGS["roles_set_list_name"], description=COG_STRINGS["roles_set_list_description"])
    @describe(roles=COG_STRINGS["roles_set_list_param_describe"])
    @rename(roles=COG_STRINGS["roles_set_list_param_rename"])
    async def set_guild_roles(self, interaction: Interaction, roles: Transform[List[Role], RoleListTransformer]):
        """The command used to set the list of roles to give to members when the join the guild/server.

        If there are one or more valid roles given in the `roles` parameter,
        any previously configured roles to be applied will be overridden.

        Args:
            interaction (Interaction): The interaction that triggered the command.
            roles (Transform[List[Role], RoleListTransformer]): One or many roles mentioned.
            Do not need to be separated with a delimiter.
        """
        await interaction.response.defer(ephemeral=True)

        initial_entries = DBSession.list(AutoRolesConfig, guild_id=interaction.guild.id)

        successful_roles = []
        for role in roles:
            if role.is_assignable:
                db_entry = AutoRolesConfig(guild_id=interaction.guild.id, role_id=role.id)
                if db_entry in initial_entries:
                    initial_entries.remove(db_entry)
                else:
                    DBSession.create(db_entry)
                successful_roles.append(role)

        if len(successful_roles) == 0:
            await interaction.followup.send(COG_STRINGS["roles_set_warn_empty"], ephemeral=True)
            return False
        else:
            for entry in initial_entries:
                DBSession.delete(entry)

        formatted_string = "\n".join([f"• {x.mention}" for x in successful_roles])

        response_embed = Embed(
            title=COG_STRINGS["roles_set_success_title"],
            description=COG_STRINGS["roles_set_success_description"].format(roles=formatted_string),
            color=Color.random()
        )

        self.logger.info(
            f"{self.bot.logging_prefix}[{interaction.guild.id}] {interaction.user.mention} updated the list of automatically applied roles: [{','.join([x.mention for x in successful_roles])}]"
        )
        await interaction.followup.send(embed=response_embed, ephemeral=False)
        return True

    @command(name=COG_STRINGS["roles_add_role_name"], description=COG_STRINGS["roles_add_role_description"])
    @describe(role=COG_STRINGS["roles_add_role_param_describe"])
    @rename(role=COG_STRINGS["roles_add_role_param_rename"])
    async def add_guild_role(self, interaction: Interaction, role: Role):
        """The command that adds a role to the list of roles, without overriding the currently configured roles.

        Args:
            interaction (Interaction): The interaction that triggered the command.
            role (Role): The role to add.
        """
        await interaction.response.defer(ephemeral=True)

        db_entry = DBSession.get(AutoRolesConfig, guild_id=role.guild.id, role_id=role.id)

        if db_entry:
            await interaction.followup.send(COG_STRINGS["roles_add_role_warn_already_added"], ephemeral=True)
            return False

        db_entry = AutoRolesConfig(guild_id=role.guild.id, role_id=role.id)
        DBSession.create(db_entry)
        self.logger.info(
            f"{self.bot.logging_prefix}[{interaction.guild.id}] {interaction.user.mention} added {role.mention} to the list of automatically assigned roles"
        )
        await interaction.followup.send(COG_STRINGS["roles_add_role_success"].format(role=role.mention), ephemeral=True)
        return True

    @command(name=COG_STRINGS["roles_remove_role_name"], description=COG_STRINGS["roles_remove_role_description"])
    @describe(role=COG_STRINGS["roles_remove_role_param_describe"])
    @rename(role=COG_STRINGS["roles_remove_role_param_rename"])
    async def remove_guild_role(self, interaction: Interaction, role: Role):
        """The command used to remove a role from the list of currently configured roles in a given guild/server.

        Args:
            interaction (Interaction): The interaction that triggered the command.
            role (Role): The role to remove.
        """
        await interaction.response.defer(ephemeral=True)

        db_entry = DBSession.get(AutoRolesConfig, guild_id=role.guild.id, role_id=role.id)

        if not db_entry:
            await interaction.followup.send(COG_STRINGS["roles_remove_role_warn_not_added"], ephemeral=True)
            return False

        DBSession.delete(db_entry)
        self.logger.info(
            f"{self.bot.logging_prefix}[{interaction.guild.id}] {interaction.user.mention} removed {role.mention} from the list of automatically assigned roles"
        )
        await interaction.followup.send(COG_STRINGS["roles_remove_role_success"].format(role=role.mention), ephemeral=True)
        return True

    @command(name=COG_STRINGS["roles_get_list_name"], description=COG_STRINGS["roles_get_list_description"])
    async def list_guild_roles(self, interaction: Interaction):
        """The command to get the current list of roles that are configured for a given guild/server.

        Args:
            interaction (Interaction): The interaction that triggered the command.
        """
        await interaction.response.defer(ephemeral=True)

        db_items = DBSession.list(AutoRolesConfig, guild_id=interaction.guild.id)

        if not db_items:
            await interaction.followup.send(COG_STRINGS["roles_get_list_warn_no_roles"], ephemeral=True)
            return False

        fetched_roles = [await get_role(interaction.guild, x.role_id) for x in db_items]

        formatted_string = "\n".join([f"• {x.mention}" for x in fetched_roles])
        response_embed = Embed(
            title=COG_STRINGS["roles_get_list_success_title"],
            description=COG_STRINGS["roles_get_list_success_description"].format(roles=formatted_string),
            color=Color.random()
        )
        await interaction.followup.send(embed=response_embed, ephemeral=True)
        return True

    @command(name=COG_STRINGS["roles_clear_list_name"], description=COG_STRINGS["roles_clear_list_description"])
    async def clear_guild_roles(self, interaction: Interaction):
        """The command used to entirely clear the list of Roles for a given guild/server.

        Args:
            interaction (Interaction): The interaction that triggered the command.
        """
        db_items = DBSession.list(AutoRolesConfig, interaction.guild.id)

        for item in db_items:
            DBSession.delete(item)

        self.logger.info(
            f"{self.bot.logging_prefix}[{interaction.guild.id}] {interaction.user.mention} cleared the list of automatically assigned roles"
        )
        await interaction.followup.send(COG_STRINGS["roles_clear_list_success"], ephemeral=True)
        return True


async def setup(bot: Bot):
    await bot.add_cog(AutoRoles(bot))
