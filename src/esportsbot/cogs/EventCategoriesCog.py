import asyncio
import logging
from collections import defaultdict

from discord import Forbidden, PermissionOverwrite, Role
from discord.ext import commands

from esportsbot.DiscordReactableMenus.EventReactMenu import EventReactMenu
from esportsbot.DiscordReactableMenus.ExampleMenus import ActionConfirmationMenu
from esportsbot.DiscordReactableMenus.reactable_lib import get_menu
from esportsbot.db_gateway import DBGatewayActions
from esportsbot.lib.discordUtil import get_attempted_arg
from esportsbot.models import Event_categories

denied_perms = PermissionOverwrite(read_messages=False, send_messages=False, connect=False)
read_only_perms = PermissionOverwrite(read_messages=True, send_messages=False, connect=False)
writable_perms = PermissionOverwrite(read_messages=True, send_messages=True, connect=True)
SIGN_IN_EMOJI = "✅"
SIGN_IN_DESCRIPTION = "Welcome to {}, react to this message to join the event so that you " \
                      "receive notifications for when things are happening!"

GENERAL_CHANNEL_SUFFIX = "general-chat"
SIGN_IN_CHANNEL_SUFFIX = "sign-in"
VOICE_CHANNEL_SUFFIX = "VC"


class EventCategoriesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.user_strings = bot.STRINGS["event_categories"]
        self.command_error_message = bot.STRINGS["command_error_generic"]
        self.db = DBGatewayActions()
        self.event_menus = defaultdict(dict)
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Loaded {__name__}!")

    @commands.Cog.listener()
    async def on_ready(self):
        await self.load_event_menus()
        self.logger.info(f"{__name__} is now ready!")

    async def load_event_menus(self):
        bot_guilds = [x.id for x in self.bot.guilds]

        to_load = []

        for guild in bot_guilds:
            to_load.append(self.load_events_in_guild(guild))

        loaded_guilds = await asyncio.gather(*to_load)

        self.event_menus = dict(zip(bot_guilds, loaded_guilds))

    async def load_events_in_guild(self, guild_id):
        raw_events = self.db.list(Event_categories, guild_id=guild_id)

        to_load = []

        for event in raw_events:
            event_menu = event.event_menu
            to_load.append(EventReactMenu.from_dict(self.bot, event_menu))

        loaded_events = await asyncio.gather(*to_load)

        events = {}
        for event in loaded_events:
            if isinstance(event, dict):
                self.delete_event_data(event.get("guild_id"), event.get("id"))
            elif isinstance(event, EventReactMenu):
                events[event.id] = event

        return events

    async def send_current_events(self, context: commands.Context):
        guild_events = self.event_menus[context.guild.id]
        events = str([str(x.title) for x in guild_events.values()]).replace("[", "").replace("]", "")
        if len(events) > 0:
            reply = self.user_strings["unrecognised_event"].format(events=events)
        else:
            reply = self.user_strings["no_events"]
        await context.reply(reply)

    def get_event_by_name(self, guild_id, event_name):
        guild_events = self.event_menus[guild_id]
        if event_name:
            for event_id in guild_events:
                if event_name.lower() in guild_events.get(event_id).title.lower():
                    return guild_events.get(event_id)
        else:
            return get_menu(guild_events, event_name)

    def update_event(self, guild_id, event_menu):
        db_item = self.db.get(Event_categories, guild_id=guild_id, event_id=event_menu.id)
        db_item.event_menu = event_menu.to_dict()
        self.db.update(db_item)

    def delete_event_data(self, guild_id, event_id):
        db_item = self.db.get(Event_categories, guild_id=guild_id, event_id=event_id)
        self.db.delete(db_item)

    @staticmethod
    async def event_closed_perms(general, sign_in, voice_chat, bot_role, event_role, shared_role, reason):
        # The Guilds default role, pretty much always @everyone
        default_role = general.guild.default_role

        # Get the current permissions for the general channel and update them
        current_general = {
            bot_role: writable_perms,
            event_role: denied_perms,
            shared_role: denied_perms,
            default_role: denied_perms
        }
        await general.edit(overwrites=current_general, reason=reason)

        # Get the current permissions for the voice channel and update them
        current_vc = {
            bot_role: writable_perms,
            event_role: denied_perms,
            shared_role: denied_perms,
            default_role: denied_perms
        }
        await voice_chat.edit(overwrites=current_vc, reason=reason)

        # Get the current permissions for the sign in channel and update them
        current_sign_in = {
            bot_role: writable_perms,
            event_role: denied_perms,
            shared_role: denied_perms,
            default_role: denied_perms
        }
        await sign_in.edit(overwrites=current_sign_in, reason=reason)

    @staticmethod
    async def event_open_perms(general, sign_in, voice_chat, event_role, shared_role, reason):
        # The Guilds default role, pretty much always @everyone
        default_role = general.guild.default_role

        # Get the current permissions for the general channel and update them
        current_general = general.overwrites
        current_general[event_role] = writable_perms
        current_general[shared_role] = denied_perms
        current_general[default_role] = denied_perms
        await general.edit(overwrites=current_general, reason=reason)

        # Get the current permissions for the voice channel and update them
        current_vc = voice_chat.overwrites
        current_vc[event_role] = writable_perms
        current_vc[shared_role] = denied_perms
        current_vc[default_role] = denied_perms
        await voice_chat.edit(overwrites=current_vc, reason=reason)

        # Get the current permissions for the sign in channel and update them
        current_sign_in = sign_in.overwrites
        current_sign_in[event_role] = read_only_perms
        current_sign_in[shared_role] = read_only_perms
        current_sign_in[default_role] = denied_perms
        await sign_in.edit(overwrites=current_sign_in, reason=reason)

    @staticmethod
    def get_event_channels(event_menu):
        sign_in_channel = event_menu.message.channel
        general_channel = list(filter(lambda x: GENERAL_CHANNEL_SUFFIX in x.name, event_menu.event_category.text_channels))[0]
        voice_channel = list(filter(lambda x: VOICE_CHANNEL_SUFFIX in x.name, event_menu.event_category.voice_channels))[0]
        return general_channel, sign_in_channel, voice_channel

    @commands.group(
        name="events",
        help="Create events with sign in menus dedicated event roles, and event channels.",
        invoke_without_command=True
    )
    async def event_command_group(self, context: commands.context):
        pass

    @event_command_group.command(
        name="create-event",
        usage="<event name> <shared role>",
        help="Creates a new category, text channel, voice channel and sign-in menu with the given name, and "
        "once opened will, the sign-in channel will be available to the given role."
    )
    @commands.has_permissions(administrator=True)
    async def create_event(self, context: commands.Context, event_name: str, shared_role: Role) -> bool:

        self.logger.info(f"Creating a new Event with name {event_name}")
        audit_reason = "Done with `create-event` command"

        if not shared_role:
            shared_role = context.guild.default_role

        guild_events = self.event_menus[context.guild.id]

        # Check if an event already exists with the given name.
        for event_id in guild_events:
            if event_name.lower() in guild_events.get(event_id).title.lower():
                self.logger.warning(f"There is already an event with the name {event_name} in {context.guild.name}")
                await context.reply(self.user_strings["event_exists"].format(event_name=event_name))
                return False

        event_category = await context.guild.create_category(name=event_name, reason=audit_reason)
        event_sign_in_channel = await context.guild.create_text_channel(
            name=f"{event_name} {SIGN_IN_CHANNEL_SUFFIX}",
            category=event_category,
            sync_permissions=False,
            reason=audit_reason
        )
        event_general_channel = await context.guild.create_text_channel(
            name=f"{event_name} {GENERAL_CHANNEL_SUFFIX}",
            category=event_category,
            sync_permissions=False,
            reason=audit_reason
        )
        event_voice_channel = await context.guild.create_voice_channel(
            name=f"{event_name} {VOICE_CHANNEL_SUFFIX}",
            category=event_category,
            sync_permissions=False,
            reason=audit_reason
        )
        event_role = await context.guild.create_role(name=event_name, reason=audit_reason)

        # Used to ensure that the bot can always see/type in the channel.
        bot_top_role = context.me.roles[-1]

        # Set the permissions for each of the channels created by the command:
        await self.event_closed_perms(
            event_general_channel,
            event_sign_in_channel,
            event_voice_channel,
            bot_top_role,
            event_role,
            shared_role,
            audit_reason
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

        db_item = Event_categories(
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
        return True

    @event_command_group.command(
        name="open-event",
        usage="<event name>",
        help="Reveal the sign-in channel for the name event channel."
    )
    @commands.has_permissions(administrator=True)
    async def open_event(self, context: commands.Context, event_name: str) -> bool:
        self.logger.info(f"Attempting to open event with name {event_name}, if this is none, searching for latest event menu")

        audit_reason = "Done with `open-event` command"

        event_menu = self.get_event_by_name(context.guild.id, event_name)

        # If there no event with the given name, exit:
        if not event_menu:
            self.logger.warning(f"There is no event to open with the name {event_name} in {context.guild.name}")
            await self.send_current_events(context)
            return False

        # Set the permissions for the generic event channels:
        general_channel, sign_in_channel, voice_channel = self.get_event_channels(event_menu)
        await self.event_open_perms(
            general_channel,
            sign_in_channel,
            voice_channel,
            event_menu.event_role,
            event_menu.shared_role,
            reason=audit_reason
        )

        await event_menu.enable_menu(self.bot)
        self.update_event(context.guild.id, event_menu)
        self.logger.info(f"Successfully opened an event with the name {event_name} in {context.guild.name}")
        await context.reply(
            self.user_strings["success_channel"].format(
                channel_id=event_menu.message.channel.id,
                role_name=event_menu.shared_role.name
            )
        )
        return True

    @event_command_group.command(
        name="close-event",
        usage="<event name>",
        help="Close off the event channels to everyone that isn't an admin"
    )
    @commands.has_permissions(administrator=True)
    async def close_event(self, context: commands.Context, event_name: str) -> bool:
        self.logger.info(f"Attempting to close event with name {event_name}, if this is none, searching for latest event menu")

        audit_reason = "Done with `close-event` command"

        event_menu = self.get_event_by_name(context.guild.id, event_name)

        # If there no event with the given name, exit:
        if not event_menu:
            self.logger.warning(f"There is no event to close with the name {event_name} in {context.guild.id}")
            await self.send_current_events(context)
            return False

        bot_top_role = context.me.roles[-1]

        # Set the permissions for the generic event channels:
        general_channel, sign_in_channel, voice_channel = self.get_event_channels(event_menu)
        await self.event_closed_perms(
            general_channel,
            sign_in_channel,
            voice_channel,
            bot_top_role,
            event_menu.event_role,
            event_menu.shared_role,
            reason=audit_reason
        )

        await event_menu.disable_menu(self.bot)
        self.update_event(context.guild.id, event_menu)
        self.logger.info(f"Successfully closed an event with the name {event_name} in {context.guild.name}")
        await context.reply(self.user_strings["success_event_closed"])
        return True

    @event_command_group.command(
        name="delete-event",
        usage="<event name>",
        help="Deletes the event channels and the temporary event role"
    )
    @commands.has_permissions(administrator=True)
    async def delete_event(self, context: commands.Context, event_name: str):
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
        if not confirm_menu.delete_after:
            await confirm_menu.disable_menu(self.bot)

        self.logger.info(f"Deletion of {event_name} menu cancelled by {context.author.name}#{context.author.discriminator}")
        await context.reply(self.user_strings["delete_cancelled"].format(event_name=event_name))

    @create_event.error
    async def on_create_event_error(self, context: commands.Context, error: commands.CommandError):
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
        self.logger.warning(
            f"There was an error while performing the '{context.command.name}' "
            f"command: {error.__class__.__name__}"
        )
        # When the user forgets to supply required arguments.
        if isinstance(error, commands.MissingRequiredArgument):
            self.logger.warning(f"Unable to perform {context.command.name} as the command lacked sufficient arguments")
            await context.reply(
                self.user_strings["missing_arguments"].format(prefix=self.bot.command_prefix,
                                                              command=context.command.name)
            )
            return

        # When the user does not have the correct permissions to perform the command.
        if isinstance(error, commands.MissingPermissions):
            print(error.missing_perms)
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

        # If an error occurred that wasn't one of the above, send a message telling the user to contact a dev as something
        # unexpected has occurred.
        await context.reply(self.command_error_message)
        raise error


def setup(bot):
    bot.add_cog(EventCategoriesCog(bot))
