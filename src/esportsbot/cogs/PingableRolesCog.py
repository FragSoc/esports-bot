import datetime
import logging
import os
from collections import defaultdict
from typing import Dict, List

from discord.ext import commands, tasks

from esportsbot.DiscordReactableMenus.EmojiHandler import MultiEmoji
from esportsbot.DiscordReactableMenus.PingableMenus import PingableRoleMenu, PingableVoteMenu
from esportsbot.db_gateway import DBGatewayActions

# The emoji to use in the role menu:
from esportsbot.models import Pingable_polls, Pingable_roles, Pingable_settings

# The default role emoji to use on the role react menus:
PINGABLE_ROLE_EMOJI = MultiEmoji("💎")
# The title and description of the role react:
PINGABLE_ROLE_TITLE = "Pingable Role: {}"
PINGABLE_ROLE_DESCRIPTION = "React to this message to receive this pingable role"
# The suffix of the pingable role when the role gets created
PINGABLE_ROLE_SUFFIX = "(Pingable)"

# The default emoji to use in the poll:
PINGABLE_POLL_EMOJI = MultiEmoji("📋")
# The title and description of the poll:
PINGABLE_POLL_TITLE = "Vote to create {} Pingable Role"
PINGABLE_POLL_DESCRIPTION = "If the vote is successful you will be given the role"

# Minimum length of the poll:
MIN_POLL_LENGTH = 60

# Values to be stored in the DB:

# The number of votes required for a poll to be successful
PINGABLE_POLL_THRESHOLD = 2
# The length of the poll:
PINGABLE_POLL_LENGTH = 20
# Number of seconds before role can be pinged again
PINGABLE_COOLDOWN = 60


class PingableRolesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = DBGatewayActions()
        self.user_strings = self.bot.STRINGS["pingable_roles"]
        self.command_error_message = bot.STRINGS["command_error_generic"]

        self.guild_settings = self.load_guild_settings()  # Guild ID: Pingable_settings as dict
        self.polls = None  # Menu ID: {name: pingable name, menu: poll menu instance}
        self.roles = None  # Menu ID: {role id: pingable role id, menu: role menu instance}
        self.all_role_ids = None  # Guild ID: {role id : menu id}
        self.roles_on_cooldown = []  # List of roles that are on cooldown

        self.logger = logging.getLogger(__name__)

        self.current_poll = None
        self.current_menu = None
        self.current_role = None
        self.on_cooldown = False

    @commands.Cog.listener()
    async def on_ready(self):
        guild_ids = [x.id for x in self.bot.guilds]
        self.roles = self.load_all_roles(guild_ids)
        self.polls = self.load_all_polls(guild_ids)
        self.all_role_ids = self.all_roles_from_guild_data(self.roles)
        await self.initialise_menus()
        self.ensure_tasks()
        self.logger.info(f"Loaded {__name__}!")

    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignore messages that don't have mentions in them.
        if not message.role_mentions:
            return

        # Ignore pings from admins, would trust them to not abuse the ping power, but can be removed for safety.
        if message.author.guild_permissions.administrator:
            return

        # Check each role mentioned in the message:
        for role in message.role_mentions:
            if role.id in self.all_role_ids.get(message.guild.id):
                menu_id = self.all_role_ids.get(message.guild.id).get(role.id)
                menu = self.roles.get(menu_id).get("menu")
                menu.last_pinged = datetime.datetime.now()
                await role.edit(mentionable=False)
                self.roles_on_cooldown.append(role)
                self.ensure_tasks()

    async def initialise_menus(self):

        # Load role menus:
        for menu_id in self.roles:
            menu_data = self.roles.get(menu_id).get("menu")
            self.roles[menu_id]["menu"] = await PingableRoleMenu.from_dict(self.bot, menu_data)

        # Load poll menus:
        for poll_id in self.polls:
            menu_data = self.polls.get(poll_id).get("menu")
            self.polls[poll_id]["menu"] = await PingableVoteMenu.from_dict(self.bot, menu_data)

    def load_guild_settings(self) -> Dict:
        db_data: [Pingable_settings] = self.db.list(Pingable_settings)

        loaded_data = {}

        for item in db_data:
            loaded_data[item.guild_id] = {
                "poll_length": item.default_poll_length,
                "poll_threshold": item.default_poll_threshold,
                "poll_emoji": MultiEmoji.from_dict(item.default_poll_emoji),
                "role_emoji": MultiEmoji.from_dict(item.default_role_emoji)
            }

        return loaded_data

    def load_all_polls(self, guild_ids: List[int]) -> Dict:
        loaded_data = {}

        for guild in guild_ids:
            guild_data = self.load_guild_polls(guild)
            loaded_data = {**guild_data, **loaded_data}

        return loaded_data

    def load_guild_polls(self, guild_id: int) -> Dict:
        guild_polls: [Pingable_polls] = self.db.list(Pingable_polls, guild_id=guild_id)

        guild_data = {}

        for item in guild_polls:
            guild_data[item.poll_id] = {"name": item.pingable_name, "menu": item.poll}

        return guild_data

    def load_all_roles(self, guild_ids: List[int]) -> Dict:
        loaded_data = {}

        for guild in guild_ids:
            guild_data = self.load_guild_roles(guild)
            loaded_data = {**guild_data, **loaded_data}

        return loaded_data

    def load_guild_roles(self, guild_id: int) -> Dict:
        guild_roles: [Pingable_roles] = self.db.list(Pingable_roles, guild_id=guild_id)

        guild_data = {}

        for item in guild_roles:
            guild_data[item.menu_id] = {"role_id": item.role_id, "menu": item.menu}

        return guild_data

    @staticmethod
    def all_roles_from_guild_data(role_data: Dict) -> Dict:
        roles = defaultdict(dict)

        for menu_id in role_data:
            menu_data = role_data.get(menu_id)
            guild_id = menu_data.get("menu").get("guild_id")
            role_id = menu_data.get("role_id")
            roles[guild_id][role_id] = menu_id

        return roles

    def ensure_tasks(self):
        if not self.check_poll.is_running() or self.check_poll.is_being_cancelled():
            self.check_poll.start()

        if not self.check_cooldown.is_running() or self.check_cooldown.is_being_cancelled():
            self.check_cooldown.start()

    @tasks.loop(seconds=10)
    async def check_poll(self):
        if len(self.polls) == 0:
            self.check_poll.cancel()
            self.check_poll.stop()
            return

        current_time = datetime.datetime.now()

        polls_ids_to_remove = []

        for poll_id in self.polls:
            if self.polls.get(poll_id).get("menu").end_time <= current_time:
                polls_ids_to_remove.append(poll_id)
                await self.finish_poll(self.polls.get(poll_id).get("menu"))

        for poll_id in polls_ids_to_remove:
            self.polls.pop(poll_id)

    @tasks.loop(seconds=10)
    async def check_cooldown(self):
        if not self.roles_on_cooldown:
            self.check_cooldown.cancel()
            self.check_cooldown.stop()
            return

        current_time = datetime.datetime.now()

        roles_to_remove = []

        for role in self.roles_on_cooldown:
            menu_id = self.all_role_ids.get(role.guild.id).get(role.id)
            menu = self.roles.get(menu_id).get("menu")
            if current_time - menu.last_pinged >= datetime.timedelta(seconds=menu.cooldown):
                await role.edit(mentionable=True)

        for role in roles_to_remove:
            self.roles_on_cooldown.remove(role)

    async def finish_poll(self, poll_to_finish):
        threshold_emoji = MultiEmoji("✅")
        channel = poll_to_finish.message.channel
        threshold = self.guild_settings.get(channel.guild.id).get("poll_threshold")
        embed = poll_to_finish.generate_result_embed(threshold_emoji, threshold)

        await channel.send(embed=embed)

        if poll_to_finish.total_votes >= threshold:
            role = await channel.guild.create_role(name=poll_to_finish.name + PINGABLE_ROLE_SUFFIX, mentionable=True)
            current_menu = PingableRoleMenu(
                pingable_role=role,
                ping_cooldown=self.guild_settings.get(channel.guild.id).get("default_cooldown_length"),
                title=f"{poll_to_finish.name}{PINGABLE_ROLE_SUFFIX} Role React",
                description="React to this message to get this pingable role."
            )

            current_menu.add_option(self.guild_settings.get(channel.guild.id).get("role_emoji"), role)
            await current_menu.finalise_and_send(self.bot, channel)
            if not self.all_role_ids.get(channel.guild.id):
                self.all_role_ids[channel.guild.id] = {}
            self.all_role_ids[channel.guild.id][role.id] = current_menu.id
            self.roles[current_menu.id] = {"role_id": role.id, "menu": current_menu}
            db_item = Pingable_roles(
                guild_id=channel.guild.id,
                role_id=role.id,
                menu_id=current_menu.id,
                menu=current_menu.to_dict()
            )
            self.db.create(db_item)

        db_item = self.db.get(Pingable_polls, guild_id=channel.guild.id, poll_id=poll_to_finish.id)
        self.db.delete(db_item)
        await poll_to_finish.message.delete()

    @commands.group(name="pingme", help="Get and create custom roles with ping cooldown timers.", invoke_without_command=True)
    async def ping_me(self, context: commands.Context):
        pass

    @ping_me.command(name="default-settings", help="Sets the default value for the poll length, threshold and emojis")
    async def default_settings(self, context: commands.Context):
        guild_id = context.guild.id

        exists = self.db.get(Pingable_settings, guild_id=guild_id)

        current_item = Pingable_settings(
            guild_id=guild_id,
            default_poll_length=int(os.getenv("DEFAULT_POLL_LENGTH")),
            default_poll_threshold=int(os.getenv("DEFAULT_POLL_THRESHOLD")),
            default_poll_emoji=PINGABLE_POLL_EMOJI.to_dict(),
            default_role_emoji=PINGABLE_ROLE_EMOJI.to_dict()
        )

        if exists:
            self.db.update(current_item)
        else:
            self.db.create(current_item)

    @ping_me.command(
        name="create-role",
        usage="<role_name> [poll length seconds]",
        help="Starts a poll to determine if a new role with the given name should be created."
    )
    async def create_role(self, context: commands.Context, role_name: str, poll_length: int = None) -> bool:

        if poll_length is None or poll_length < MIN_POLL_LENGTH:
            poll_length = PINGABLE_POLL_LENGTH

        role_poll = PingableVoteMenu(
            pingable_name=role_name,
            auto_enable=True,
            title=PINGABLE_POLL_TITLE.format(role_name),
            description=PINGABLE_POLL_DESCRIPTION,
            poll_length=poll_length
        )

        role_poll.add_option(self.guild_settings.get(context.guild.id).get("poll_emoji"), role_name)
        await role_poll.finalise_and_send(self.bot, context.channel)
        db_item = Pingable_polls(
            guild_id=context.guild.id,
            pingable_name=role_name,
            poll_id=role_poll.id,
            poll=role_poll.to_dict()
        )
        self.db.create(db_item)
        self.polls[role_poll.id] = {"name": role_name, "menu": role_poll}
        self.logger.info(f"Created a poll for role with name {role_name}")
        self.ensure_tasks()
        await context.reply(self.user_strings["create_success"])
        return True

    @create_role.error
    async def on_create_error(self, context: commands.Context, error: commands.CommandError):
        if isinstance(error, ValueError):
            self.logger.warning(
                "User attempted to give non-integer value as poll length in the following message: %s",
                context.message.content
            )
            await context.reply(self.user_strings["invalid_argument"])
            return

        await context.reply(self.command_error_message)
        raise error


def setup(bot):
    bot.add_cog(PingableRolesCog(bot))
