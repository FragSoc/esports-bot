import datetime
import logging
import os
from collections import defaultdict
from typing import Dict, List

from discord import Embed, Role
from discord.ext import commands, tasks

from esportsbot.DiscordReactableMenus.EmojiHandler import MultiEmoji
from esportsbot.DiscordReactableMenus.PingableMenus import PingableRoleMenu, PingableVoteMenu
from esportsbot.db_gateway import DBGatewayActions

# The emoji to use in the role menu:
from esportsbot.lib.discordUtil import get_attempted_arg
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

TASK_INTERVAL = 10


class PingableRolesCog(commands.Cog):
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
                self.logger.debug(f"{role.name} pingable role was just mentioned in {message.guild.name}")
                menu_id = self.all_role_ids.get(message.guild.id).get(role.id)
                menu = self.roles.get(menu_id).get("menu")
                menu.last_pinged = datetime.datetime.now()
                await role.edit(mentionable=False)
                self.roles_on_cooldown.append(role)
                self.ensure_tasks()

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        guild_roles = self.all_role_ids.get(role.guild.id)
        if not guild_roles:
            return

        menu_id = guild_roles.get(role.id)
        if not menu_id:
            return

        await self.remove_pingable_role(role)

        self.logger.info(f"Deleted {role.name} for the guild {role.guild.name} from DB")

    async def remove_pingable_role(self, role):
        self.logger.debug(f"{role.name} pingable role was just removed from {role.guild.name}")
        db_item = self.db.get(Pingable_roles, guild_id=role.guild.id, role_id=role.id)
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
        self.logger.debug("Initialising menus into actual menu objects from data base info")

        # Load role menus:
        for menu_id in self.roles:
            menu_data = self.roles.get(menu_id).get("menu")
            self.roles[menu_id]["menu"] = await PingableRoleMenu.from_dict(self.bot, menu_data)

        # Load poll menus:
        for poll_id in self.polls:
            menu_data = self.polls.get(poll_id).get("menu")
            self.polls[poll_id]["menu"] = await PingableVoteMenu.from_dict(self.bot, menu_data)

        self.logger.info("All menus initialised!")

    def load_guild_settings(self) -> Dict:
        self.logger.debug("Loading menu guild settings for all guilds")
        db_data: [Pingable_settings] = self.db.list(Pingable_settings)

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
        self.logger.debug("Loading pingable polls interrupted by shutdown")
        loaded_data = {}

        for guild in guild_ids:
            guild_data = self.load_guild_polls(guild)
            loaded_data = {**guild_data, **loaded_data}

        self.logger.info(f"Loaded {len(loaded_data)} pingable poll(s)!")

        return loaded_data

    def load_guild_polls(self, guild_id: int) -> Dict:
        self.logger.debug(f"Loading pingable polls for guild with id: {guild_id}")
        guild_polls: [Pingable_polls] = self.db.list(Pingable_polls, guild_id=guild_id)

        guild_data = {}

        for item in guild_polls:
            guild_data[item.poll_id] = {"name": item.pingable_name, "menu": item.poll}

        self.logger.debug(f"Loaded {len(guild_data)} pingable polls for guild with id: {guild_id}")

        return guild_data

    def load_all_roles(self, guild_ids: List[int]) -> Dict:
        self.logger.debug("Loading pingable react menus from DB")
        loaded_data = {}

        for guild in guild_ids:
            guild_data = self.load_guild_roles(guild)
            loaded_data = {**guild_data, **loaded_data}

        self.logger.info(f"Loaded {len(loaded_data)} pingable react menu(s) in {len(guild_ids)} guild(s)")

        return loaded_data

    def load_guild_roles(self, guild_id: int) -> Dict:
        self.logger.debug(f"Loading pingable react menus for guild with id: {guild_id}")
        guild_roles: [Pingable_roles] = self.db.list(Pingable_roles, guild_id=guild_id)

        guild_data = {}

        for item in guild_roles:
            guild_data[item.menu_id] = {"role_id": item.role_id, "menu": item.menu}

        self.logger.debug(f"Loaded {len(guild_data)} pingable reaction menus for guild with id {guild_id}")

        return guild_data

    def all_roles_from_guild_data(self, role_data: Dict) -> Dict:
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
        if not self.check_poll.is_running() or self.check_poll.is_being_cancelled():
            self.check_poll.start()

        if not self.check_cooldown.is_running() or self.check_cooldown.is_being_cancelled():
            self.check_cooldown.start()

    @tasks.loop(seconds=TASK_INTERVAL)
    async def check_poll(self):
        if len(self.polls) == 0:
            self.check_poll.cancel()
            self.check_poll.stop()
            return

        current_time = datetime.datetime.now()

        polls_ids_to_remove = []

        for poll_id in self.polls:
            if self.polls.get(poll_id).get("menu").end_time <= current_time:
                self.logger.info(
                    f"Poll for pingable role %s is over, checking results!",
                    self.polls.get(poll_id).get('menu').name
                )
                polls_ids_to_remove.append(poll_id)
                await self.finish_poll(self.polls.get(poll_id).get("menu"))

        for poll_id in polls_ids_to_remove:
            self.polls.pop(poll_id)

    @tasks.loop(seconds=TASK_INTERVAL)
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
                roles_to_remove.append(role)
                self.logger.info(f"{role.name} role is no longer on cooldown!")
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
            self.logger.info(f"Pingable poll with name {poll_to_finish.name} had more votes than the voting threshold!")
            role = await channel.guild.create_role(name=poll_to_finish.name + PINGABLE_ROLE_SUFFIX, mentionable=True)
            await self.create_reaction_menu(role, channel)
            self.logger.debug(f"Saved new pingable role information for {role.name} to DB!")

        db_item = self.db.get(Pingable_polls, guild_id=channel.guild.id, poll_id=poll_to_finish.id)
        self.db.delete(db_item)
        await poll_to_finish.message.delete()

    async def create_reaction_menu(self, role, channel):
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
        db_item = Pingable_roles(
            guild_id=channel.guild.id,
            role_id=role.id,
            menu_id=current_menu.id,
            menu=current_menu.to_dict()
        )
        self.db.create(db_item)

    def role_exists(self, name: str) -> bool:
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

    @commands.group(name="pingme", help="Get and create custom roles with ping cooldown timers.", invoke_without_command=True)
    async def ping_me(self, context: commands.Context):
        pass

    @ping_me.group(name="settings", help="Set default values for this server.")
    @commands.has_permissions(administrator=True)
    async def ping_me_settings(self, context: commands.Context):
        pass

    @ping_me_settings.command(name="get-settings", help="Returns an embed of the current default settings for the server.")
    async def get_guild_settings(self, context: commands.Context):
        guild_settings = self.guild_settings.get(context.guild.id)
        if not guild_settings:
            return

        embed = Embed(
            title="Current Pingable Roles Settings",
            description="These are the current pingable settings for this server"
        )
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

    @ping_me_settings.command(
        name="default-settings",
        help="Resets all settings for this guild to the bot-defined defaults defined in the .env file."
    )
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

        self.logger.info(f"{context.guild.name} has had its pingable settings set back to defaults!")

    @ping_me_settings.command(
        name="poll-length",
        usage="<poll length in seconds>",
        help="Sets the default poll length to the given time in seconds. "
        "Poll lengths can still be overridden by giving the poll length in the `create-poll` command!"
    )
    async def set_poll_length(self, context: commands.Context, poll_length: int):
        db_item = self.db.get(Pingable_settings, guild_id=context.guild.id)
        db_item.default_poll_length = poll_length
        self.db.update(db_item)

        self.guild_settings[context.guild.id]["poll_length"] = poll_length

        await context.reply(self.user_strings["set_poll_length"].format(poll_length=poll_length))
        self.logger.info(f"Set {context.guild.name} default poll length to {poll_length}s")

    @ping_me_settings.command(
        name="poll-threshold",
        usage="<number of votes threshold>",
        help="Sets the number of votes required in a poll for the role to be created."
    )
    async def set_poll_threshold(self, context: commands.Context, vote_threshold: int):
        db_item = self.db.get(Pingable_settings, guild_id=context.guild.id)
        db_item.default_poll_threshold = vote_threshold
        self.db.update(db_item)

        self.guild_settings[context.guild.id]["poll_threshold"] = vote_threshold

        await context.reply(self.user_strings["set_poll_threshold"].format(vote_threshold=vote_threshold))
        self.logger.info(f"Set {context.guild.name} poll threshold to {vote_threshold} votes")

    @ping_me_settings.command(
        name="ping-cooldown",
        usage="<cooldown in seconds>",
        help="Sets the default ping cooldown for any pingable role created with this cog."
    )
    async def set_role_cooldown(self, context: commands.Context, role_cooldown: int):
        db_item = self.db.get(Pingable_settings, guild_id=context.guild.id)
        db_item.default_cooldown_length = role_cooldown
        self.db.update(db_item)

        self.guild_settings[context.guild.id]["role_cooldown"] = role_cooldown

        await context.reply(self.user_strings["set_role_cooldown"].format(cooldown=role_cooldown))
        self.logger.info(f"Set {context.guild.name} pingable role cooldown to {role_cooldown}s")

    @ping_me_settings.command(
        name="poll-emoji",
        usage="<emoji>",
        help="Sets the emoji to be used when creating a poll to vote in."
    )
    async def set_poll_emoji(self, context: commands.Context, poll_emoji: MultiEmoji):
        db_item = self.db.get(Pingable_settings, guild_id=context.guild.id)
        db_item.default_poll_emoji = poll_emoji.to_dict()
        self.db.update(db_item)

        self.guild_settings[context.guild.id]["poll_emoji"] = poll_emoji

        await context.reply(self.user_strings["set_poll_emoji"].format(emoji=poll_emoji.discord_emoji))
        self.logger.info(f"Set {context.guild.name} poll emoji to {poll_emoji.name}")

    @ping_me_settings.command(
        name="role-emoji",
        usage="<emoji>",
        help="Sets the default emoji to be used in the role reaction menu for the pingable role once it has been created."
    )
    async def set_role_emoji(self, context: commands.Context, role_emoji: MultiEmoji):
        db_item = self.db.get(Pingable_settings, guild_id=context.guild.id)
        db_item.default_role_emoji = role_emoji.to_dict()
        self.db.update(db_item)

        self.guild_settings[context.guild.id]["role_emoji"] = role_emoji

        await context.reply(self.user_strings["set_role_emoji"].format(emoji=role_emoji.discord_emoji))
        self.logger.info(f"Set {context.guild.name} role emoji to {role_emoji.name}")

    @ping_me.command(
        name="create-role",
        usage="<role name> [Optional: poll length in seconds]",
        help="Creates a new poll to create a role if the number of votes has surpassed the server's threshold after the"
        " poll length has passed."
    )
    async def create_role(self, context: commands.Context, role_name: str, poll_length: int = None):
        if self.role_exists(role_name):
            await context.reply(self.user_strings["already_exists"].format(role=role_name))
            return

        if poll_length is None:
            poll_length = self.guild_settings.get(context.guild.id).get("poll_length")

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
        self.logger.info(f"Created a new poll for a pingable role with the name {role_name} in guild {context.guild.name}")

    @ping_me.command(
        name="delete-role",
        usage="<one or many role mentions>",
        help="Deletes the mentioned roles from the server. Cannot be used to delete non-pingable roles."
    )
    @commands.has_permissions(administrator=True)
    async def delete_role(self, context: commands.Context):
        if not await self.role_mentions_are_valid(context):
            return

        deleted_roles = []

        for role in context.message.role_mentions:
            db_item = self.db.get(Pingable_roles, guild_id=context.guild.id, role_id=role.id)
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

    @ping_me.command(
        name="convert-role",
        usage="<One or many role mentions>",
        help="Converts the mentioned roles into pingable roles and creates their reaction menus."
    )
    @commands.has_permissions(administrator=True)
    async def convert_role(self, context: commands.Context):
        if not context.message.role_mentions:
            await context.reply(self.user_strings["no_roles_given"])
            return

        converted_roles = []

        for role in context.message.role_mentions:
            db_item = self.db.get(Pingable_roles, guild_id=context.guild.id, role_id=role.id)
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

    @ping_me.command(
        name="convert-pingable",
        usage="<one or many role mentions>",
        help="Converts the mentioned roles from pingable roles into normal roles and deletes their reaction menus."
    )
    @commands.has_permissions(administrator=True)
    async def convert_pingable(self, context: commands.Context):
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

    @ping_me.command(
        name="role-cooldown",
        usage="<role mention | role ID> <cooldown in seconds>",
        help="Sets the ping cooldown for a specific role which overrides the server default for that role."
    )
    @commands.has_permissions(administrator=True)
    async def change_pingable_role_cooldown(self, context: commands.Context, pingable_role: Role, cooldown_seconds: int):
        role_menu = await self.get_menu_from_role_ping(context, pingable_role)
        role_menu.cooldown = cooldown_seconds

        db_item = self.db.get(Pingable_roles, guild_id=context.guild.id, role_id=pingable_role.id)
        if db_item:
            db_item.menu = role_menu.to_dict()
            self.db.update(db_item)
        else:
            db_item = Pingable_roles(
                guild_id=context.guild.id,
                role_id=pingable_role.id,
                menu_id=role_menu.id,
                menu=role_menu.to_dict()
            )
            self.db.create(db_item)

        await context.reply(
            self.user_strings["role_cooldown_updated"].format(role=pingable_role.name,
                                                              seconds=cooldown_seconds)
        )

    @ping_me.command(
        name="role-emoji",
        usage="<role mention | role ID> <emoji>",
        help="Sets the emoji to use in the reaction menu for the given role."
    )
    @commands.has_permissions(administrator=True)
    async def change_pingable_role_emoji(self, context: commands.Context, pingable_role: Role, role_emoji: MultiEmoji):
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

    @ping_me.command(
        name="disable-role",
        usage="<one or many role mentions>",
        help="Disables the roles mentioned from being mentioned by non-administrators and disables their reaction menus."
    )
    @commands.has_permissions(administrator=True)
    async def disable_pingable_role(self, context: commands.Context):
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

    @ping_me.command(
        name="enable-role",
        usage="<one or many role mentions>",
        help="Enabled the roles mentioned to be mentioned by non-administrators and "
        "allows their reaction menus to be reacted to."
    )
    @commands.has_permissions(administrator=True)
    async def enabled_pingable_roles(self, context: commands.Context):
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
        if isinstance(error, commands.RoleNotFound):
            # The position of the role arg in the change_pingable_role_cooldown command
            role_arg_index = 0
            await self.invalid_role_error(context, role_arg_index, self.change_pingable_role_cooldown)

    @change_pingable_role_emoji.error
    async def role_emoji_error(self, context: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.RoleNotFound):
            # The position of the role arg in the change_pingable_role_emoji command
            role_arg_index = 0
            await self.invalid_role_error(context, role_arg_index, self.change_pingable_role_emoji)

    async def invalid_role_error(self, context: commands.Context, role_arg_index: int, command):
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
