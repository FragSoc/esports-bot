from sqlalchemy import Column, String, BigInteger, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base

base = declarative_base()

__all__ = ["base"]
