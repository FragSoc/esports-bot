import logging
import os
import shlex

from discord.ext import commands
from esportsbot.db_gateway import DBGatewayActions
from esportsbot.DiscordReactableMenus.EmojiHandler import (EmojiKeyError, MultiEmoji)
from esportsbot.DiscordReactableMenus.ExampleMenus import RoleReactMenu
from esportsbot.DiscordReactableMenus.reactable_lib import get_menu
from esportsbot.models import RoleMenus

DELETE_ON_CREATE = os.getenv("DELETE_ROLE_CREATION", "FALSE").lower() == "true"


class RoleReactCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.user_strings = self.bot.STRINGS["role_reacts"]
        self.db = DBGatewayActions()
        self.reaction_menus = {}
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Finished loading {__name__}... waiting for ready")

    @commands.Cog.listener()
    async def on_ready(self):
        self.reaction_menus = await self.load_menus()
        self.logger.info(f"{__name__} is now ready!")

    async def load_menus(self):
        """
        Loads saved role reaction menus from the DB for all guilds .
        :return: A dictionary of reaction menu IDs and their reaction menus .
        """
        all_menus = self.db.list(RoleMenus)
        loaded_menus = {}
        for menu in all_menus:
            loaded_menus[menu.menu_id] = await RoleReactMenu.from_dict(self.bot, menu.menu)
        return loaded_menus

    def add_or_update_db(self, menu_id):
        """
        Creates a new DB item or updates an existing one for a given menu id .
        :param menu_id: The menu id to create or update .
        """
        db_item = self.db.get(RoleMenus, menu_id=menu_id)
        if db_item:
            db_item.menu = self.reaction_menus.get(menu_id).to_dict()
            self.db.update(db_item)
        else:
            db_item = RoleMenus(menu_id=menu_id, menu=self.reaction_menus.get(menu_id).to_dict())
            self.db.create(db_item)

    @staticmethod
    def options_from_strings(message, roles):
        """
        Gets the role/emoji pairs for the options to add to the role reaction menu from the message contents .
        :param message: The message contents .
        :param roles: The list of roles mentioned in the message in the order they were mentioned in .
        :return: A dictionary of emoji to role.
        """
        options = {}
        for i in range(len(roles)):
            if i == len(roles) - 1:
                emoji_end_index = len(message)
            else:
                emoji_end_index = message.index(roles[i + 1])

            emoji_str = message[message.index(roles[i]) + len(roles[i]):emoji_end_index]
            emoji_str = emoji_str.strip()

            if emoji_str in options:
                raise EmojiKeyError(emoji_str)
            else:
                options[emoji_str] = roles[i]

        return options

    @staticmethod
    def title_and_description(message):
        """
        Get the title and description of a reaction menu from the creation command .
        :param message: The message contents .
        :return: A tuple of Title, Description
        """
        quote_last_index = message.rfind('"')
        quote_first_index = message.index('"')
        short_message = message[quote_first_index:quote_last_index + 1]
        split_message = shlex.split(short_message)
        return split_message[0], split_message[1]

    @commands.group(name="roles", help="Create reaction menus that can be used to get roles.")
    async def command_group(self, context: commands.Context):
        """
        The command group used to make all commands sub-commands .
        :param context: The context of the command .
        """
        pass

    @command_group.command(name="make-menu")
    @commands.has_permissions(administrator=True)
    async def create_role_menu(self, context: commands.Context):
        """
        Creates a new role reaction menu with the options provided in the command .
        :param context: The context of the command .
        """
        roles = context.message.role_mentions
        role_strings = [f"<@&{x.id}>" for x in roles]
        # The mentioned roles in the correct order.
        sorted_strings = sorted(role_strings, key=lambda x: context.message.content.index(x))

        try:
            menu_options = self.options_from_strings(context.message.content, sorted_strings)
        except EmojiKeyError as e:
            # The emoji is already in the reaction menu .
            await context.reply(self.user_strings["duplicate_emoji"].format(emoji=e.emoji))
            return

        try:
            title, description = self.title_and_description(context.message.content)
        except ValueError:
            # The user missed some quotes around their title/description.
            await context.reply(self.user_strings["missing_quotes"])
            return

        role_menu = RoleReactMenu(title=title, description=description, auto_enable=True, use_inline=False)
        role_menu.add_many(menu_options)
        await role_menu.finalise_and_send(self.bot, context.channel)

        self.reaction_menus[role_menu.id] = role_menu
        self.add_or_update_db(role_menu.id)
        if DELETE_ON_CREATE:
            await context.message.delete()

    @command_group.command(name="add-option")
    @commands.has_permissions(administrator=True)
    async def add_menu_option(self, context: commands.Context, menu_id: str = None):
        """
        Adds more roles to the role reaction menu . This is done using the message.role_mentions attr instead of
         using function params.
        :param context: The context of the command .
        :param menu_id: The ID of the menu to add the roles to .
        """
        roles = context.message.role_mentions
        role_strings = [f"<@&{x.id}>" for x in roles]
        # The mentioned roles in the correct order.
        sorted_strings = sorted(role_strings, key=lambda x: context.message.content.index(x))

        # If the user hasn't supplied a menu ID the menu ID var will be the role mention:
        if menu_id in sorted_strings:
            menu_id = None

        found_menu = get_menu(self.reaction_menus, menu_id)

        if not found_menu:
            await context.reply(self.user_strings["invalid_id"].format(given_id=menu_id))
            return

        try:
            options_to_add = self.options_from_strings(context.message.content, sorted_strings)
        except EmojiKeyError as e:
            await context.reply(self.user_strings["duplicate_emoji"].format(emoji=e.emoji))
            return

        found_menu.add_many(options_to_add)
        await found_menu.update_message()
        self.add_or_update_db(found_menu.id)

    @command_group.command(name="remove-option")
    @commands.has_permissions(administrator=True)
    async def remove_menu_option(self, context: commands.Context, option_key: MultiEmoji, menu_id=None):
        """
        Removes an role option from a reaction menu .
        :param context: The context of the command .
        :param option_key: The emoji used to get the role to remove from the menu .
        :param menu_id: The ID of the menu to remove the option from .
        :return:
        """
        menu = get_menu(self.reaction_menus, menu_id)
        if not menu:
            await context.reply(self.user_strings["invalid_id"].format(given_id=menu_id))
            return

        menu.remove_option(option_key)
        await menu.update_message()
        self.add_or_update_db(menu.id)

    @command_group.command(name="disable-menu")
    @commands.has_permissions(administrator=True)
    async def disable_menu(self, context: commands.Context, menu_id=None):
        """
        Disables a reaction menu to stop users from being able to get roles from it .
        :param context: The context of the command .
        :param menu_id: The ID of the menu to disable .
        """
        menu = get_menu(self.reaction_menus, menu_id)
        if not menu:
            await context.reply(self.user_strings["invalid_id"].format(given_id=None))
            return

        await menu.disable_menu(self.bot)
        self.add_or_update_db(menu.id)
        await context.reply(self.user_strings["disable_menu"].format(menu_id=menu.id))

    @command_group.command(name="enable-menu")
    @commands.has_permissions(administrator=True)
    async def enable_menu(self, context: commands.Context, menu_id=None):
        """
        Allows users to react to a message and get roles from it .
        :param context: The context of the command .
        :param menu_id: The menu ID to enable .
        """
        menu = get_menu(self.reaction_menus, menu_id)
        if not menu:
            await context.reply(self.user_strings["invalid_id"].format(given_id=None))
            return

        await menu.enable_menu(self.bot)
        self.add_or_update_db(menu.id)
        await context.reply(self.user_strings["enable_menu"].format(menu_id=menu.id))

    @command_group.command(name="delete-menu")
    @commands.has_permissions(administrator=True)
    async def delete_menu(self, context: commands.Context, menu_id):
        """
        Deletes a reaction menu entirely .
        :param context: The context of the command .
        :param menu_id: The menu ID to delete .
        """
        menu = get_menu(self.reaction_menus, menu_id)

        if not menu:
            await context.reply(self.user_strings["invalid_id"].format(given_id=menu_id))
            return

        await menu.message.delete()
        self.reaction_menus.pop(menu.id)
        db_item = self.db.get(RoleMenus, menu_id=menu.id)
        self.db.delete(db_item)
        await context.reply(self.user_strings["delete_menu"].format(menu_id=menu.id))

    @command_group.command(name="toggle-ids")
    @commands.has_permissions(administrator=True)
    async def toggle_show_ids(self, context: commands.Context):
        """
        Toggles if the menu IDs are showing in the footer of all reaction menus .
        :param context: The context of the command .
        """
        for menu_id in self.reaction_menus:
            menu = self.reaction_menus.get(menu_id)
            if menu.guild.id != context.guild.id:
                continue
            menu.toggle_footer()
            await menu.update_message()
            self.add_or_update_db(menu_id)

    @remove_menu_option.error
    async def remove_error(self, context: commands.Context, error):
        if isinstance(error, commands.BadArgument):
            await context.reply(self.user_strings["invalid_emoji"])
            return

        raise error


def setup(bot):
    bot.add_cog(RoleReactCog(bot))
