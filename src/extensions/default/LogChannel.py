import asyncio
import logging
import os
import re
from typing import Any, Coroutine

from discord.app_commands import command, default_permissions
from discord.ext.commands import Bot, GroupCog

from common.io import load_cog_toml

COG_STRINGS = load_cog_toml(__name__)


class LogStreamCapture(logging.StreamHandler):

    def __init__(self, emit_handler: Coroutine, **kwargs: Any):
        super().__init__(**kwargs)
        self.emit_handler = emit_handler

    def emit(self, record):
        try:
            asyncio.create_task(self.emit_handler(record))
            message = self.format(record)
            self.stream.write(message)
        except:
            self.handleError(record)


@default_permissions(administrator=True)
class LogChannel(GroupCog, name=COG_STRINGS["log_group_name"]):

    def __init__(self, bot: Bot):
        self.bot = bot
        self.root_logger = logging.getLogger()
        self.custom_handler = LogStreamCapture(self.log_handler)
        self.root_logger.addHandler(self.custom_handler)
        self.prefix = os.getenv("LOGGING_PREFIX")

    async def log_handler(self, record: logging.LogRecord):
        message_contents = record.message
        if not message_contents.startswith(self.prefix):
            return

        contents_no_prefix = record.message[record.message.index(self.prefix) + len(self.prefix):]
        matches = re.search(r"^\[(?P<guild>[0-9]+)\]", contents_no_prefix)
        if not matches:
            return

        guild_id = matches.groupdict().get("guild")
        if not guild_id or not guild_id.isdigit():
            return


async def setup(bot: Bot):
    await bot.add_cog(LogChannel(bot))