from sqlalchemy import Column, String, BigInteger, Boolean, Float, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base

base = declarative_base()


class Guild_info(base):
    __tablename__ = 'guild_info'
    guild_id = Column(BigInteger, primary_key=True, nullable=False)
    log_channel_id = Column(BigInteger, nullable=True)
    default_role_id = Column(BigInteger, nullable=True)


class Pingable_polls(base):
    __tablename__ = 'pingable_polls'
    guild_id = Column(BigInteger, primary_key=True, nullable=False)
    pingable_name = Column(String, primary_key=True, nullable=False)
    poll_id = Column(BigInteger, nullable=False)
    poll = Column(JSONB, nullable=False)


class Pingable_roles(base):
    __tablename__ = 'pingable_roles'
    guild_id = Column(BigInteger, primary_key=True, nullable=False)
    role_id = Column(BigInteger, primary_key=True, nullable=False)
    menu_id = Column(BigInteger, nullable=False)
    menu = Column(JSONB, nullable=False)
    total_pings = Column(BigInteger, nullable=False)
    monthly_pings = Column(BigInteger, nullable=False)


class Pingable_settings(base):
    __tablename__ = 'pingable_settings'
    guild_id = Column(BigInteger, primary_key=True, nullable=False)
    default_cooldown_length = Column(BigInteger, nullable=False)
    default_poll_length = Column(BigInteger, nullable=False)
    default_poll_threshold = Column(BigInteger, nullable=False)
    default_poll_emoji = Column(JSONB, nullable=False)
    default_role_emoji = Column(JSONB, nullable=False)


class Event_categories(base):
    __tablename__ = 'event_categories'
    guild_id = Column(BigInteger, primary_key=True, nullable=False)
    event_id = Column(BigInteger, primary_key=True, nullable=False)
    event_name = Column(String, nullable=False)
    event_menu = Column(JSONB, nullable=False)


class Role_menus(base):
    __tablename__ = 'role_menus'
    menu_id = Column(BigInteger, primary_key=True, nullable=False)
    menu = Column(JSONB, nullable=False)


class Voting_menus(base):
    __tablename__ = 'voting_menus'
    menu_id = Column(BigInteger, primary_key=True, nullable=False)
    menu = Column(JSONB, nullable=False)


class Voicemaster_master(base):
    __tablename__ = 'voicemaster_master'
    master_id = Column(BigInteger, primary_key=True, autoincrement=True, nullable=False)
    guild_id = Column(BigInteger, nullable=False)
    channel_id = Column(BigInteger, nullable=False)


class Voicemaster_slave(base):
    __tablename__ = 'voicemaster_slave'
    vc_id = Column(BigInteger, primary_key=True, autoincrement=True, nullable=False)
    guild_id = Column(BigInteger, nullable=False)
    channel_id = Column(BigInteger, nullable=False)
    owner_id = Column(BigInteger, nullable=False)
    locked = Column(Boolean, nullable=False)


class Twitch_info(base):
    __tablename__ = 'twitch_info'
    guild_id = Column(BigInteger, nullable=False)
    channel_id = Column(BigInteger, primary_key=True, nullable=False)
    hook_id = Column(BigInteger, primary_key=True, nullable=False)
    twitch_handle = Column(String, nullable=False)
    custom_message = Column(String, nullable=True)


class Twitter_info(base):
    __tablename__ = 'twitter_info'
    id = Column(BigInteger, primary_key=True, autoincrement=True, nullable=False)
    guild_id = Column(BigInteger, nullable=False)
    twitter_user_id = Column(String, nullable=False)
    twitter_handle = Column(String, nullable=False)


class Music_channels(base):
    __tablename__ = 'music_channels'
    id = Column(BigInteger, primary_key=True, autoincrement=True, nullable=False)
    guild_id = Column(BigInteger, nullable=False)
    channel_id = Column(BigInteger, nullable=False)
    queue_message_id = Column(BigInteger, nullable=False)
    preview_message_id = Column(BigInteger, nullable=False)
