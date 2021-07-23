import logging
import os

from discord.ext import commands

from esportsbot.DiscordReactableMenus.ExampleMenus import PollReactMenu
from esportsbot.DiscordReactableMenus.reactable_lib import get_all_options
from esportsbot.db_gateway import DBGatewayActions
from esportsbot.models import Voting_menus

DELETE_ON_CREATE = os.getenv("DELETE_VOTING_CREATION", "FALSE").lower() == "true"


class VotingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.db = DBGatewayActions()
        self.voting_menus = {}
        self.user_strings = bot.STRINGS["vote_reacts"]

    @commands.Cog.listener()
    async def on_ready(self):
        self.voting_menus = await self.load_menus()
        self.logger.info(f"Finished loading {__name__}!")

    async def load_menus(self):
        all_menus = self.db.list(Voting_menus)
        loaded_menus = {}
        for menu in all_menus:
            loaded_menus[menu.menu_id] = await PollReactMenu.from_dict(self.bot, menu.menu)
        return loaded_menus

    async def validate_menu(self, context, menu_id):
        voting_menu = self.voting_menus.get(menu_id)

        if not voting_menu:
            await context.reply(self.user_strings["invalid_id"].format(given_id=menu_id))
            return voting_menu, False

        if voting_menu.author.id != context.author.id and not context.author.guild_permissions.administrator:
            owner = f"{voting_menu.author.name}#{voting_menu.author.discriminator}"
            await context.reply(self.user_strings["wrong_author"].format(author=owner))
            return voting_menu, False

        return voting_menu, True

    def add_or_update_db(self, menu_id):
        db_item = self.db.get(Voting_menus, menu_id=menu_id)
        if db_item:
            db_item.menu = self.voting_menus.get(menu_id).to_dict()
            self.db.update(db_item)
        else:
            db_item = Voting_menus(menu_id=menu_id, menu=self.voting_menus.get(menu_id).to_dict())
            self.db.create(db_item)

    async def finalise_poll(self, menu):
        results = await menu.generate_results()
        await menu.message.channel.send(embed=results)
        self.voting_menus.pop(menu.id)
        db_item = self.db.get(Voting_menus, menu_id=menu.id)
        self.db.delete(db_item)
        await menu.message.delete()

    @commands.group(name="votes", help="Create reaction menus that can be used as a poll.")
    async def command_group(self, context: commands.Context):
        pass

    # TODO: Fix link
    @command_group.command(
        name="make-poll",
        usage="<title> \n[options]\n...",
        help="Creates a new poll for users to vote on. "
        "Each of the options to vote on are put on a new line, more help regarding this command can be found here: {}."
    )
    async def create_poll_menu(self, context: commands.Context):
        message_contents = context.message.content.split("\n")
        title = message_contents.pop(0)
        title = title[title.index(context.command.name) + len(context.command.name):].strip()
        menu_options = get_all_options(message_contents)
        description = f"This poll is controlled by {context.author.mention}."
        voting_menu = PollReactMenu(
            title=title,
            description=description,
            auto_enable=True,
            author=context.author,
            show_ids=True,
            poll_length=0
        )
        voting_menu.add_many(menu_options)

        await voting_menu.finalise_and_send(self.bot, context.channel)

        self.voting_menus[voting_menu.id] = voting_menu
        self.add_or_update_db(voting_menu.id)
        if DELETE_ON_CREATE:
            await context.message.delete()

    @command_group.command(
        name="add-option",
        usage="<menu id> <emoji> <description>",
        help="Adds another option to an existing poll.",
        aliases=["add",
                 "aoption"]
    )
    async def add_poll_option(self, context: commands.Context, menu_id: int, emoji):
        voting_menu, valid = await self.validate_menu(context, menu_id)

        if not valid:
            return

        # Assume the rest of the message after the emoji param is the description, avoiding the need to use quotes.
        description = context.message.content[context.message.content.index(emoji) + len(emoji):].strip()

        voting_menu.add_option(emoji, description)
        await voting_menu.update_message()
        self.add_or_update_db(voting_menu.id)

    @command_group.command(
        name="remove-option",
        usage="<menu id> <emoji>",
        help="Removes a poll option from an existing poll",
        aliases=["remove",
                 "roption"]
    )
    async def remove_poll_option(self, context: commands.Context, menu_id: int, emoji):
        voting_menu, valid = await self.validate_menu(context, menu_id)

        if not valid:
            return

        voting_menu.remove_option(emoji)
        await voting_menu.update_message()
        self.add_or_update_db(voting_menu.id)

    @command_group.command(
        name="delete-poll",
        usage="<menu id>",
        help="Deletes a given role reaction menu.",
        aliases=["delete",
                 "del"]
    )
    async def delete_poll(self, context: commands.Context, menu_id: int):
        voting_menu, valid = await self.validate_menu(context, menu_id)

        if not valid:
            return

        await voting_menu.message.delete()
        self.voting_menus.pop(voting_menu.id)
        db_item = self.db.get(Voting_menus, menu_id=voting_menu.id)
        self.db.delete(db_item)
        await context.reply(self.user_strings["delete_menu"].format(menu_id=voting_menu.id))

    @command_group.command(name="end-poll", usage="<menu id>", help="Finishes a poll.", aliases=["finish", "complete", "end"])
    async def finish_poll(self, context: commands.Context, menu_id: int):
        voting_menu, valid = await self.validate_menu(context, menu_id)

        if not valid:
            return

        await self.finalise_poll(voting_menu)

    @command_group.command(
        name="reset-poll",
        usage="<menu id>",
        help="Removes all user reactions from the poll.",
        aliases=["reset",
                 "clear",
                 "restart"]
    )
    async def reset_poll_votes(self, context: commands.Context, menu_id: int):
        voting_menu, valid = await self.validate_menu(context, menu_id)

        if not valid:
            return

        await voting_menu.message.clear_reactions()
        if voting_menu.enabled:
            voting_menu.enabled = False
            await voting_menu.enable_menu(self.bot)

        await context.reply(self.user_strings["reset_menu"].format(menu_id=menu_id))

    @delete_poll.error
    @finish_poll.error
    @add_poll_option.error
    @reset_poll_votes.error
    @remove_poll_option.error
    async def integer_parse_error(self, context: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.BadArgument):
            await context.reply(self.user_strings["needs_number"])
            return

        raise error


def setup(bot):
    bot.add_cog(VotingCog(bot))
