from sqlalchemy import Column, String, BigInteger, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base

base = declarative_base()

__all__ = [
    "GuildInfo",
    "DefaultRoles",
    "PingablePolls",
    "PingableRoles",
    "PingableSettings",
    "EventCategories",
    "RoleMenus",
    "VotingMenus",
    "VoicemasterMaster",
    "VoicemasterSlave",
    "TwitchInfo",
    "TwitterInfo",
    "MusicChannels",
    "base"
]


class GuildInfo(base):
    __tablename__ = 'guild_info'
    guild_id = Column(BigInteger, primary_key=True, nullable=False)
    log_channel_id = Column(BigInteger, nullable=True)


class DefaultRoles(base):
    __tablename__ = 'default_roles'
    default_roles_id = Column(BigInteger, primary_key=True, autoincrement=True, nullable=False)
    guild_id = Column(BigInteger, nullable=False)
    role_id = Column(BigInteger, nullable=False)


class PingablePolls(base):
    __tablename__ = 'pingable_polls'
    guild_id = Column(BigInteger, primary_key=True, nullable=False)
    pingable_name = Column(String, primary_key=True, nullable=False)
    poll_id = Column(BigInteger, nullable=False)
    poll = Column(JSONB, nullable=False)


class PingableRoles(base):
    __tablename__ = 'pingable_roles'
    guild_id = Column(BigInteger, primary_key=True, nullable=False)
    role_id = Column(BigInteger, primary_key=True, nullable=False)
    menu_id = Column(BigInteger, nullable=False)
    menu = Column(JSONB, nullable=False)
    total_pings = Column(BigInteger, nullable=False)
    monthly_pings = Column(BigInteger, nullable=False)


class PingableSettings(base):
    __tablename__ = 'pingable_settings'
    guild_id = Column(BigInteger, primary_key=True, nullable=False)
    default_cooldown_length = Column(BigInteger, nullable=False)
    default_poll_length = Column(BigInteger, nullable=False)
    default_poll_threshold = Column(BigInteger, nullable=False)
    default_poll_emoji = Column(JSONB, nullable=False)
    default_role_emoji = Column(JSONB, nullable=False)


class EventCategories(base):
    __tablename__ = 'event_categories'
    guild_id = Column(BigInteger, primary_key=True, nullable=False)
    event_id = Column(BigInteger, primary_key=True, nullable=False)
    event_name = Column(String, nullable=False)
    event_menu = Column(JSONB, nullable=False)


class RoleMenus(base):
    __tablename__ = 'role_menus'
    menu_id = Column(BigInteger, primary_key=True, nullable=False)
    menu = Column(JSONB, nullable=False)


class VotingMenus(base):
    __tablename__ = 'voting_menus'
    menu_id = Column(BigInteger, primary_key=True, nullable=False)
    menu = Column(JSONB, nullable=False)


class VoicemasterMaster(base):
    __tablename__ = 'voicemaster_master'
    master_id = Column(BigInteger, primary_key=True, autoincrement=True, nullable=False)
    guild_id = Column(BigInteger, nullable=False)
    channel_id = Column(BigInteger, nullable=False)


class VoicemasterSlave(base):
    __tablename__ = 'voicemaster_slave'
    vc_id = Column(BigInteger, primary_key=True, autoincrement=True, nullable=False)
    guild_id = Column(BigInteger, nullable=False)
    channel_id = Column(BigInteger, nullable=False)
    owner_id = Column(BigInteger, nullable=False)
    locked = Column(Boolean, nullable=False)
    custom_name = Column(Boolean, nullable=False)


class TwitchInfo(base):
    __tablename__ = 'twitch_info'
    guild_id = Column(BigInteger, nullable=False)
    channel_id = Column(BigInteger, primary_key=True, nullable=False)
    hook_id = Column(BigInteger, primary_key=True, nullable=False)
    twitch_handle = Column(String, nullable=False)
    custom_message = Column(String, nullable=True)


class TwitterInfo(base):
    __tablename__ = 'twitter_info'
    id = Column(BigInteger, primary_key=True, autoincrement=True, nullable=False)
    guild_id = Column(BigInteger, nullable=False)
    twitter_user_id = Column(String, nullable=False)
    twitter_handle = Column(String, nullable=False)


class MusicChannels(base):
    __tablename__ = 'music_channels'
    id = Column(BigInteger, primary_key=True, autoincrement=True, nullable=False)
    guild_id = Column(BigInteger, nullable=False)
    channel_id = Column(BigInteger, nullable=False)
    queue_message_id = Column(BigInteger, nullable=False)
    preview_message_id = Column(BigInteger, nullable=False)
