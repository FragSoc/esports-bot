from sqlalchemy import Column, String, Integer, Boolean, Float, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base

base = declarative_base()


class Guild_info(base):
    __tablename__ = 'guild_info'
    guild_id = Column(Integer, primary_key=True, nullable=False)
    log_channel_id = Column(Integer, nullable=True)
    default_role_id = Column(Integer, nullable=True)
    num_running_polls = Column(Integer, nullable=False)
    role_ping_cooldown_seconds = Column(Integer, nullable=False)
    pingme_create_threshold = Column(Integer, nullable=False)
    pingme_create_poll_length_seconds = Column(Integer, nullable=False)
    pingme_role_emoji = Column(String, nullable=True)
    shared_role_id = Column(Integer, nullable=True)


class Pingable_roles(base):
    __tablename__ = 'pingable_roles'
    name = Column(String, nullable=False)
    guild_id = Column(Integer, ForeignKey("guild_info.guild_id"), nullable=False)
    role_id = Column(Integer, primary_key=True, nullable=False)
    on_cooldown = Column(Boolean, nullable=False)
    last_ping = Column(Float, nullable=False)
    ping_count = Column(Integer, nullable=False)
    monthly_ping = Column(Integer, nullable=False)
    creator_id = Column(Integer, nullable=False)
    colour = Column(Integer, nullable=False)


class Event_categories(base):
    __tablename__ = 'event_categories'
    guild_id = Column(Integer, ForeignKey("guild_info.guild_id"), primary_key=True, nullable=False)
    event_name = Column(String, primary_key=True, nullable=False)
    role_id = Column(Integer, nullable=False)
    signin_menu = Column(Integer, nullable=False)


class Reaction_menus(base):
    __tablename__ = 'reaction_menus'
    message_id = Column(Integer, primary_key=True, nullable=False)
    menu = Column(JSONB, nullable=False)


class Voicemaster_master(base):
    __tablename__ = 'voicemaster_master'
    master_id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    guild_id = Column(Integer, nullable=False)
    channel_id = Column(Integer, nullable=False)


class Voicemaster_slave(base):
    __tablename__ = 'voicemaster_slave'
    vc_id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    guild_id = Column(Integer, nullable=False)
    channel_id = Column(Integer, nullable=False)
    owner_id = Column(Integer, nullable=False)
    locked = Column(Boolean, nullable=False)


class Twitch_info(base):
    __tablename__ = 'twitch_info'
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    guild_id = Column(Integer, nullable=False)
    channel_id = Column(Integer, nullable=False)
    twitch_handle = Column(String, nullable=False)
    currently_live = Column(Boolean, nullable=False)
    custom_message = Column(String, nullable=False)
    # Will most likely change after Benji switch


class Twitter_info(base):
    __tablename__ = 'twitter_info'
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    guild_id = Column(Integer, nullable=False)
    twitter_user_id = Column(String, nullable=False)
    twitter_handle = Column(String, nullable=False)


class Music_channels(base):
    __tablename__ = 'music_channels'
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    guild_id = Column(Integer, nullable=False)
    channel_id = Column(Integer, nullable=False)
    queue_message_id = Column(Integer, nullable=False)
    preview_message_id = Column(Integer, nullable=False)
