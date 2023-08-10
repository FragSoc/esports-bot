import logging
import os
from asyncio import create_task, Task
from asyncio import sleep as async_sleep
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import IntEnum

from discord import Color, Embed, Interaction, Role, Message
from discord.app_commands import command, default_permissions, describe, guild_only, rename, autocomplete
from discord.ext.commands import Bot, GroupCog
from discord.ui import View, Button

from common.discord import respond_or_followup, check_interaction_prefix, UserRolesConfigTransformer
from common.io import load_cog_toml
from database.gateway import DBSession
from database.models import UserRolesConfig, UserRolesRoles

COG_STRINGS = load_cog_toml(__name__)
INTERACTION_PREFIX = f"{__name__}.interaction"
INTERACTION_SPLIT_CHARACTER = "-"
USER_INTERACTION_COOLDOWN = int(os.getenv("INTERACTION_COOLDOWN", 60))
ROLE_SUFFIX = os.getenv("ROLE_SUFFIX")


@dataclass()
class PollData:
    role_name: str
    guild_id: int
    channel_id: int
    message_id: int
    user_votes: set
    end_time: datetime


class InteractionType(IntEnum):
    VOTE_ADD = 0
    VOTE_REMOVE = 1
    ROLE_ADD = 2
    ROLE_REMOVE = 3

    @property
    def id(self) -> str:
        base = f"{INTERACTION_PREFIX}{INTERACTION_SPLIT_CHARACTER}"
        match self:
            case InteractionType.VOTE_ADD:
                return f"{base}voteadd"
            case InteractionType.VOTE_REMOVE:
                return f"{base}voteremove"
            case InteractionType.ROLE_ADD:
                return f"{base}roleadd"
            case InteractionType.ROLE_REMOVE:
                return f"{base}roleremove"
            case _:
                raise ValueError(f"Missing ID for given enum - {self:s}")

    def __str__(self):
        return self.id

    @classmethod
    def from_string(self, string: str) -> "InteractionType":
        if not string.startswith(INTERACTION_PREFIX):
            raise ValueError("Invalid enum string ID given")

        enum_id = string.split(INTERACTION_SPLIT_CHARACTER)[1]
        match enum_id:
            case "voteadd":
                return InteractionType.VOTE_ADD
            case "voteremove":
                return InteractionType.VOTE_REMOVE
            case "roleadd":
                return InteractionType.ROLE_ADD
            case "roleremove":
                return InteractionType.ROLE_REMOVE
            case _:
                raise ValueError("Invalid enum string ID given")


def timeout_role_mention(role: Role, duration: float):

    async def timeout():
        await role.edit(mentionable=False)
        await async_sleep(duration)
        await role.edit(mentionable=True)

    create_task(timeout())


def make_vote_embed(poll_data: PollData, vote_threshold: int):
    end_int = int(poll_data.end_time.timestamp())
    end_time = f"<t:{end_int}:R>"

    description = COG_STRINGS["users_vote_menu_description"].format(threshold=vote_threshold)
    description += f"\n\n**Current Votes:   `{len(poll_data.user_votes)}/{vote_threshold}`**"
    description += f"\n\n**Voting Ends   {end_time}**"

    embed = Embed(
        title=COG_STRINGS["users_vote_menu_title"].format(name=poll_data.role_name),
        description=description,
        color=Color.random()
    )

    return embed


def make_vote_ended_embed(poll_data: PollData, vote_threshold: int):
    end_int = int(poll_data.end_time.timestamp())
    end_time = f"<t:{end_int}:R>"
    description = f"**Voting ended {end_time}**"
    description += f"\n\nPoll finished with: `{len(poll_data.user_votes)}/{vote_threshold}` vote(s)"
    embed = Embed(
        title=COG_STRINGS["users_vote_menu_title"].format(name=poll_data.role_name),
        description=description,
        color=Color.random()
    )
    return embed


def make_role_embed(poll_data: PollData):
    embed = Embed(
        title=f"Get the {poll_data.role_name} {ROLE_SUFFIX} Role",
        description="This is a Pingable Role role menu. Use the buttons below to add/remove the role from yourself.",
        color=Color.random()
    )

    return embed


@default_permissions(administrator=True)
@guild_only()
class UserRolesAdmin(GroupCog, name=COG_STRINGS["users_admin_group_name"]):

    def __init__(self, bot: Bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"{__name__}.{__class__.__name__} has been added as a Cog")
        self.guild_configs = {}

    def load_config(self):
        db_items = DBSession.list(UserRolesConfig)
        self.guild_configs = {x.guild_id: x for x in db_items}

    @GroupCog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            if not DBSession.get(UserRolesConfig, guild_id=guild.id):
                DBSession.create(UserRolesConfig(guild_id=guild.id))

        self.load_config()

    @command(name=COG_STRINGS["users_admin_get_config_name"], description=COG_STRINGS["users_admin_get_config_description"])
    @describe(setting=COG_STRINGS["users_admin_get_config_property_describe"])
    @rename(setting=COG_STRINGS["users_admin_get_config_property_rename"])
    @autocomplete(setting=UserRolesConfigTransformer.autocomplete)
    async def get_config(self, interaction: Interaction, setting: str = None):
        guild_config = self.guild_configs.get(interaction.guild.id)

        if not setting:
            config_title = COG_STRINGS["users_admin_get_config_title"]
            config_description = COG_STRINGS["users_admin_get_config_subtext"]
            settings = "\n".join(
                f"• _{' '.join(x.capitalize() for x in x.split('_'))}_ – `{getattr(guild_config, x)}`"
                for x in guild_config.__dict__ if not x.startswith("_") and "guild" not in x.lower()
            )

            message = f"{config_title}\n{config_description}\n\n{settings}"
            await interaction.response.send_message(message, ephemeral=True)
            return

        try:
            value = getattr(guild_config, setting)
            pretty_string = " ".join(x.capitalize() for x in setting.split("_"))
            await interaction.response.send_message(
                COG_STRINGS["users_admin_get_config_single"].format(setting=pretty_string,
                                                                    value=value),
                ephemeral=True,
            )
        except AttributeError:
            await interaction.response.send_message(
                COG_STRINGS["users_admin_get_config_wrong_setting"].format(setting=setting),
                ephemeral=True,
                delete_after=15
            )


@guild_only()
class UserRoles(GroupCog, name=COG_STRINGS["users_group_name"]):

    def __init__(self, bot: Bot, admin_cog_instance: GroupCog):
        self.bot = bot
        self.admin_cog = admin_cog_instance
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"{__name__}.{__class__.__name__} has been added as a Cog")
        self.current_polls = {}
        self.poll_callbacks = []
        self.user_interaction_timeout = {}
        self.tracked_role_ids = {}
        self.load_roles()

    def load_roles(self):
        db_items = DBSession.list(UserRolesRoles)
        for item in db_items:
            if item.guild_id not in self.tracked_role_ids:
                self.tracked_role_ids[item.guild_id] = []
            self.tracked_role_ids[item.guild_id].append(item.role_id)

    @GroupCog.listener()
    async def on_message(self, message: Message):
        if message.author.bot:
            return

        if message.author.guild_permissions.administrator:
            return

        roles = self.tracked_role_ids.get(message.guild.id)
        if not roles:
            return

        guild_config = self.admin_cog.guild_configs.get(message.guild.id)
        for role in message.role_mentions:
            if role.id in roles:
                timeout_role_mention(role, guild_config.mention_cooldown)

    @GroupCog.listener()
    async def on_interaction(self, interaction: Interaction):
        if not check_interaction_prefix(interaction, INTERACTION_PREFIX):
            return

        current_guild_polls = self.current_polls.get(interaction.guild.id, {})
        poll_data: PollData = current_guild_polls.get(interaction.message.id, None)

        interaction_type = InteractionType.from_string(interaction.data.get("custom_id"))
        guild_config = self.admin_cog.guild_configs.get(interaction.guild.id)

        match interaction_type:
            case InteractionType.VOTE_ADD:
                await self.user_add_vote(interaction, poll_data, guild_config)

            case InteractionType.VOTE_REMOVE:
                await self.user_remove_vote(interaction, poll_data, guild_config)

            case InteractionType.ROLE_ADD:
                await self.user_add_role(interaction)

            case InteractionType.ROLE_REMOVE:
                await self.user_remove_role(interaction)

    def timeout_user_interaction(self, user_id: int):
        cooldown_task = create_task(async_sleep(USER_INTERACTION_COOLDOWN))

        def callback(task: Task):
            self.user_interaction_timeout.pop(user_id)

        cooldown_task.add_done_callback(callback)
        self.user_interaction_timeout[user_id] = cooldown_task

    async def user_add_role(self, interaction: Interaction):
        interaction_id = interaction.data.get("custom_id")
        role_id = int(interaction_id.split(INTERACTION_SPLIT_CHARACTER)[-1])
        role = interaction.guild.get_role(role_id)
        if not role:
            await interaction.response.send_message(COG_STRINGS["users_role_invalid"], ephemeral=True)
            return

        await interaction.user.add_roles(role)
        await interaction.response.send_message(COG_STRINGS["users_role_added"].format(role=role.name), ephemeral=True)

    async def user_remove_role(self, interaction: Interaction):
        interaction_id = interaction.data.get("custom_id")
        role_id = int(interaction_id.split(INTERACTION_SPLIT_CHARACTER)[-1])
        role = interaction.guild.get_role(role_id)
        if not role:
            await interaction.response.send_message(COG_STRINGS["users_role_invalid"], ephemeral=True)
            return

        await interaction.user.remove_roles(role)
        await interaction.response.send_message(COG_STRINGS["users_role_removed"].format(role=role.name), ephemeral=True)

    async def check_for_timeout(self, interaction: Interaction):
        if interaction.user.id in self.user_interaction_timeout:
            time = f"{USER_INTERACTION_COOLDOWN}s"
            await interaction.response.send_message(
                COG_STRINGS["users_interaction_timeout"].format(time=time),
                ephemeral=True,
                delete_after=5
            )
            return False
        return True

    async def validate_user_vote(self, interaction: Interaction, poll_data: PollData):
        if poll_data is None:
            await interaction.message.edit(view=None)
            await interaction.response.send_message(
                COG_STRINGS["users_vote_ended"].format(name=poll_data.role_name),
                ephemeral=True,
                delete_after=10
            )
            return False

        # ngl in my mind this logic doesn't make sense, but it works...
        if datetime.now() > poll_data.end_time:
            await interaction.message.edit(view=None)
            await interaction.response.send_message(
                COG_STRINGS["users_vote_ended"].format(name=poll_data.role_name),
                ephemeral=True,
                delete_after=10
            )
            return False

        return True

    async def user_add_vote(self, interaction: Interaction, poll_data: PollData, guild_config: UserRolesConfig):
        if not await self.validate_user_vote(interaction, poll_data):
            return

        if not await self.check_for_timeout(interaction):
            return

        poll_data.user_votes.add(interaction.user.id)
        await self.update_vote_count(poll_data, guild_config)
        if len(poll_data.user_votes) < guild_config.vote_threshold:
            await interaction.response.send_message(
                COG_STRINGS["users_vote_added"].format(name=poll_data.role_name),
                ephemeral=True,
                delete_after=10
            )
        else:
            await self.end_poll(poll_data)

        self.timeout_user_interaction(interaction.user.id)

    async def user_remove_vote(self, interaction: Interaction, poll_data: PollData, guild_config: UserRolesConfig):
        if not await self.validate_user_vote(interaction, poll_data):
            return

        if not await self.check_for_timeout(interaction):
            return

        poll_data.user_votes.discard(interaction.user.id)
        await self.update_vote_count(poll_data, guild_config)
        await interaction.response.send_message(
            COG_STRINGS["users_vote_removed"].format(name=poll_data.role_name),
            ephemeral=True,
            delete_after=10
        )

        self.timeout_user_interaction(interaction)

    async def update_vote_count(self, poll_data: PollData, guild_config: UserRolesConfig):
        embed = make_vote_embed(poll_data, guild_config.vote_threshold)

        guild = self.bot.get_guild(poll_data.guild_id)
        channel = guild.get_channel(poll_data.channel_id)
        message = await channel.fetch_message(poll_data.message_id)
        if not message:
            return

        await message.edit(embed=embed)

    async def end_poll(self, poll_data: PollData):
        if not self.current_polls.get(poll_data.guild_id, {}).get(poll_data.message_id):
            return

        embed = make_role_embed(poll_data)
        guild = self.bot.get_guild(poll_data.guild_id)
        channel = guild.get_channel(poll_data.channel_id)

        view = View(timeout=None)
        role = await guild.create_role(name=f"{poll_data.role_name} {ROLE_SUFFIX}", mentionable=True)
        DBSession.create(UserRolesRoles(guild_id=guild.id, role_id=role.id))
        if not self.tracked_role_ids.get(guild.id):
            self.tracked_role_ids[guild.id] = []
        self.tracked_role_ids[guild.id].append(role.id)

        add_button = Button(emoji="✅", custom_id=f"{InteractionType.ROLE_ADD.id}{INTERACTION_SPLIT_CHARACTER}{role.id}")
        view.add_item(add_button)
        remove_button = Button(emoji="❌", custom_id=f"{InteractionType.ROLE_REMOVE.id}{INTERACTION_SPLIT_CHARACTER}{role.id}")
        view.add_item(remove_button)

        message = await channel.send(embed=embed, view=view)
        await message.pin()

        guild_config = self.admin_cog.guild_configs.get(poll_data.guild_id)
        vote_ended_embed = make_vote_ended_embed(poll_data, guild_config.vote_threshold)
        old_message = await channel.fetch_message(poll_data.message_id)
        await old_message.edit(embed=vote_ended_embed, view=None)
        self.current_polls.get(poll_data.guild_id).pop(poll_data.message_id)

    @command(name=COG_STRINGS["users_start_vote_name"], description=COG_STRINGS["users_start_vote_description"])
    @describe(role_name=COG_STRINGS["users_start_vote_role_name_describe"])
    @rename(role_name=COG_STRINGS["users_start_vote_role_name_rename"])
    async def start_vote(self, interaction: Interaction, role_name: str):
        await interaction.response.defer(ephemeral=True)

        message = await interaction.channel.send("​")
        guild_config = self.admin_cog.guild_configs.get(interaction.guild.id)

        end_datetime = datetime.now() + timedelta(seconds=guild_config.vote_length)

        poll_data = PollData(
            role_name=role_name,
            guild_id=interaction.guild.id,
            channel_id=interaction.channel.id,
            message_id=message.id,
            user_votes=set(),
            end_time=end_datetime
        )

        if not self.current_polls.get(interaction.guild.id):
            self.current_polls[interaction.guild.id] = {}
        self.current_polls[interaction.guild.id][message.id] = poll_data

        view = View(timeout=guild_config.vote_length)

        add_button = Button(emoji="✅", custom_id=InteractionType.VOTE_ADD.id)
        view.add_item(add_button)
        remove_button = Button(emoji="❌", custom_id=InteractionType.VOTE_REMOVE.id)
        view.add_item(remove_button)

        poll_task = create_task(async_sleep(guild_config.vote_length))

        def callback(task: Task):
            self.poll_callbacks.remove(task)
            create_task(self.end_poll(poll_data))

        poll_task.add_done_callback(callback)
        self.poll_callbacks.append(poll_task)

        await message.edit(embed=make_vote_embed(poll_data, guild_config.vote_threshold), view=view)
        await respond_or_followup(COG_STRINGS["react_start_vote_success"].format(name=role_name), interaction, ephemeral=True)


async def setup(bot: Bot):
    admin_cog = UserRolesAdmin(bot)
    await bot.add_cog(admin_cog)
    await bot.add_cog(UserRoles(bot, admin_cog))
