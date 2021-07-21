import logging
import shlex

from discord.ext import commands

from esportsbot.DiscordReactableMenus.EmojiHandler import EmojiKeyError, MultiEmoji
from esportsbot.DiscordReactableMenus.ExampleMenus import RoleReactMenu
from esportsbot.DiscordReactableMenus.reactable_lib import get_menu
from esportsbot.db_gateway import DBGatewayActions
from esportsbot.models import Role_menus


class RoleReactCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.user_strings = self.bot.STRINGS["role_reacts"]
        self.db = DBGatewayActions()
        self.reaction_menus = {}
        self.logger = logging.getLogger(__name__)

    @commands.Cog.listener()
    async def on_ready(self):
        self.reaction_menus = await self.load_menus()

    async def load_menus(self):
        all_menus = self.db.list(Role_menus)
        loaded_menus = {}
        for menu in all_menus:
            loaded_menus[menu.menu_id] = await RoleReactMenu.from_dict(self.bot, menu.menu)
        return loaded_menus

    def add_or_update_db(self, menu_id):
        db_item = self.db.get(Role_menus, menu_id=menu_id)
        if db_item:
            db_item.menu = self.reaction_menus.get(menu_id).to_dict()
            self.db.update(db_item)
        else:
            db_item = Role_menus(menu_id=menu_id, menu=self.reaction_menus.get(menu_id).to_dict())
            self.db.create(db_item)

    @staticmethod
    def options_from_strings(message, roles):
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
        quote_last_index = message.rfind('"')
        quote_first_index = message.index('"')
        short_message = message[quote_first_index:quote_last_index + 1]
        split_message = shlex.split(short_message)
        return split_message[0], split_message[1]

    @commands.group(name="roles", help="Create reaction menus that can be used to get roles.")
    async def command_group(self, context: commands.Context):
        pass

    # TODO: Fix link
    @command_group.command(
        name="make-menu",
        usage="<title> <description> [<mentioned role> <emoji>]",
        help="Creates a new role reaction menu with the given roles and their emojis. "
        "Go to {} for more help regarding usage."
    )
    @commands.has_permissions(administrator=True)
    async def create_role_menu(self, context: commands.Context):
        roles = context.message.role_mentions
        role_strings = [f"<@&{x.id}>" for x in roles]
        # The mentioned roles in the correct order.
        sorted_strings = sorted(role_strings, key=lambda x: context.message.content.index(x))

        try:
            menu_options = self.options_from_strings(context.message.content, sorted_strings)
        except EmojiKeyError as e:
            await context.reply(self.user_strings["duplicate_emoji"].format(emoji=e.emoji))
            return

        try:
            title, description = self.title_and_description(context.message.content)
        except IndexError:
            await context.reply(self.user_strings["missing_quotes"])
            return

        role_menu = RoleReactMenu(title=title, description=description, auto_enable=True, use_inline=False)
        role_menu.add_many(menu_options)
        await role_menu.finalise_and_send(self.bot, context.channel)

        self.reaction_menus[role_menu.id] = role_menu
        self.add_or_update_db(role_menu.id)

    @command_group.command(
        name="add-option",
        usage="[optional: menu id] [<mentioned role> <emoji>]",
        help="Adds a new option to a reaction menu. If no ID is given it will add the option to the latest menu."
    )
    @commands.has_permissions(administrator=True)
    async def add_menu_option(self, context: commands.Context, menu_id=None):

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

    @command_group.command(
        name="remove-option",
        usage="<emoji> [optional: menu id]",
        help="Removes the role associated with the emoji from the given menu. "
        "If no ID is given it will remove the option from the latest menu."
    )
    @commands.has_permissions(administrator=True)
    async def remove_menu_option(self, context: commands.Context, option_key: MultiEmoji, menu_id=None):
        menu = get_menu(self.reaction_menus, menu_id)
        if not menu:
            await context.reply(self.user_strings["invalid_id"].format(given_id=menu_id))
            return

        menu.remove_option(option_key)
        await menu.update_message()
        self.add_or_update_db(menu.id)

    @command_group.command(
        name="disable-menu",
        usage="[optional: menu id]",
        help="Stops users from using the reaction menu to get roles. If no ID is given the latest menu will be disabled."
    )
    @commands.has_permissions(administrator=True)
    async def disable_menu(self, context: commands.Context, menu_id=None):
        menu = get_menu(self.reaction_menus, menu_id)
        if not menu:
            await context.reply(self.user_strings["invalid_id"].format(given_id=None))
            return

        await menu.disable_menu(self.bot)
        self.add_or_update_db(menu.id)
        await context.reply(self.user_strings["disable_menu"].format(menu_id=menu.id))

    @command_group.command(
        name="enable-menu",
        usage="[optional: menu id]",
        help="Allows users to use a reaction menu to get its roles. If no ID is given the latest menu will be enabled."
    )
    @commands.has_permissions(administrator=True)
    async def enable_menu(self, context: commands.Context, menu_id=None):
        menu = get_menu(self.reaction_menus, menu_id)
        if not menu:
            await context.reply(self.user_strings["invalid_id"].format(given_id=None))
            return

        await menu.enable_menu(self.bot)
        self.add_or_update_db(menu.id)
        await context.reply(self.user_strings["enable_menu"].format(menu_id=menu.id))

    @command_group.command(name="delete-menu", usage="<menu id>", help="Deletes a given role reaction menu.")
    @commands.has_permissions(administrator=True)
    async def delete_menu(self, context: commands.Context, menu_id):
        menu = get_menu(self.reaction_menus, menu_id)

        if not menu:
            await context.reply(self.user_strings["invalid_id"].format(given_id=None))
            return

        await menu.message.delete()
        self.reaction_menus.pop(menu.id)
        db_item = self.db.get(Role_menus, menu_id=menu.id)
        self.db.delete(db_item)
        await context.reply(self.user_strings["delete_menu"].format(given_id=menu.id))

    @command_group.command(name="toggle-ids", help="Toggles the footer displaying the menu ID for all role reaction menus.")
    @commands.has_permissions(administrator=True)
    async def toggle_show_ids(self, context: commands.Context):
        for menu_id in self.reaction_menus:
            menu = self.reaction_menus.get(menu_id)
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
