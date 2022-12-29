import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from zoneinfo import ZoneInfo

from discord import (
    EntityType,
    EventStatus,
    Interaction,
    PermissionOverwrite,
    PrivacyLevel,
    Role,
    ScheduledEvent,
    SelectOption
)
from discord.app_commands import (
    Choice,
    Transform,
    checks,
    choices,
    command,
    default_permissions,
    describe,
    guild_only,
    rename
)
from discord.ext.commands import Bot, Cog
from discord.ui import Select, View

from client import EsportsBot
from common.discord import DatetimeTransformer
from common.io import load_cog_toml, load_timezones

COG_STRINGS = load_cog_toml(__name__)
EVENT_INTERACTION_PREFIX = f"{__name__}.interaction"
TIMEZONES = load_timezones()

SIGN_IN_CHANNEL_SUFFIX = "sign-in"

denied_perms = PermissionOverwrite(read_messages=False, send_messages=False, connect=False, view_channel=False)
read_only_perms = PermissionOverwrite(read_messages=True, send_messages=False, connect=False, view_channel=True)
writable_perms = PermissionOverwrite(read_messages=True, send_messages=True, connect=True, view_channel=True)


class RoleTypeEnum(IntEnum):
    DEFAULT = 0  # Guild default role
    COMMON = 1  # Common role amongst members
    EVENT = 2  # Event specific role
    BOTTOP = 3  # The Bot's top role


@dataclass(slots=True, unsafe_hash=True)
class Event:
    name: str
    start_time: datetime
    end_time: datetime
    guild_id: int = field(compare=True)
    channel_id: int = field(compare=True)
    event_id: int = field(hash=True)
    role_id: int = None


def get_event_custom_id(guild_id: int, channel_id: int, suffix: str):
    return f"{EVENT_INTERACTION_PREFIX}-{guild_id}-{channel_id}-{suffix}"


def get_category_permissions(role_type: RoleTypeEnum, is_signin: bool = False, is_open: bool = False):
    # pass
    match role_type:
        case RoleTypeEnum.DEFAULT:
            return denied_perms
        case RoleTypeEnum.COMMON:
            if not is_open:
                return denied_perms
            elif is_signin:
                return read_only_perms
            else:
                return denied_perms
        case RoleTypeEnum.EVENT:
            if not is_open:
                return denied_perms
            elif is_signin:
                return read_only_perms
            else:
                return writable_perms
        case RoleTypeEnum.BOTTOP:
            return writable_perms
        case _:
            return denied_perms


class EventTools(Cog):

    def __init__(self, bot: EsportsBot):
        self.bot = bot
        self.events = {}
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"{__name__} has been added as a Cog")

    @Cog.listener()
    async def on_scheduled_event_update(self, before: ScheduledEvent, after: ScheduledEvent):
        if not self.events.get(before.id) or not self.events.get(after.id):
            return False

        if after.status == EventStatus.scheduled:
            pass

        if after.status == EventStatus.active:
            pass

        if after.status == EventStatus.cancelled:
            pass

    @Cog.listener()
    async def on_interaction(self, interaction: Interaction):
        if not interaction.data or not interaction.data.get("custom_id"):
            return False

        if interaction.data.get("custom_id").startswith(EVENT_INTERACTION_PREFIX):
            await interaction.response.send_message(interaction.data.get("custom_id"), ephemeral=True)

    @command(name=COG_STRINGS["events_create_event_name"], description=COG_STRINGS["events_create_event_description"])
    @describe(
        event_name=COG_STRINGS["events_create_event_title_describe"],
        event_location=COG_STRINGS["events_create_event_location_describe"],
        event_start=COG_STRINGS["events_create_event_start_desribe"],
        event_end=COG_STRINGS["events_create_event_end_describe"],
        timezone=COG_STRINGS["events_create_event_timezone_describe"],
        role=COG_STRINGS["events_create_event_role_describe"]
    )
    @rename(
        event_name=COG_STRINGS["events_create_event_title_rename"],
        event_location=COG_STRINGS["events_create_event_location_rename"],
        event_start=COG_STRINGS["events_create_event_start_rename"],
        event_end=COG_STRINGS["events_create_event_end_rename"],
        timezone=COG_STRINGS["events_create_event_timezone_rename"],
        role=COG_STRINGS["events_create_event_role_rename"]
    )
    @choices(
        timezone=[Choice(name=TIMEZONES.get(x).get("_description"),
                         value=TIMEZONES.get(x).get("_alias")) for x in TIMEZONES]
    )
    @default_permissions(administrator=True)
    @checks.has_permissions(administrator=True)
    @guild_only()
    async def create_event(
        self,
        interaction: Interaction,
        event_name: str,
        event_location: str,
        event_start: Transform[datetime,
                               DatetimeTransformer],
        event_end: Transform[datetime,
                             DatetimeTransformer],
        timezone: Choice[str],
        role: Role
    ):
        await interaction.response.defer()

        event_start_aware = event_start.replace(tzinfo=ZoneInfo(timezone.value))
        event_end_aware = event_end.replace(tzinfo=ZoneInfo(timezone.value))

        event_role = await interaction.guild.create_role(name=f"{event_name} (Event)")

        category_permissions = {
            interaction.guild.me: get_category_permissions(RoleTypeEnum.BOTTOP),
            event_role: get_category_permissions(RoleTypeEnum.EVENT),
            role: get_category_permissions(RoleTypeEnum.COMMON),
            interaction.guild.default_role: get_category_permissions(RoleTypeEnum.DEFAULT)
        }

        signin_permissions = {
            interaction.guild.me: get_category_permissions(RoleTypeEnum.BOTTOP,
                                                           is_signin=True),
            event_role: get_category_permissions(RoleTypeEnum.EVENT,
                                                 is_signin=True),
            role: get_category_permissions(RoleTypeEnum.COMMON,
                                           is_signin=True),
            interaction.guild.default_role: get_category_permissions(RoleTypeEnum.DEFAULT,
                                                                     is_signin=True)
        }

        category = await interaction.guild.create_category(name=event_name, overwrites=category_permissions)
        signin_channel = await interaction.guild.create_text_channel(
            name=f"{event_name} {SIGN_IN_CHANNEL_SUFFIX}",
            category=category,
            overwrites=signin_permissions
        )

        event = await interaction.guild.create_scheduled_event(
            name=event_name,
            start_time=event_start_aware.astimezone(),
            end_time=event_end_aware.astimezone(),
            description=f"Once the event has started, use {signin_channel.mention} to sign in!",
            location=f"Channel: {signin_channel.mention} | Building: {event_location}",
            entity_type=EntityType.external,
            privacy_level=PrivacyLevel.guild_only
        )

        signin_menu = View(timeout=None)

        options = [
            {
                "label": "Not Signed In",
                "description": f"Select this option to sign out of {event_name}",
                "value": 0,
                "emoji": "❎",
                "default": True
            },
            {
                "label": "Signed In",
                "description": f"Select this option to sign in to {event_name}",
                "value": 1,
                "emoji": "✅",
                "default": False
            }
        ]

        sign_in_status = Select(
            placeholder="Your Sign-in Status",
            min_values=1,
            max_values=1,
            options=[SelectOption(**x) for x in options],
            custom_id=get_event_custom_id(interaction.guild.id,
                                          signin_channel.id,
                                          "sign_in_status")
        )

        signin_menu.add_item(sign_in_status)

        await signin_channel.send(content=f"Use the menu below to sign in or out of {event_name}!", view=signin_menu)

        event_store = Event(
            name=event_name,
            start_time=event_start_aware,
            end_time=event_end_aware,
            guild_id=interaction.guild.id,
            channel_id=signin_channel.id,
            role_id=event_role.id,
            event_id=event.id
        )

        self.events[event_store] = event_store

        await interaction.followup.send("Created event!", ephemeral=True)


async def setup(bot: Bot):
    await bot.add_cog(EventTools(bot))
