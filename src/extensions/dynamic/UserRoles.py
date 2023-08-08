import logging
from asyncio import create_task
from asyncio import sleep as async_sleep
from dataclasses import dataclass
from enum import IntEnum

from discord import Color, Embed, Interaction, Role
from discord.app_commands import default_permissions, guild_only
from discord.ext.commands import Bot, GroupCog

from common.io import load_cog_toml
from database.gateway import DBSession
from database.models import UserRolesConfig

COG_STRINGS = load_cog_toml(__name__)
INTERACTION_PREFIX = f"{__name__}.interaction"
INTERACTION_SPLIT_CHARACTER = "-"


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

        enum_id = string.split(INTERACTION_SPLIT_CHARACTER)[-1]
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


def make_role_embed(poll_data: PollData):
    embed = Embed(
        title=f"Get the {poll_data.role_name} (Pingable) Role",
        description="This is a Pingable Role role menu.",
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


@guild_only()
class UserRoles(GroupCog, name=COG_STRINGS["users_group_name"]):

    def __init__(self, bot: Bot, admin_cog_instance: GroupCog):
        self.bot = bot
        self.admin_cog = admin_cog_instance
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"{__name__}.{__class__.__name__} has been added as a Cog")


async def setup(bot: Bot):
    admin_cog = UserRolesAdmin(bot)
    await bot.add_cog(admin_cog)
    await bot.add_cog(UserRoles(bot, admin_cog))
