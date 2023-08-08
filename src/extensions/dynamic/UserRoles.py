import logging
from asyncio import create_task
from asyncio import sleep as async_sleep
from datetime import datetime

from discord import Color, Embed, Interaction, Role
from discord.app_commands import default_permissions, guild_only
from discord.ext.commands import Bot, GroupCog

from common.io import load_cog_toml
from database.gateway import DBSession
from database.models import UserRolesConfig

COG_STRINGS = load_cog_toml(__name__)


def timeout_role_mention(role: Role, duration: float):

    async def timeout():
        await role.edit(mentionable=False)
        await async_sleep(duration)
        await role.edit(mentionable=True)

    create_task(timeout())


def make_vote_embed(role_name: str, vote_duration: float, vote_threshold: int):
    end = datetime.now().timestamp() + vote_duration
    end_int = int(end)
    end_time = f"<t:{end_int}:R>"

    embed = Embed(
        title=COG_STRINGS["users_vote_menu_title"].format(name=role_name),
        description=COG_STRINGS["users_vote_menu_description"].format(threshold=vote_threshold,
                                                                      timestamp=end_time),
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
