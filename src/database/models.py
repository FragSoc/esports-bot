from sqlalchemy import Column, String, BigInteger, Boolean
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
    is_locked = Column(Boolean, nullable=False)
    is_limited = Column(Boolean, nullable=False)
    has_custom_name = Column(Boolean, nullable=False)
