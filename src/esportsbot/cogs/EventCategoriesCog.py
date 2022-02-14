import asyncio
import logging
from collections import defaultdict
from enum import IntEnum

from discord import Forbidden, PermissionOverwrite, Role
from discord.ext import commands

from esportsbot.DiscordReactableMenus.EventReactMenu import EventReactMenu
from esportsbot.DiscordReactableMenus.ExampleMenus import ActionConfirmationMenu
from esportsbot.DiscordReactableMenus.reactable_lib import get_menu
from esportsbot.db_gateway import DBGatewayActions
from esportsbot.lib.discordUtil import get_attempted_arg
from esportsbot.models import EventCategories, DefaultRoles

denied_perms = PermissionOverwrite(read_messages=False, send_messages=False, connect=False, view_channel=False)
read_only_perms = PermissionOverwrite(read_messages=True, send_messages=False, connect=False, view_channel=True)
writable_perms = PermissionOverwrite(read_messages=True, send_messages=True, connect=True, view_channel=True)
SIGN_IN_EMOJI = "✅"
SIGN_IN_DESCRIPTION = "Welcome to {}, react to this message to join the event so that you " \
                      "receive notifications for when things are happening!"

GENERAL_CHANNEL_SUFFIX = "general-chat"
SIGN_IN_CHANNEL_SUFFIX = "sign-in"
VOICE_CHANNEL_SUFFIX = "VC"


class RoleTypeEnum(IntEnum):
    DEFAULT = 0  # The Default role
    SHARED = 1  # The Shared role users receive when joining the server
    EVENT = 2  # The Event role
    TOP = 3  # The Top role the bot has


class EventCategoriesCog(commands.Cog):
    """
    An event category is used to manage a group of event channels. When an event is created, it creates a Discord Category
    and inside the category it creates a sign-in menu/channel, a general event channel and a general event voice channel.

    This module implements the ability to create and manage events, all the commands requiring administrator privileges to run.
    """
    def __init__(self, bot):
        self.bot = bot
        self.user_strings = bot.STRINGS["event_categories"]
        self.db = DBGatewayActions()
        self.event_menus = defaultdict(dict)
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Loaded {__name__}!")

    @commands.Cog.listener()
    async def on_ready(self):
        """
        When bot discord client is ready and has logged into the discord API, this function runs and is used to load and
        initialise events, which include initialising the sign-in menus used to get the event roles.
        """
        await self.load_event_menus()
        self.logger.info(f"{__name__} is now ready!")

    async def load_event_menus(self):
        """
        Loads any event menus saved in the DB for all guilds .
        """
        bot_guilds = [x.id for x in self.bot.guilds]

        to_load = []

        for guild in bot_guilds:
            to_load.append(self.load_events_in_guild(guild))

        loaded_guilds = await asyncio.gather(*to_load)

        self.event_menus = dict(zip(bot_guilds, loaded_guilds))

    async def load_events_in_guild(self, guild_id):
        """
        Loads any event menus saved in the DB for a specific guild .
        :param guild_id: The ID of the guild to load the event menus of .
        :return: A Dictionary of the event menus in the guild .
        """
        raw_events = self.db.list(EventCategories, guild_id=guild_id)

        to_load = []

        for event in raw_events:
            event_menu = event.event_menu
            to_load.append(EventReactMenu.from_dict(self.bot, event_menu))

        loaded_events = await asyncio.gather(*to_load)

        # Any menu that has failed to load will not have been initialised to a menu and will still be a dict,
        # so should be deleted from the DB.
        events = {}
        for event in loaded_events:
            if isinstance(event, dict):
                self.delete_event_data(event.get("guild_id"), event.get("id"))
            elif isinstance(event, EventReactMenu):
                events[event.id] = event

        return events

    async def send_current_events(self, context: commands.Context):
        """
        Sends a list of the currently active events in a guild .
        :param context: The context of the command .
        """
        guild_events = self.event_menus[context.guild.id]
        events = str([str(x.title) for x in guild_events.values()]).replace("[", "").replace("]", "")
        if len(events) > 0:
            reply = self.user_strings["unrecognised_event"].format(events=events)
        else:
            reply = self.user_strings["no_events"]
        await context.reply(reply)

    def get_event_by_name(self, guild_id, event_name):
        """
        Gets an event menu given a guild and the event's name .
        :param guild_id: The ID of the guild to find the event in .
        :param event_name: The name of the event to find the menu of .
        :return: An event menu if there is one with that name in the guild .
        """
        guild_events = self.event_menus[guild_id]
        if event_name:
            for event_id in guild_events:
                if event_name.lower() in guild_events.get(event_id).title.lower():
                    return guild_events.get(event_id)
        else:
            # IF the event name given is None, try to find the latest menu.
            return get_menu(guild_events, event_name)

    def update_event(self, guild_id, event_menu):
        """
        Updates the DB with the latest event data .
        :param guild_id: The ID of the guild the event is in .
        :param event_menu: The Reaction Menu instance of the event that has been updated .
        """
        db_item = self.db.get(EventCategories, guild_id=guild_id, event_id=event_menu.id)
        db_item.event_menu = event_menu.to_dict()
        self.db.update(db_item)

    def delete_event_data(self, guild_id, event_id):
        """
        Deletes an event menu's data from the DB.
        :param guild_id: The ID of the guild where the event is in .
        :param event_id: The ID of the event in the guild .
        """
        db_item = self.db.get(EventCategories, guild_id=guild_id, event_id=event_id)
        self.db.delete(db_item)

    @commands.group(name="events", invoke_without_command=True)
    async def event_command_group(self, context: commands.context):
        """
        The command group used to make all commands sub-commands .
        :param context: The context of the command .
        """
        pass

    @event_command_group.command(name="create-event")
    @commands.has_permissions(administrator=True)
    async def create_event(self, context: commands.Context, event_name: str, shared_role: Role = None):
        """
        Creates a new event with the given name and using the shared role in the server to stop users from seeing the
        event early .
        :param context: The context of the command .
        :param event_name: The name of the event to create .
        :param shared_role: The shared role that all users have .
        """
        self.logger.info(f"Creating a new Event with name {event_name}")
        audit_reason = "Done with `create-event` command"

        if not shared_role:
            db_data = self.db.get(DefaultRoles, guild_id=context.guild.id)
            if not db_data or not db_data.role_id:
                shared_role = context.guild.default_role
            else:
                shared_role = context.guild.get_role(db_data.role_id)
                if not shared_role:
                    shared_role = context.guild.default_role

        guild_events = self.event_menus[context.guild.id]

        # Check if an event already exists with the given name.
        for event_id in guild_events:
            if event_name.lower() in guild_events.get(event_id).title.lower():
                self.logger.warning(f"There is already an event with the name {event_name} in {context.guild.name}")
                await context.reply(self.user_strings["event_exists"].format(event_name=event_name))
                return

        event_role = await context.guild.create_role(name=event_name, reason=audit_reason)

        category_overwrites = {
            context.me: writable_perms,
            event_role: writable_perms,
            shared_role: denied_perms,
            context.guild.default_role: denied_perms
        }

        signin_overwrites = {
            context.me: writable_perms,
            event_role: read_only_perms,
            shared_role: denied_perms,
            context.guild.default_role: denied_perms
        }

        # Create the channels for the event:
        event_category = await context.guild.create_category(
            name=event_name,
            overwrites=category_overwrites,
            reason=audit_reason
        )
        event_sign_in_channel = await event_category.create_text_channel(
            name=f"{event_name} {SIGN_IN_CHANNEL_SUFFIX}",
            sync_permissions=False,
            overwrites=signin_overwrites,
            reason=audit_reason
        )
        await event_category.create_text_channel(
            name=f"{event_name} {GENERAL_CHANNEL_SUFFIX}",
            sync_permissions=True,
            reason=audit_reason
        )
        await event_category.create_voice_channel(
            name=f"{event_name} {VOICE_CHANNEL_SUFFIX}",
            sync_permissions=True,
            reason=audit_reason
        )

        # Create the sign-in message:
        event_menu = EventReactMenu(
            shared_role=shared_role,
            event_role=event_role,
            title=event_name,
            description=SIGN_IN_DESCRIPTION.format(event_name),
            auto_enable=False
        )

        event_menu.add_option(SIGN_IN_EMOJI, event_role)

        await event_menu.finalise_and_send(self.bot, event_sign_in_channel)

        db_item = EventCategories(
            guild_id=context.guild.id,
            event_id=event_menu.id,
            event_name=event_menu.title,
            event_menu=event_menu.to_dict()
        )
        self.db.create(db_item)

        self.event_menus[context.guild.id][event_menu.id] = event_menu
        self.logger.info(f"Successfully created an event with the name {event_name} in {context.guild.name}!")
        await context.reply(
            self.user_strings["success_event"].format(
                event_name=event_name,
                event_role_mention=event_role.mention,
                sign_in_menu_id=event_menu.id,
                sign_in_channel_mention=event_sign_in_channel.mention,
                shared_role_name=shared_role.name,
                command_prefix=self.bot.command_prefix
            )
        )

    @event_command_group.command(name="open-event")
    @commands.has_permissions(administrator=True)
    async def open_event(self, context: commands.Context, event_name: str):
        """
        Opens the sign-in channel for the event so that users with the shared role given in the
        create-event command can see it .
        :param context: The context of the command .
        :param event_name: The name of the event to open .
        """
        self.logger.info(f"Attempting to open event with name {event_name}, if this is none, searching for latest event menu")

        audit_reason = "Done with `open-event` command"

        event_menu = self.get_event_by_name(context.guild.id, event_name)

        # If there no event with the given name, exit:
        if not event_menu:
            self.logger.warning(f"There is no event to open with the name {event_name} in {context.guild.name}")
            await self.send_current_events(context)
            return

        await event_menu.enable_menu(self.bot)
        self.update_event(context.guild.id, event_menu)

        signin_channel = event_menu.message.channel
        current_perms = signin_channel.overwrites
        current_perms[event_menu.shared_role] = read_only_perms
        await signin_channel.edit(overwrites=current_perms, reason=audit_reason)

        self.logger.info(f"Successfully opened an event with the name {event_name} in {context.guild.name}")
        await context.reply(
            self.user_strings["success_channel"].format(
                channel_id=event_menu.message.channel.id,
                role_name=event_menu.shared_role.name
            )
        )
        return

    @event_command_group.command(name="close-event")
    @commands.has_permissions(administrator=True)
    async def close_event(self, context: commands.Context, event_name: str):
        """
        Closes all the channels so that no users can see any of the event channels,
        including the general, voice and sign in channels .
        :param context: The context of the command .
        :param event_name:  The name of the event to close .
        """
        self.logger.info(f"Attempting to close event with name {event_name}, if this is none, searching for latest event menu")

        audit_reason = "Done with `close-event` command"

        event_menu = self.get_event_by_name(context.guild.id, event_name)

        # If there no event with the given name, exit:
        if not event_menu:
            self.logger.warning(f"There is no event to close with the name {event_name} in {context.guild.id}")
            await self.send_current_events(context)
            return

        await event_menu.disable_menu(self.bot)
        self.update_event(context.guild.id, event_menu)

        signin_channel = event_menu.message.channel
        current_perms = signin_channel.overwrites
        current_perms[event_menu.shared_role] = denied_perms
        await signin_channel.edit(overwrites=current_perms, reason=audit_reason)

        await self.remove_react_roles(context, event_menu, event_name)

        self.logger.info(f"Successfully closed an event with the name {event_name} in {context.guild.name}")
        await context.reply(self.user_strings["success_event_closed"])
        return

    @event_command_group.command(name="delete-event")
    @commands.has_permissions(administrator=True)
    async def delete_event(self, context: commands.Context, event_name: str):
        """
        Deletes an event. This includes all the channels in the category and the role created for the event .
        :param context: The context of the command .
        :param event_name: The name of the event to delete .
        """
        self.logger.info(f"Attempting to close event with name {event_name}, if this is none, searching for latest event menu")

        event_menu = self.get_event_by_name(context.guild.id, event_name)

        # If there no event with the given name, exit:
        if not event_menu:
            self.logger.warning(f"There is no event to delete with the name {event_name} in {context.guild.id}")
            await self.send_current_events(context)
            return False

        confirm_menu = ActionConfirmationMenu(title=f"Confirm that you want to delete {event_name} event", auto_enable=True)
        confirm_menu.set_confirm_func(self.confirm_delete_event, event_menu, confirm_menu, context)
        confirm_menu.set_cancel_func(self.cancel_delete_event, event_menu.title, confirm_menu, context)
        await confirm_menu.finalise_and_send(self.bot, context.channel)

    async def confirm_delete_event(self, event_menu, confirm_menu, context):
        """
        Used in the deletion confirmation reaction menu so that an admin can confirm the decision to delete an event .
        :param event_menu: The event menu that will be deleted  .
        :param confirm_menu: The menu used to confirm the decision .
        :param context: The context of the command .
        """
        audit_reason = "Done with `delete-event` command"
        event_category = event_menu.event_category
        event_role = event_menu.event_role

        # Delete all the channels in the category:
        for channel in event_category.channels:
            await channel.delete(reason=audit_reason)
        await event_category.delete(reason=audit_reason)

        await event_role.delete(reason=audit_reason)
        self.event_menus[context.guild.id].pop(event_menu.id)
        self.delete_event_data(guild_id=context.guild.id, event_id=event_menu.id)

        self.logger.info(f"Successfully deleted an event with the name {event_menu.title} in {context.guild.name}")
        await context.reply(self.user_strings["success_event_deleted"].format(event_name=event_menu.title))

        if not confirm_menu.delete_after:
            await confirm_menu.disable_menu(self.bot)

    async def cancel_delete_event(self, event_name, confirm_menu, context):
        """
        Used in the deletion confirmation reaction menu so that an admin can cancel the decision to delete an event .
        :param event_name: The name of the event that didn't get deleted .
        :param confirm_menu: The menu used to confirm the decision .
        :param context: The context of the command .
        """
        if not confirm_menu.delete_after:
            await confirm_menu.disable_menu(self.bot)

        self.logger.info(f"Deletion of {event_name} menu cancelled by {context.author.name}#{context.author.discriminator}")
        await context.reply(self.user_strings["delete_cancelled"].format(event_name=event_name))

    @staticmethod
    async def remove_react_roles(context, event_menu, event_name):
        all_members = context.guild.members
        for member in all_members:
            if event_menu.event_role in member.roles:
                await member.remove_roles(event_menu.event_role, reason=f"{event_name} Event Closed")

        reactions = event_menu.message.reactions

        for reaction in reactions:
            await reaction.clear()

    @create_event.error
    async def on_create_event_error(self, context: commands.Context, error: commands.CommandError):
        """
        The error handler for the create_event command .
        :param context: The context of the command .
        :param error: The error that occurred when the command was executed .
        """
        # This can occur if the Role given is as an ID or just invalid:
        if isinstance(error, commands.RoleNotFound):
            self.logger.warning("The argument parsed was not a Role, trying to find a role with the given value")
            arg_index = 1
            attempted_role, command_args = get_attempted_arg(context.message.content, arg_index)
            try:
                role_id = int(attempted_role)
                for role in context.guild.roles:
                    if role.id == role_id:
                        # Retry the command and parse the given role_id as an actual role object.
                        self.logger.info(f"Retrying {context.command.name} with found role: {role.name}")
                        command_args[arg_index] = role
                        await self.create_event(context, *command_args)
                        return
                raise ValueError()
            except ValueError:
                self.logger.error(f"Unable to find a role with id: {attempted_role}")
                await context.reply(self.user_strings["invalid_role"])
                return

    @create_event.error
    @open_event.error
    @close_event.error
    @delete_event.error
    async def generic_error_handler(self, context: commands.Context, error: commands.CommandError):
        """
        A more generic error handler for the rest of the commands .
        :param context: The context of the command .
        :param error: The error that occurred .
        """
        self.logger.warning(
            f"There was an error while performing the '{context.command.name}' "
            f"command: {error.__class__.__name__}"
        )
        # When the user forgets to supply required arguments.
        if isinstance(error, commands.MissingRequiredArgument):
            self.logger.warning(f"Unable to perform {context.command.name} as the command lacked sufficient arguments")
            command_name = context.command.full_parent_name + " " + context.command.name
            await context.reply(
                self.user_strings["missing_arguments"].format(prefix=self.bot.command_prefix,
                                                              command=command_name)
            )
            return

        # When the user does not have the correct permissions to perform the command.
        if isinstance(error, commands.MissingPermissions):
            permission = error.missing_perms[0].replace("_", " ").replace("guild", "server")
            self.logger.error(f"Unable to perform {context.command.name} as you lack the permissions: {permission}")
            await context.reply(self.user_strings["user_missing_perms"].format(permission=permission))
            return

        # When the bot does not have the correct permissions to perform the command.
        if isinstance(error, Forbidden):
            self.logger.error(f"Unable to perform {context.command.name} as the bot lacks permissions")
            # A list of permissions known to potentially cause issues:
            permissions = "view channel, send messages, manage channels, manage roles"
            await context.reply(self.user_strings["bot_missing_perms"].format(permissions=permissions))
            return


def setup(bot):
    bot.add_cog(EventCategoriesCog(bot))
