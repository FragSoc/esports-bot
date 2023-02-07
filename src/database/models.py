from sqlalchemy import BigInteger, Boolean, Column, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base

base = declarative_base()

__all__ = ["base", "VoiceAdminParent", "VoiceAdminChild"]


class VoiceAdminParent(base):
    __tablename__ = "voiceadmin_parents"
    primary_key = Column(BigInteger, primary_key=True, autoincrement=True, nullable=False)
    guild_id = Column(BigInteger, nullable=False)
    channel_id = Column(BigInteger, nullable=False)


class VoiceAdminChild(base):
    __tablename__ = "voiceadmin_children"
    primary_key = Column(BigInteger, primary_key=True, autoincrement=True, nullable=False)
    guild_id = Column(BigInteger, nullable=False)
    channel_id = Column(BigInteger, nullable=False)
    owner_id = Column(BigInteger, nullable=False)
    is_locked = Column(Boolean, nullable=False)
    is_limited = Column(Boolean, nullable=False)
    has_custom_name = Column(Boolean, nullable=False)


class AutoRolesConfig(base):
    __tablename__ = "autoroles_config"
    primary_key = Column(BigInteger, primary_key=True, autoincrement=True, nullable=False)
    guild_id = Column(BigInteger, nullable=False)
    role_id = Column(BigInteger, nullable=False)


class EventToolsEvents(base):
    __tablename__ = "eventtools_events"
    primary_key = Column(BigInteger, primary_key=True, autoincrement=True, nullable=False)
    guild_id = Column(BigInteger, nullable=False)
    channel_id = Column(BigInteger, nullable=False)
    event_role_id = Column(BigInteger, nullable=False)
    common_role_id = Column(BigInteger, nullable=False)
    event_id = Column(BigInteger, nullable=False)
    event_name = Column(String, nullable=False)
    is_archived = Column(Boolean, nullable=True, default=False)
