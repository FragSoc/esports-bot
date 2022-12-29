import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from zoneinfo import ZoneInfo

from discord import (
    Colour,
    Embed,
    EntityType,
    EventStatus,
    Guild,
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
    autocomplete,
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
from common.discord import (ColourTransformer, DatetimeTransformer, primary_key_from_object)
from common.io import load_cog_toml, load_timezones
from database.gateway import DBSession
from database.models import EventToolsEvents

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


@dataclass(slots=True)
class Event:
    name: str
    guild_id: int = field(compare=True)
    channel_id: int = field(compare=True)
    event_id: int
    event_role_id: int = None
    common_role_id: int = None

    def __hash__(self) -> int:
        return self.event_id


def get_event_custom_id(event_id: int, suffix: str):
    return f"{EVENT_INTERACTION_PREFIX}-{event_id}-{suffix}"


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


def get_event_permissions(guild: Guild, event_role: Role, common_role: Role, is_open: bool):
    category_permissions = {
        guild.me: get_category_permissions(RoleTypeEnum.BOTTOP,
                                           is_open=is_open),
        event_role: get_category_permissions(RoleTypeEnum.EVENT,
                                             is_open=is_open),
        common_role: get_category_permissions(RoleTypeEnum.COMMON,
                                              is_open=is_open),
        guild.default_role: get_category_permissions(RoleTypeEnum.DEFAULT,
                                                     is_open=is_open)
    }

    signin_permissions = {
        guild.me: get_category_permissions(RoleTypeEnum.BOTTOP,
                                           is_signin=True,
                                           is_open=is_open),
        event_role: get_category_permissions(RoleTypeEnum.EVENT,
                                             is_signin=True,
                                             is_open=is_open),
        common_role: get_category_permissions(RoleTypeEnum.COMMON,
                                              is_signin=True,
                                              is_open=is_open),
        guild.default_role: get_category_permissions(RoleTypeEnum.DEFAULT,
                                                     is_signin=True,
                                                     is_open=is_open)
    }

    return (category_permissions, signin_permissions)


class EventTools(Cog):

    def __init__(self, bot: EsportsBot):
        self.bot = bot
        self.events = self.load_events()
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Loaded {len(self.events)} event(s) from DB")
        self.logger.info(f"{__name__} has been added as a Cog")

    def load_events(self):
        db_entries = DBSession.list(EventToolsEvents)
        all_events = {}
        for entry in db_entries:
            event = Event(
                name=entry.event_name,
                guild_id=entry.guild_id,
                channel_id=entry.channel_id,
                event_id=entry.event_id,
                event_role_id=entry.event_role_id,
                common_role_id=entry.common_role_id
            )
            if all_events.get(event):
                self.logger.warning(
                    f"Duplicate event found - {entry.event_name} "
                    f"(guildid - {entry.guild_id} | eventid - {entry.event_id}). Skipping adding this event..."
                )
                continue
            all_events[entry.event_id] = event
        return all_events

    async def update_event_channel_permissions(self, event_id: int, guild: Guild, is_open: bool):
        event = self.events.get(event_id)
        event_role = guild.get_role(event.event_role_id)
        common_role = guild.get_role(event.common_role_id)
        category_permissions, signin_permissions = get_event_permissions(guild, event_role, common_role, is_open)
        signin_channel = guild.get_channel(event.channel_id)
        category = signin_channel.category
        await category.edit(overwrites=category_permissions)
        await signin_channel.edit(overwrites=signin_permissions)

    @Cog.listener()
    async def on_scheduled_event_update(self, before: ScheduledEvent, after: ScheduledEvent):
        # Not an EventTool event
        if not self.events.get(before.id) or not self.events.get(after.id):
            return False

        # Open the sign-in channel when the event starts
        if before.status == EventStatus.scheduled and after.status == EventStatus.active:
            await self.update_event_channel_permissions(after.id, after.guild, is_open=True)

        # Delete the channels and role upon cancellation
        if after.status == EventStatus.cancelled:
            event = self.events.pop(after.id)
            event_role = after.guild.get_role(event.event_role_id)
            signin_channel = after.guild.get_channel(event.channel_id)
            category = signin_channel.category
            for channel in category.channels:
                await channel.delete()
            await category.delete()
            await event_role.delete()
            db_entry = DBSession.get(EventToolsEvents, guild_id=event.guild_id, event_id=event.event_id)
            DBSession.delete(db_entry)

        # Hide the channels again when the event ends
        if after.status == EventStatus.ended:
            await self.update_event_channel_permissions(after.id, after.guild, is_open=False)

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
        common_role=COG_STRINGS["events_create_event_role_describe"],
        event_colour=COG_STRINGS["events_create_event_colour_describe"]
    )
    @rename(
        event_name=COG_STRINGS["events_create_event_title_rename"],
        event_location=COG_STRINGS["events_create_event_location_rename"],
        event_start=COG_STRINGS["events_create_event_start_rename"],
        event_end=COG_STRINGS["events_create_event_end_rename"],
        timezone=COG_STRINGS["events_create_event_timezone_rename"],
        common_role=COG_STRINGS["events_create_event_role_rename"],
        event_colour=COG_STRINGS["events_create_event_colour_rename"]
    )
    @choices(
        timezone=[Choice(name=TIMEZONES.get(x).get("_description"),
                         value=TIMEZONES.get(x).get("_alias")) for x in TIMEZONES]
    )
    @autocomplete(event_colour=ColourTransformer.autocomplete)
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
        common_role: Role,
        event_colour: Transform[Colour,
                                ColourTransformer]
    ):
        await interaction.response.defer()
        event_start_aware = event_start.replace(tzinfo=ZoneInfo(timezone.value))
        event_end_aware = event_end.replace(tzinfo=ZoneInfo(timezone.value))

        event_role = await interaction.guild.create_role(name=f"{event_name} (Event)", color=event_colour)

        category_permissions, signin_permissions = get_event_permissions(interaction.guild, event_role, common_role, False)

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
                "label": COG_STRINGS["events_create_event_sign_out"],
                "description": f"Select this option to sign out of {event_name}",
                "value": 0,
                "emoji": "❎",
                "default": True
            },
            {
                "label": COG_STRINGS["events_create_event_sign_in"],
                "description": f"Select this option to sign into {event_name}",
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
            custom_id=get_event_custom_id(event.id,
                                          "sign_in_status")
        )

        signin_menu.add_item(sign_in_status)

        signin_embed = Embed(
            title=COG_STRINGS["events_create_event_embed_title"].format(name=event_name),
            description=COG_STRINGS["events_create_event_embed_description"].format(
                name=event_name,
                location=event_location,
                role=event_role.mention,
                start=int(event.start_time.timestamp()),
                end=int(event.end_time.timestamp()),
                sign_in=COG_STRINGS["events_create_event_sign_in"],
                sign_out=COG_STRINGS["events_create_event_sign_out"]
            ),
            color=event_colour,
            url=event.url
        )

        await signin_channel.send(embed=signin_embed, view=signin_menu)

        event_store = Event(
            name=event_name,
            guild_id=interaction.guild.id,
            channel_id=signin_channel.id,
            event_role_id=event_role.id,
            common_role_id=common_role.id,
            event_id=event.id
        )

        db_entry = EventToolsEvents(
            primary_key=primary_key_from_object(event),
            guild_id=interaction.guild.id,
            channel_id=signin_channel.id,
            event_role_id=event_role.id,
            common_role_id=common_role.id,
            event_id=event.id,
            event_name=event_name
        )
        DBSession.create(db_entry)
        self.events[event.id] = event_store

        await interaction.followup.send("Created event!", ephemeral=True)


async def setup(bot: Bot):
    await bot.add_cog(EventTools(bot))
