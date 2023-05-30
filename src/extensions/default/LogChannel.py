import asyncio
import logging
import os
import re
from typing import Any, Coroutine

from discord import Interaction, TextChannel
from discord.app_commands import command, default_permissions, describe, rename
from discord.ext.commands import Bot, GroupCog

from common.discord import respond_or_followup
from common.io import load_cog_toml
from database.gateway import DBSession
from database.models import LogChannelChannels

COG_STRINGS = load_cog_toml(__name__)
DISCORD_MESSAGE_LIMIT = 2000


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
        if not record.message.startswith(self.prefix):
            return

        contents_no_prefix = record.message[record.message.index(self.prefix) + len(self.prefix):]
        matches = re.search(r"^\[(?P<guild>[0-9]+)\]", contents_no_prefix)
        if not matches:
            return

        guild_id = matches.groupdict().get("guild")
        if not guild_id or not guild_id.isdigit():
            return

        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return

        log_channel_entry = DBSession.get(LogChannelChannels, guild_id=guild.id)
        if not log_channel_entry:
            return

        channel = guild.get_channel(log_channel_entry.channel_id)
        message = await channel.fetch_message(log_channel_entry.current_message_id)

        log_message = f"[<t:{int(record.created)}:f>] " + contents_no_prefix.replace(f"[{guild_id}]", "").strip()

        if len(message.content) + len(log_message) > DISCORD_MESSAGE_LIMIT - 5:
            message = await channel.send(content=log_message)
            log_channel_entry.current_message_id = message.id
            DBSession.update(log_channel_entry)
        else:
            await message.edit(content=f"{message.content}\n{log_message}")

    @command(name=COG_STRINGS["log_set_channel_name"], description=COG_STRINGS["log_set_channel_description"])
    @describe(channel=COG_STRINGS["log_set_channel_channel_describe"])
    @rename(channel=COG_STRINGS["log_set_channel_channel_rename"])
    async def set_log_channel(self, interaction: Interaction, channel: TextChannel):
        message = await channel.send("# Logging start")
        current_channel = DBSession.get(LogChannelChannels, guild_id=interaction.guild.id)
        if not current_channel:
            db_item = LogChannelChannels(guild_id=interaction.guild.id, channel_id=channel.id, current_message_id=message.id)
            DBSession.create(db_item)
        else:
            current_channel.channel_id = channel.id
            current_channel.current_message_id = message.id
            DBSession.update(current_channel)

        await respond_or_followup(
            COG_STRINGS["log_set_channel_success"].format(channel=channel.mention),
            interaction=interaction
        )

    @command(name=COG_STRINGS["log_remove_channel_name"], description=COG_STRINGS["log_remove_channel_description"])
    async def remove_log_channel(self, interaction: Interaction):
        guild_id = interaction.guild.id

        db_item = DBSession.get(LogChannelChannels, guild_id=guild_id)
        if not db_item:
            await respond_or_followup(
                COG_STRINGS["log_remove_channel_success"].format(channel="any channel"),
                interaction=interaction
            )
            return

        channel_id = db_item.channel_id
        DBSession.delete(db_item)

        channel = interaction.guild.get_channel(channel_id)
        if not channel:
            await respond_or_followup(
                COG_STRINGS["log_remove_channel_success"].format(channel="any channel"),
                interaction=interaction
            )
            return

        await respond_or_followup(
            COG_STRINGS["log_remove_channel_success"].format(channel=channel.mention),
            interaction=interaction
        )


async def setup(bot: Bot):
    await bot.add_cog(LogChannel(bot))