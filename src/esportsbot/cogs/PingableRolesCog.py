import datetime
import logging
import os
from collections import defaultdict
from typing import Dict, List

from discord import Colour, Embed, Role
from discord.ext import commands, tasks
from esportsbot.db_gateway import DBGatewayActions
from esportsbot.DiscordReactableMenus.EmojiHandler import MultiEmoji
from esportsbot.DiscordReactableMenus.PingableMenus import (PingableRoleMenu, PingableVoteMenu)
from esportsbot.lib.discordUtil import get_attempted_arg
from esportsbot.models import (GuildInfo, PingablePolls, PingableRoles, PingableSettings)

# The default role emoji to use on the role react menus:
PINGABLE_ROLE_EMOJI = MultiEmoji("💎")
# The title and description of the role react:
PINGABLE_ROLE_TITLE = "Pingable Role: {}"
PINGABLE_ROLE_DESCRIPTION = "React to this message to receive this pingable role"
# The suffix of the pingable role when the role gets created
PINGABLE_ROLE_SUFFIX = "(Pingable)"

# The default emoji to use in the poll:
PINGABLE_POLL_EMOJI = MultiEmoji("📋")
# The emoji used to mock the vote threshold:
THRESHOLD_EMOJI = MultiEmoji("🏆")
# The title and description of the poll:
PINGABLE_POLL_TITLE = "Vote to create {} Pingable Role"
PINGABLE_POLL_DESCRIPTION = "The number of votes required to make this role is: `>= {vote_num} votes`. " \
                            "If the number of votes is reached and you have voted, you will be given the role automatically " \
                            "when the poll finishes."

TASK_INTERVAL = 10


class PingableRolesCog(commands.Cog):
    """
    Pingable roles are roles that can be voted in to be created by any user, and that once created have a cooldown tied to how
    often that role can be pinged.

    A user can create a poll where if there are enough votes by the time the poll ends, a role will be created.
    The length of the poll and the number of votes required are customisable by server admins.

    After the poll finishes, a reaction menu gets created, allowing any user to react and receive the role.
    Initially the role will have the default cooldown of the server, but can be overridden.

    This module implements the above features through a set of commands and making use of a Pingable DB to store and load roles
    between shutdowns.
    """
    def __init__(self, bot):
        self.bot = bot
        self.db = DBGatewayActions()
        self.user_strings = self.bot.STRINGS["pingable_roles"]
        self.command_error_message = bot.STRINGS["command_error_generic"]
        self.logger = logging.getLogger(__name__)

        self.guild_settings = self.load_guild_settings()  # Guild ID: Pingable_settings as dict
        self.polls = None  # Menu ID: {name: pingable name, menu: poll menu instance}
        self.roles = None  # Menu ID: {role id: pingable role id, menu: role menu instance}
        self.all_role_ids = None  # Guild ID: {role id : menu id}
        self.roles_on_cooldown = []  # List of roles that are on cooldown

        self.current_poll = None
        self.current_menu = None
        self.current_role = None
        self.on_cooldown = False
        self.logger.info(f"Finished loading {__name__}... waiting for ready")

    @commands.Cog.listener()
    async def on_ready(self):
        """
        When bot discord client is ready and has logged into the discord API, this function runs and is used to load and
        initialise any saved Pingable Roles, as well as their reaction menus.
        """
        guild_ids = [x.id for x in self.bot.guilds]
        self.roles = self.load_all_roles(guild_ids)
        self.polls = self.load_all_polls(guild_ids)
        self.all_role_ids = self.all_roles_from_guild_data(self.roles)
        await self.delete_missing_roles()
        await self.initialise_menus()
        self.ensure_tasks()
        if os.getenv("RUN_MONTHLY_REPORT", "FALSE").lower() == "true":
            self.monthly_ping_report.start()
        self.logger.info(f"{__name__} is now ready!")

    @commands.Cog.listener()
    async def on_message(self, message):
        """
        When a message is sent in a channel the bot is able to see, check if a Pingable Role was mentioned in the message, and
        if so put it on cooldown.
        :param message: The message sent.
        """
        # Ignore messages that don't have mentions in them.
        if not message.role_mentions:
            return

        # Ignore pings from admins, would trust them to not abuse the ping power, but can be removed for safety.
        if message.author.guild_permissions.administrator:
            return

        # Check each role mentioned in the message:
        for role in message.role_mentions:
            if role.id in self.all_role_ids[message.guild.id]:
                self.logger.debug(f"{role.name} pingable role was just mentioned in {message.guild.name}")
                menu_id = self.all_role_ids.get(message.guild.id).get(role.id)
                menu = self.roles.get(menu_id).get("menu")
                menu.last_pinged = datetime.datetime.now()
                await role.edit(mentionable=False)
                self.roles_on_cooldown.append(role)
                self.ensure_tasks()
                db_item = self.db.get(PingableRoles, guild_id=role.guild.id, role_id=role.id)
                if db_item:
                    db_item.total_pings += 1
                    db_item.monthly_pings += 1
                    self.db.update(db_item)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        """
        When a role is deleted by a server administrator, check if the role deleted was a Pingable Role, and if it was, remove
        the Pingable Role from the DB so it is not loaded again when the bot starts.
        :param role: The role that was deleted.
        """
        guild_roles = self.all_role_ids.get(role.guild.id)
        if not guild_roles:
            return

        menu_id = guild_roles.get(role.id)
        if not menu_id:
            return

        await self.remove_pingable_role(role)

        self.logger.info(f"Deleted {role.name} for the guild {role.guild.name} from DB")

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        """
        When the bot joins a server, initialise the default settings used when creating a Pingable Role in the DB.
        :param guild: The server the bot joined.
        """
        if guild not in self.guild_settings:
            db_item = PingableSettings(
                guild_id=guild.id,
                default_poll_length=int(os.getenv("DEFAULT_POLL_LENGTH")),
                default_poll_threshold=int(os.getenv("DEFAULT_POLL_THRESHOLD")),
                default_cooldown_length=int(os.getenv("DEFAULT_COOLDOWN_LENGTH")),
                default_poll_emoji=PINGABLE_POLL_EMOJI.to_dict(),
                default_role_emoji=PINGABLE_ROLE_EMOJI.to_dict()
            )
            self.db.create(db_item)
            self.logger.info(f"Joined new guild: {guild.name} ; Set default pingable settings")

    async def delete_missing_roles(self):
        """
        Check every role loaded from the DB that it still exists at once loaded. If the role does not exist it will be
        deleted from the DB.
        """
        bot_guild_ids = [x.id for x in self.bot.guilds]
        guilds_to_remove = []

        for guild_id in self.all_role_ids:

            if guild_id not in bot_guild_ids:
                # If the guild is not in the bot's guilds, delete every role.
                for role_id in self.all_role_ids.get(guild_id):
                    self.delete_role_from_db(guild_id, role_id)

                continue

            # Iterate through each role and check for its existence.
            guild_role_ids = [x.id for x in await self.bot.get_guild(guild_id).fetch_roles()]
            for role_id in self.all_role_ids.get(guild_id):
                if role_id not in guild_role_ids:
                    self.delete_role_from_db(guild_id, role_id)

            if not self.all_role_ids.get(guild_id):
                guilds_to_remove.append(guilds_to_remove)

        # Remove empty guilds from the dictionary.
        for guild_id in guilds_to_remove:
            self.all_role_ids.pop(guild_id)

    def delete_role_from_db(self, guild_id, role_id):
        """
        Deletes a role from the DB and ensures that the role is not in the internal dicts.
        :param guild_id: The ID of the guild of the role to delete.
        :param role_id: The ID of the role to delete.
        """
        menu_id = self.all_role_ids.get(guild_id, {}).get(role_id)

        if not menu_id or menu_id not in self.roles:
            return

        self.roles.pop(menu_id)
        self.all_role_ids.get(guild_id).pop(role_id)

        db_item = self.db.get(PingableRoles, guild_id=guild_id, role_id=role_id, menu_id=menu_id)
        self.db.delete(db_item)

    async def remove_pingable_role(self, role):
        """
        Deletes a pingable role from the DB and from the cog dictionaries .
        :param role: The role to delete .
        """
        self.logger.debug(f"{role.name} pingable role was just removed from {role.guild.name}")
        db_item = self.db.get(PingableRoles, guild_id=role.guild.id, role_id=role.id)
        menu_id = db_item.menu_id
        menu_data = self.roles.pop(menu_id)
        menu = menu_data.get("menu")
        await menu.message.delete()
        self.db.delete(db_item)
        self.all_role_ids.get(role.guild.id).pop(role.id)

        if role.id in self.roles_on_cooldown:
            self.roles_on_cooldown.remove(role.id)

        if len(self.all_role_ids.get(role.guild.id)) == 0:
            self.all_role_ids.pop(role.guild.id)

    async def initialise_menus(self):
        """
        Once the data has been loaded from the DB it must initialised to an actual reaction menu instance .
        """
        self.logger.debug("Initialising menus into actual menu objects from data base info")

        to_pop = []

        # Load role menus:
        for menu_id in self.roles:
            menu_data = self.roles.get(menu_id).get("menu")
            loaded_menu = await PingableRoleMenu.from_dict(self.bot, menu_data)
            if isinstance(loaded_menu, dict):
                db_item = self.db.get(PingableRoles, guild_id=menu_data.get("guild_id"), role_id=menu_data.get("role_id"))
                self.db.delete(db_item)
                to_pop.append(menu_id)
            else:
                self.roles[menu_id]["menu"] = loaded_menu

        for menu in to_pop:
            self.roles.pop(menu)

        to_pop = []

        # Load poll menus:
        for poll_id in self.polls:
            menu_data = self.polls.get(poll_id).get("menu")
            loaded_menu = await PingableVoteMenu.from_dict(self.bot, menu_data)
            if isinstance(loaded_menu, dict):
                db_item = self.db.get(PingablePolls, guild_id=menu_data.get("guild_id"), menu_id=poll_id)
                self.db.delete(db_item)
                to_pop.append(poll_id)
            else:
                self.polls[poll_id]["menu"] = loaded_menu

        for menu in to_pop:
            self.polls.pop(menu)

        self.logger.info(f"Initialised {len(self.polls)} pingable polls, and {len(self.roles)} pingable roles")

    def load_guild_settings(self) -> Dict:
        """
        Loads the default settings for all the guilds .
        :return:
        """
        self.logger.debug("Loading menu guild settings for all guilds")
        db_data = self.db.list(PingableSettings)

        loaded_data = {}

        for item in db_data:
            loaded_data[item.guild_id] = {
                "poll_length": item.default_poll_length,
                "poll_threshold": item.default_poll_threshold,
                "poll_emoji": MultiEmoji.from_dict(item.default_poll_emoji),
                "role_emoji": MultiEmoji.from_dict(item.default_role_emoji),
                "role_cooldown": item.default_cooldown_length
            }

        self.logger.info(f"Loaded settings for {len(loaded_data)} guild(s)!")

        return loaded_data

    def load_all_polls(self, guild_ids: List[int]) -> Dict:
        """
        Loads any polls that were going on when the bot shutdown for all guilds .
        :param guild_ids: The listr of guild ids that the bot should load .
        :return: A dictionary of all the polls currently happening .
        """
        self.logger.debug("Loading pingable polls interrupted by shutdown")
        loaded_data = {}

        for guild in guild_ids:
            guild_data = self.load_guild_polls(guild)
            loaded_data = {**guild_data, **loaded_data}

        self.logger.info(f"Found {len(loaded_data)} pingable poll menu(s) in DB table")

        return loaded_data

    def load_guild_polls(self, guild_id: int) -> Dict:
        """
         Loads any polls that were going on when the bot shutdown for a specific guild .
        :param guild_id: The guild to load on-going polls for .
        :return: A dictionary of all the polls happening in the guild specified .
        """
        self.logger.debug(f"Loading pingable polls for guild with id: {guild_id}")
        guild_polls: [PingablePolls] = self.db.list(PingablePolls, guild_id=guild_id)

        guild_data = {}

        for item in guild_polls:
            guild_data[item.poll_id] = {"name": item.pingable_name, "menu": item.poll}

        self.logger.debug(f"Loaded {len(guild_data)} pingable polls for guild with id: {guild_id}")

        return guild_data

    def load_all_roles(self, guild_ids: List[int]) -> Dict:
        """
         Loads all the pingable roles for all guilds .
        :param guild_ids: The list of guild ids that the bot is in .
        :return: A dictionary of pingable role reaction menus .
        """
        self.logger.debug("Loading pingable react menus from DB")
        loaded_data = {}

        for guild in guild_ids:
            guild_data = self.load_guild_roles(guild)
            loaded_data = {**guild_data, **loaded_data}

        self.logger.info(f"Found {len(loaded_data)} pingable react menu(s) in DB table")

        return loaded_data

    def load_guild_roles(self, guild_id: int) -> Dict:
        """
         Loads all the pingable roles for a specific guild .
        :param guild_id: The guild to load the roles from .
        :return: A dictionary of pingable role reaction menus .
        """
        self.logger.debug(f"Loading pingable react menus for guild with id: {guild_id}")
        guild_roles: [PingableRoles] = self.db.list(PingableRoles, guild_id=guild_id)

        guild_data = {}

        for item in guild_roles:
            guild_data[item.menu_id] = {"role_id": item.role_id, "menu": item.menu}

        self.logger.debug(f"Loaded {len(guild_data)} pingable reaction menus for guild with id {guild_id}")

        return guild_data

    def all_roles_from_guild_data(self, role_data: Dict) -> Dict:
        """
        Gets a dictionary of guilds and their pingable role ids and the pingable role menus for that role .
        :param role_data: The role data gathered from the DB .
        :return: A dictionary of guilds to pingable role ids and role menu ids .
        """
        self.logger.debug("Getting all pingable roles as dict of Guild->[Role->Menu ID]")
        roles = defaultdict(dict)

        for menu_id in role_data:
            menu_data = role_data.get(menu_id)
            guild_id = menu_data.get("menu").get("guild_id")
            role_id = menu_data.get("role_id")
            roles[guild_id][role_id] = menu_id

        self.logger.info(f"Found pingable roles in {len(roles)} guild(s)")

        return roles

    async def get_menu_from_role_ping(self, context: commands.Context, role: Role):
        """
        Get a reaction menu from a role mention .
        :param context: The context of the command .
        :param role: The role that was mentioned .
        :return: The reaction menu of the role .
        """
        guild_id = context.guild.id
        if not self.all_role_ids.get(guild_id):
            await context.reply(self.user_strings["no_pingable_roles"])
            return None

        menu_id = self.all_role_ids.get(guild_id).get(role.id)
        if not menu_id:
            await context.reply(self.user_strings["invalid_role"])
            return None

        role_menu = self.roles.get(menu_id).get("menu")
        return role_menu

    async def role_mentions_are_valid(self, context: commands.Context):
        """
        Checks if the role mentions in the message are valid mentions or if they contain mentions that are not pingable roles .
        :param context: The context of the command .
        :return: A boolean of if the mentioned roles are valid pingable roles .
        """
        role_mentions = context.message.role_mentions
        if not role_mentions:
            await context.reply(self.user_strings["no_roles_given"])
            return False

        guild_roles = self.all_role_ids.get(context.guild.id)
        if not guild_roles:
            await context.reply(self.user_strings["no_pingable_roles"])
            return False
        return True

    def ensure_tasks(self):
        """
        Ensure that the repeatable tasks the bot needs to run are running.
        """
        if not self.check_poll.is_running() or self.check_poll.is_being_cancelled():
            self.check_poll.start()

        if not self.check_cooldown.is_running() or self.check_cooldown.is_being_cancelled():
            self.check_cooldown.start()

    @tasks.loop(seconds=TASK_INTERVAL)
    async def check_poll(self):
        """
        Checks active polls to see if they have passed their poll length and should be finished .
        """
        if len(self.polls) == 0:
            self.check_poll.cancel()
            self.check_poll.stop()
            return

        current_time = datetime.datetime.now()

        polls_ids_to_remove = []

        for poll_id in self.polls:
            if self.polls.get(poll_id).get("menu").end_time <= current_time:
                self.logger.info(
                    f"Poll for pingable role {self.polls.get(poll_id).get('menu').name} is over, checking results!"
                )
                polls_ids_to_remove.append(poll_id)
                await self.finish_poll(self.polls.get(poll_id).get("menu"))

        for poll_id in polls_ids_to_remove:
            self.polls.pop(poll_id)

    @tasks.loop(seconds=TASK_INTERVAL)
    async def check_cooldown(self):
        """
        Checks roles that are currently on cooldown and if they should come off cooldown .
        """
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
                roles_to_remove.append(role)
                self.logger.info(f"{role.name} role is no longer on cooldown!")
                await role.edit(mentionable=True)

        for role in roles_to_remove:
            self.roles_on_cooldown.remove(role)

    @tasks.loop(hours=24)
    async def monthly_ping_report(self):
        """
        Runs the metrics for all the pingable roles for the last month .
        """
        today = datetime.datetime.today()

        if today.day != 1:
            return

        embed_base = Embed(
            title="Monthly !pingme Report",
            description="The number of times each !pingme role was pinged in the last month"
        )
        embed_base.colour = Colour.random()
        embed_base.footer(text=f"Ping report for {today.strftime('%B %Y')}")

        for guild in self.bot.guilds:
            guild_info = self.db.get(GuildInfo, guild_id=guild.id)
            if not guild_info or not guild_info.log_channel_id:
                continue

            guild_roles = self.db.list(PingableRoles, guild_id=guild.id)
            guild_embed = embed_base.copy()
            for pingable_role in guild_roles:
                role_instance = guild.get_role(pingable_role.role_id)
                guild_embed.add_field(
                    name=role_instance.name,
                    value=f"{role_instance.mention}\n{pingable_role.monthly_pings} pings"
                )
                pingable_role.monthly_pings = 0

            if guild_roles:
                log_channel = guild.get_channel(guild_info.log_channel_id)
                if not log_channel:
                    log_channel = await guild.fetch_channel(guild_info.log_channel_id)
                await log_channel.send(embed=guild_embed)

    async def finish_poll(self, poll_to_finish):
        """
        Finalises a poll and checks if the role that is for should be created or if the poll should just be deleted .
        :param poll_to_finish: The poll that has finished .
        """
        channel = poll_to_finish.message.channel
        threshold = self.guild_settings.get(channel.guild.id).get("poll_threshold")
        embed = await poll_to_finish.generate_result_embed(THRESHOLD_EMOJI, threshold)

        await channel.send(embed=embed)

        total_votes = await poll_to_finish.get_total_votes()

        if total_votes >= threshold:
            self.logger.info(f"Pingable poll with name {poll_to_finish.name} had more votes than the voting threshold!")
            role = await channel.guild.create_role(name=poll_to_finish.name + PINGABLE_ROLE_SUFFIX, mentionable=True)
            await self.create_reaction_menu(role, channel)
            await self.give_roles_to_reacts(poll_to_finish.message, role)
            self.logger.debug(f"Saved new pingable role information for {role.name} to DB!")

        db_item = self.db.get(PingablePolls, guild_id=channel.guild.id, poll_id=poll_to_finish.id)
        self.db.delete(db_item)
        await poll_to_finish.message.delete()

    async def create_reaction_menu(self, role, channel):
        """
        Creates a reaction menu for a given role and in a given channel .
        :param role: The role to create the reaction menu for .
        :param channel: The channel to post the reaction menu to .
        """
        current_menu = PingableRoleMenu(
            pingable_role=role,
            ping_cooldown=self.guild_settings.get(channel.guild.id).get("role_cooldown"),
            title=f"{role.name} Role React",
            description="React to this message to get this pingable role."
        )

        current_menu.add_option(self.guild_settings.get(channel.guild.id).get("role_emoji"), role)
        await current_menu.finalise_and_send(self.bot, channel)
        self.logger.info(f"Created a new reaction menu and role for the role: {role.name}")

        if not self.all_role_ids.get(channel.guild.id):
            self.all_role_ids[channel.guild.id] = {}

        self.all_role_ids[channel.guild.id][role.id] = current_menu.id
        self.roles[current_menu.id] = {"role_id": role.id, "menu": current_menu}

        db_item = PingableRoles(
            guild_id=channel.guild.id,
            role_id=role.id,
            menu_id=current_menu.id,
            menu=current_menu.to_dict(),
            monthly_pings=0,
            total_pings=0
        )
        self.db.create(db_item)

    @staticmethod
    async def give_roles_to_reacts(message, role):
        """
        Gives the given role to the reactees of a message.
        :param message: The message to get the user reactions from.
        :param role: The role to give the users.
        """
        for react in message.reactions:
            async for user in react.users():
                if not user.bot:
                    await user.add_roles(role)

    def role_exists(self, name: str) -> bool:
        """
        Checks if there is a role with the name given as a pingable role .
        :param name:
        :return:
        """
        # Check current polls:
        for menu_id in self.polls:
            menu_name = self.polls.get(menu_id).get("name")
            if name.lower() in menu_name.lower():
                return True

        for menu_id in self.roles:
            menu = self.roles.get(menu_id).get("menu")
            if name.lower() in menu.role.name.lower():
                return True

        return False

    async def get_guild_in_settings(self, context):
        """
        Gets the current guild settings for a guild. If the guild is not in the settings DB, returns None.
        :param context: The context of the command.
        :return: A Pingable_settings DB item if the guild is in the DB, else None.
        """
        db_item = self.db.get(PingableSettings, guild_id=context.guild.id)
        if not db_item:
            await context.send(
                self.user_strings["needs_initialising"].format(
                    prefix=self.bot.command_prefix,
                    command="pingme settings default-settings"
                )
            )
            return None
        return db_item

    @commands.group(name="pingme", invoke_without_command=True)
    async def ping_me(self, context: commands.Context):
        """
        The command group used to make all commands sub-commands .
        :param context: The context of the command .
        """
        pass

    @ping_me.group(name="settings")
    @commands.has_permissions(administrator=True)
    async def ping_me_settings(self, context: commands.Context):
        """
        The command group used to make all settings commands into sub-commands .
        :param context: The context of the command .
        """
        pass

    @ping_me_settings.command(name="get-settings")
    async def get_guild_settings(self, context: commands.Context):
        """
        Returns a list of the current settings in a guild .
        :param context: The context of the command .
        """
        guild_settings = self.guild_settings.get(context.guild.id)
        if not guild_settings:
            await context.send(
                self.user_strings["needs_initialising"].format(prefix=self.bot.command_prefix,
                                                               command="default-settings")
            )
            return

        embed = Embed(
            title="Current Pingable Roles Settings",
            description="These are the current pingable settings for this server"
        )
        # An alternative visual option for displaying the settings:
        # e.add_field(
        #         name=f"• Poll Emoji: {guild_settings.get('poll_emoji').discord_emoji}",
        #         value=f"**• Role Emoji: {guild_settings.get('role_emoji').discord_emoji}**",
        #         inline=False
        # )
        # e.add_field(
        #         name=f"• Poll Length Seconds: {guild_settings.get('poll_length')}",
        #         value=f"**• Poll Vote Threshold: {guild_settings.get('vote_threshold')}**",
        #         inline=False
        # )
        # e.add_field(
        #         name=f"• Role Cooldown Seconds: {guild_settings.get('role_cooldown')}",
        #         value="​",
        #         inline=False
        # )
        embed.add_field(name=f"• Poll Emoji: {guild_settings.get('poll_emoji').discord_emoji}", value="​", inline=False)
        embed.add_field(name=f"• Role Emoji: {guild_settings.get('role_emoji').discord_emoji}", value="​", inline=False)
        embed.add_field(name=f"• Poll Length Seconds: {guild_settings.get('poll_length')}", value="​", inline=False)
        embed.add_field(name=f"• Poll Vote Threshold: {guild_settings.get('poll_threshold')}", value="​", inline=False)
        embed.add_field(name=f"• Role Cooldown Seconds: {guild_settings.get('role_cooldown')}", value="​", inline=False)
        await context.send(embed=embed)

    @ping_me_settings.command(name="default-settings")
    async def default_settings(self, context: commands.Context):
        """
        Sets the settings for a guild back to the default settings .
        :param context: The context of the command .
        """
        guild_id = context.guild.id

        exists = self.db.get(PingableSettings, guild_id=guild_id)

        if exists:
            exists.default_poll_length = int(os.getenv("DEFAULT_POLL_LENGTH"))
            exists.default_poll_threshold = int(os.getenv("DEFAULT_POLL_THRESHOLD"))
            exists.default_cooldown_length = int(os.getenv("DEFAULT_COOLDOWN_LENGTH"))
            exists.default_poll_emoji = PINGABLE_POLL_EMOJI.to_dict()
            exists.default_role_emoji = PINGABLE_ROLE_EMOJI.to_dict()
            self.db.update(exists)
        else:
            current_item = PingableSettings(
                guild_id=guild_id,
                default_poll_length=int(os.getenv("DEFAULT_POLL_LENGTH")),
                default_poll_threshold=int(os.getenv("DEFAULT_POLL_THRESHOLD")),
                default_cooldown_length=int(os.getenv("DEFAULT_COOLDOWN_LENGTH")),
                default_poll_emoji=PINGABLE_POLL_EMOJI.to_dict(),
                default_role_emoji=PINGABLE_ROLE_EMOJI.to_dict()
            )
            self.db.create(current_item)

        self.guild_settings[context.guild.id] = {}
        self.guild_settings[context.guild.id]["poll_length"] = int(os.getenv("DEFAULT_POLL_LENGTH"))
        self.guild_settings[context.guild.id]["poll_threshold"] = int(os.getenv("DEFAULT_POLL_THRESHOLD"))
        self.guild_settings[context.guild.id]["role_cooldown"] = int(os.getenv("DEFAULT_COOLDOWN_LENGTH"))
        self.guild_settings[context.guild.id]["poll_emoji"] = PINGABLE_POLL_EMOJI
        self.guild_settings[context.guild.id]["role_emoji"] = PINGABLE_ROLE_EMOJI

        self.logger.info(f"{context.guild.name} has had its pingable settings set back to defaults!")
        await context.reply(self.user_strings["default_settings_set"])

    @ping_me_settings.command(name="poll-length")
    async def set_poll_length(self, context: commands.Context, poll_length: int):
        """
        Sets the default poll length setting for a guild to the given value .
        :param context: The context of the command .
        :param poll_length: The number of seconds to set the default poll length to .
        """
        db_item = await self.get_guild_in_settings(context)
        if not db_item:
            return
        db_item.default_poll_length = poll_length
        self.db.update(db_item)

        self.guild_settings[context.guild.id]["poll_length"] = poll_length

        await context.reply(self.user_strings["set_poll_length"].format(poll_length=poll_length))
        self.logger.info(f"Set {context.guild.name} default poll length to {poll_length}s")

    @ping_me_settings.command(name="poll-threshold")
    async def set_poll_threshold(self, context: commands.Context, vote_threshold: int):
        """
        Sets the poll vote threshold setting for a guild to the given value .
        :param context: The context of the command .
        :param vote_threshold: The number of votes needed to create a role .
        """
        db_item = await self.get_guild_in_settings(context)
        if not db_item:
            return
        db_item.default_poll_threshold = vote_threshold
        self.db.update(db_item)

        self.guild_settings[context.guild.id]["poll_threshold"] = vote_threshold

        await context.reply(self.user_strings["set_poll_threshold"].format(vote_threshold=vote_threshold))
        self.logger.info(f"Set {context.guild.name} poll threshold to {vote_threshold} votes")

    @ping_me_settings.command(name="ping-cooldown")
    async def set_role_cooldown(self, context: commands.Context, role_cooldown: int):
        """
        Sets the default role ping cooldown setting for a guild to the given value .
        :param context: The context of the command .
        :param role_cooldown: The number of seconds a role will be on cooldown for .
        """
        db_item = self.db.get(PingableSettings, guild_id=context.guild.id)
        if not db_item:
            await context.send(
                self.user_strings["needs_initialising"].format(
                    prefix=self.bot.command_prefix,
                    command="pingme settings default-settings"
                )
            )
            return
        db_item.default_cooldown_length = role_cooldown
        self.db.update(db_item)

        self.guild_settings[context.guild.id]["role_cooldown"] = role_cooldown

        await context.reply(self.user_strings["set_role_cooldown"].format(cooldown=role_cooldown))
        self.logger.info(f"Set {context.guild.name} pingable role cooldown to {role_cooldown}s")

    @ping_me_settings.command(name="poll-emoji")
    async def set_poll_emoji(self, context: commands.Context, poll_emoji: MultiEmoji):
        """
        Sets the poll voting emoji for a guild to the given emoji .
        :param context: The context of the command .
        :param poll_emoji: The emoji to use in the role polls .
        """
        if poll_emoji == THRESHOLD_EMOJI:
            # Can't use the threshold emoji as the poll emoji as it is used to count votes .
            await context.reply(self.user_strings["reserved_emoji"].format(poll_emoji.discord_emoji))
            return

        db_item = await self.get_guild_in_settings(context)
        if not db_item:
            return
        db_item.default_poll_emoji = poll_emoji.to_dict()
        self.db.update(db_item)

        self.guild_settings[context.guild.id]["poll_emoji"] = poll_emoji

        await context.reply(self.user_strings["set_poll_emoji"].format(emoji=poll_emoji.discord_emoji))
        self.logger.info(f"Set {context.guild.name} poll emoji to {poll_emoji.name}")

    @ping_me_settings.command(name="role-emoji")
    async def set_role_emoji(self, context: commands.Context, role_emoji: MultiEmoji):
        """
        Sets the default role reaction emoji for a guild to the given emoji .
        :param context: The context of the command .
        :param role_emoji: The emoji to use in the role reaction menus .
        """
        db_item = await self.get_guild_in_settings(context)
        if not db_item:
            return
        db_item.default_role_emoji = role_emoji.to_dict()
        self.db.update(db_item)

        self.guild_settings[context.guild.id]["role_emoji"] = role_emoji

        await context.reply(self.user_strings["set_role_emoji"].format(emoji=role_emoji.discord_emoji))
        self.logger.info(f"Set {context.guild.name} role emoji to {role_emoji.name}")

    @ping_me.command(name="create-role")
    async def create_role(self, context: commands.Context, role_name: str, poll_length: int = None):
        """
        Creates a new role poll for a role with the name given . If no poll length is given, the guild default
        poll length is used .
        :param context: The context of the command .
        :param role_name: The name of the role to create .
        :param poll_length: The number of seconds to run the poll for .
        """
        guild_settings = self.guild_settings.get(context.guild.id)

        if not guild_settings:
            await context.send(
                self.user_strings["needs_initialising"].format(
                    prefix=self.bot.command_prefix,
                    command="pingme settings default-settings"
                )
            )
            return

        if self.role_exists(role_name):
            await context.reply(self.user_strings["already_exists"].format(role=role_name))
            return

        if poll_length is None:
            poll_length = guild_settings.get("poll_length")

        vote_threshold = guild_settings.get("poll_threshold")

        role_poll = PingableVoteMenu(
            pingable_name=role_name,
            auto_enable=True,
            title=PINGABLE_POLL_TITLE.format(role_name),
            description=PINGABLE_POLL_DESCRIPTION.format(vote_num=vote_threshold),
            poll_length=poll_length,
            author=context.author
        )

        role_poll.add_option(self.guild_settings.get(context.guild.id).get("poll_emoji"), role_name)
        await role_poll.finalise_and_send(self.bot, context.channel)
        db_item = PingablePolls(
            guild_id=context.guild.id,
            pingable_name=role_name,
            poll_id=role_poll.id,
            poll=role_poll.to_dict()
        )
        self.db.create(db_item)
        self.polls[role_poll.id] = {"name": role_name, "menu": role_poll}
        self.ensure_tasks()
        await context.reply(self.user_strings["create_success"])
        self.logger.info(f"Created a new poll for a pingable role with the name {role_name} in guild {context.guild.name}")

    @ping_me.command(name="delete-role")
    @commands.has_permissions(administrator=True)
    async def delete_role(self, context: commands.Context):
        """
        Deletes one or many pingable roles and their role reaction menus . This is done using the message.role_mentions attr
        instead of using function params.
        :param context: The context of the command .
        """
        if not await self.role_mentions_are_valid(context):
            return

        deleted_roles = []

        for role in context.message.role_mentions:
            db_item = self.db.get(PingableRoles, guild_id=context.guild.id, role_id=role.id)
            if not db_item:
                await context.send(self.user_strings["not_pingable_role"].format(role=role.name))
            else:
                deleted_roles.append(role.name)
                await role.delete()

        if not deleted_roles:
            return

        deleted_string = str(deleted_roles).replace("]", "").replace("[", "")

        await context.reply(self.user_strings["role_delete_success"].format(deleted_roles=deleted_string))
        self.logger.info(f"Deleted pingable roles: {deleted_string} in guild {context.guild.name}")

    @ping_me.command(name="convert-role")
    @commands.has_permissions(administrator=True)
    async def convert_role(self, context: commands.Context):
        """
        Converts an existing non-pingable role into a pingable role with a reaction menu for it .This is done using the
        message.role_mentions attr instead of using function params.
        :param context: The context of the command .
        """
        if not context.message.role_mentions:
            await context.reply(self.user_strings["no_roles_given"])
            return

        converted_roles = []

        for role in context.message.role_mentions:
            db_item = self.db.get(PingableRoles, guild_id=context.guild.id, role_id=role.id)
            if db_item:
                await context.send(self.user_strings["already_exists"].format(role=role.name))
            else:
                await self.create_reaction_menu(role, context.channel)
                converted_roles.append(role.name)

        if not converted_roles:
            return
        converted_string = str(converted_roles).replace("]", "").replace("[", "")

        await context.reply(self.user_strings["role_convert_success"].format(converted_roles=converted_string))
        self.logger.info(f"Converted pingable roles: {converted_string} in guild {context.guild.name}")

    @ping_me.command(name="convert-pingable")
    @commands.has_permissions(administrator=True)
    async def convert_pingable(self, context: commands.Context):
        """
        Converts a pingable role into a non-cooldown limited regular role . This is done using the message.role_mentions attr
        instead of using function params.
        :param context: The context of the command .
        :return:
        """
        if not await self.role_mentions_are_valid(context):
            return

        converted_roles = []

        for role in context.message.role_mentions:
            pingable_role = self.all_role_ids.get(context.guild.id).get(role.id)
            if not pingable_role:
                await context.send(self.user_strings["not_pingable_role"].format(role=role.name))
            else:
                converted_roles.append(role.name)
                await self.remove_pingable_role(role)

        if not converted_roles:
            return

        converted_string = str(converted_roles).replace("]", "").replace("[", "")

        await context.reply(self.user_strings["pingable_convert_success"].format(converted_roles=converted_string))
        self.logger.info(f"Converted pingable roles: {converted_string} in guild {context.guild.name}")

    @ping_me.command(name="role-cooldown")
    @commands.has_permissions(administrator=True)
    async def change_pingable_role_cooldown(self, context: commands.Context, pingable_role: Role, cooldown_seconds: int):
        """
        Changes the number of seconds a role will be on cooldown if it is mentioned .
        :param context: The context of the command .
        :param pingable_role: The role to change the cooldown for .
        :param cooldown_seconds: The number of seconds for the command to be on cooldown for .
        """
        role_menu = await self.get_menu_from_role_ping(context, pingable_role)
        role_menu.cooldown = cooldown_seconds

        db_item = self.db.get(PingableRoles, guild_id=context.guild.id, role_id=pingable_role.id)
        if db_item:
            db_item.menu = role_menu.to_dict()
            self.db.update(db_item)
        else:
            db_item = PingableRoles(
                guild_id=context.guild.id,
                role_id=pingable_role.id,
                menu_id=role_menu.id,
                menu=role_menu.to_dict(),
                monthly_pings=0,
                total_pings=0
            )
            self.db.create(db_item)

        await context.reply(
            self.user_strings["role_cooldown_updated"].format(role=pingable_role.name,
                                                              seconds=cooldown_seconds)
        )

    @ping_me.command(name="role-emoji")
    @commands.has_permissions(administrator=True)
    async def change_pingable_role_emoji(self, context: commands.Context, pingable_role: Role, role_emoji: MultiEmoji):
        """
        Change the emoji used in the reaction menu of a pingable role .
        :param context: The context of the command .
        :param pingable_role: The pingable role to change the emoji of .
        :param role_emoji: The emoji to set the reaction to .
        """
        role_menu = await self.get_menu_from_role_ping(context, pingable_role)
        if not role_menu:
            return
        await role_menu.disable_menu(self.bot)
        current_emoji_id = list(role_menu.options.keys())[0]
        current_emoji = role_menu.options.get(current_emoji_id).get("emoji")
        role_menu.remove_option(current_emoji)
        role_menu.add_option(role_emoji, role_menu.role)
        await role_menu.enable_menu(self.bot)
        await context.reply(
            self.user_strings["role_emoji_updated"].format(role=pingable_role.name,
                                                           emoji=role_emoji.discord_emoji)
        )

    @ping_me.command(name="disable-role")
    @commands.has_permissions(administrator=True)
    async def disable_pingable_role(self, context: commands.Context):
        """
        Stops a pingable role from being mentioned and from users getting the pingable role . This is done using the
        message.role_mentions attr instead of using function params.
        :param context: The context of the command .
        """
        if not await self.role_mentions_are_valid(context):
            return

        disabled_roles = []

        for role in context.message.role_mentions:
            menu_id = self.all_role_ids.get(context.guild.id).get(role.id)
            if not menu_id:
                await context.send(self.user_strings["not_pingable_role"].format(role=role.name))
            else:
                await role.edit(mentionable=False)
                await self.roles.get(menu_id).get("menu").disable_menu(self.bot)
                disabled_roles.append(role.name)

        disabled_string = str(disabled_roles).replace("[", "").replace("]", "")
        await context.reply(self.user_strings["roles_disabled"].format(disabled_roles=disabled_string))

    @ping_me.command(name="enable-role")
    @commands.has_permissions(administrator=True)
    async def enabled_pingable_roles(self, context: commands.Context):
        """
        Allows a pingable role to be mentioned and for users to be able to get the pingable role . This is done using the
        message.role_mentions attr instead of using function params.
        :param context:
        :return:
        """
        if not await self.role_mentions_are_valid(context):
            return

        enabled_roles = []

        for role in context.message.role_mentions:
            menu_id = self.all_role_ids.get(context.guild.id).get(role.id)
            if not menu_id:
                await context.send(self.user_strings["not_pingable_role"].format(role=role.name))
            else:
                await role.edit(mentionable=True)
                await self.roles.get(menu_id).get("menu").enable_menu(self.bot)
                enabled_roles.append(role.name)

        enabled_string = str(enabled_roles).replace("[", "").replace("]", "")
        await context.reply(self.user_strings["roles_enabled"].format(enabled_roles=enabled_string))

    @change_pingable_role_cooldown.error
    @set_poll_threshold.error
    @set_poll_length.error
    @create_role.error
    async def integer_parse_error(self, context: commands.Context, error: commands.CommandError):
        """
        Error handling for any integer parsing .
        :param context: The context of the command .
        :param error: The error that occurred .
        """
        if isinstance(error, ValueError):
            self.logger.warning(
                "User attempted to give non-integer value as poll length in the following message: %s",
                context.message.content
            )
            await context.reply(self.user_strings["invalid_argument"])
            return

        await context.reply(self.command_error_message)
        raise error

    @change_pingable_role_cooldown.error
    async def role_cooldown_error(self, context: commands.Context, error: commands.CommandError):
        """
        Occurs when the role parsed to change pingable role cooldown command is not a role .
        :param context: The context of the command .
        :param error: The error that occurred .
        """
        if isinstance(error, commands.RoleNotFound):
            # The position of the role arg in the change_pingable_role_cooldown command
            role_arg_index = 0
            await self.invalid_role_error(context, role_arg_index, self.change_pingable_role_cooldown)

    @change_pingable_role_emoji.error
    async def role_emoji_error(self, context: commands.Context, error: commands.CommandError):
        """
        Occurs when the role parsed to change pingable role emoji command is not a role .
        :param context: The context of the command .
        :param error: The error that occurred .
        """
        if isinstance(error, commands.RoleNotFound):
            # The position of the role arg in the change_pingable_role_emoji command
            role_arg_index = 0
            await self.invalid_role_error(context, role_arg_index, self.change_pingable_role_emoji)

    async def invalid_role_error(self, context: commands.Context, role_arg_index: int, command):
        """
        Handles when a role given to a command is not a role .
        :param context: The context of the failed command .
        :param role_arg_index: The index of the role argument in the failed command .
        :param command: The command function that failed .
        """
        self.logger.warning("The argument parsed was not a Role, trying to find a role with the given value")

        attempted_arg, command_args = get_attempted_arg(context.args, role_arg_index)
        try:
            role_id = int(attempted_arg)
            for role in context.guild.roles:
                if role.id == role_id:
                    # Retry the command and parse the given role_id as an actual role object.
                    self.logger.info(f"Retrying {context.command.name} with found role: {role.name}")
                    command_args[role_arg_index] = role
                    await command(context, *command_args)
                    return
            raise ValueError
        except ValueError:
            self.logger.error(f"Unable to find a role with id: {attempted_arg}")
            await context.reply(self.user_strings["invalid_role"])
            return


def setup(bot):
    bot.add_cog(PingableRolesCog(bot))
