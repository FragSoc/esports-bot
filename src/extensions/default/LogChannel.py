import asyncio
import logging
import re
from typing import Any, Coroutine

from discord import Interaction, TextChannel, Embed, Color, NotFound
from discord.app_commands import command, default_permissions, describe, rename
from discord.ext.commands import Bot, GroupCog

from common.discord import respond_or_followup
from common.io import load_cog_toml
from database.gateway import DBSession
from database.models import LogChannelChannels

COG_STRINGS = load_cog_toml(__name__)


class LogStreamCapture(logging.StreamHandler):

    def __init__(self, emit_handler: Coroutine, **kwargs: Any):
        super().__init__(**kwargs)
        self.emit_handler = emit_handler

    def emit(self, record):
        try:
            asyncio.create_task(self.emit_handler(record))
        except:
            self.handleError(record)


@default_permissions(administrator=True)
class LogChannel(GroupCog, name=COG_STRINGS["log_group_name"]):

    def __init__(self, bot: Bot):
        self.bot = bot
        self.root_logger = logging.getLogger()
        self.custom_handler = LogStreamCapture(self.log_handler)
        self.root_logger.addHandler(self.custom_handler)
        self.logger = logging.getLogger(__name__)

    async def log_handler(self, record: logging.LogRecord):
        if not hasattr(record, "message"):
            return

        if not record.message.startswith(self.bot.logging_prefix):
            return

        contents_no_prefix = record.message[record.message.index(self.bot.logging_prefix) + len(self.bot.logging_prefix):]
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

        log_level = ""
        match record.levelno:
            case logging.DEBUG:
                log_level = "🐞"
            case logging.INFO:
                log_level = "✅"
            case logging.WARNING:
                log_level = "⚠️"
            case logging.WARN:
                log_level = "⚠️"
            case logging.ERROR:
                log_level = "❗️"
            case logging.CRITICAL:
                log_level = "❌"

        log_info = f"[{log_level}][<t:{int(record.created)}:f>] "
        log_message = contents_no_prefix.replace(f"[{guild_id}]", "").strip()

        channel = guild.get_channel(log_channel_entry.channel_id)
        try:
            message = await channel.fetch_message(log_channel_entry.current_message_id)
            message_embed = message.embeds[-1]

            if len(message_embed.fields) < 25:
                message_embed.add_field(name=log_info, value=log_message, inline=False)
                embeds = message.embeds
                embeds[-1] = message_embed
                await message.edit(embeds=embeds)
            elif len(message.embeds < 10):
                embed = Embed(title="​", description="", colour=Color.random())
                embed.add_field(name=log_info, value=log_message, inline=False)
                embeds = message.embeds
                embeds.append(embed)
                await message.edit(embeds=embeds)
            else:
                embed = Embed(title="​", description="", colour=Color.random())
                embed.add_field(name=log_info, value=log_message, inline=False)
                message = await channel.send(embed=embed)
                log_channel_entry.current_message_id = message.id
                DBSession.update(log_channel_entry)
        except NotFound:
            embed = Embed(title="​", description="", colour=Color.random())
            embed.add_field(name=log_info, value=log_message, inline=False)
            message = await channel.send(embed=embed)
            log_channel_entry.current_message_id = message.id
            DBSession.update(log_channel_entry)
            return

    @command(name=COG_STRINGS["log_set_channel_name"], description=COG_STRINGS["log_set_channel_description"])
    @describe(channel=COG_STRINGS["log_set_channel_channel_describe"])
    @rename(channel=COG_STRINGS["log_set_channel_channel_rename"])
    async def set_log_channel(self, interaction: Interaction, channel: TextChannel):
        await channel.send("# Logging Start")
        current_channel = DBSession.get(LogChannelChannels, guild_id=interaction.guild.id)
        if not current_channel:
            db_item = LogChannelChannels(guild_id=interaction.guild.id, channel_id=channel.id, current_message_id=0)
            DBSession.create(db_item)
        else:
            current_channel.channel_id = channel.id
            current_channel.current_message_id = 0
            DBSession.update(current_channel)

        await respond_or_followup(
            COG_STRINGS["log_set_channel_success"].format(channel=channel.mention),
            interaction=interaction
        )

    @command(name=COG_STRINGS["log_get_channel_name"], description=COG_STRINGS["log_get_channel_description"])
    async def get_log_channel(self, interaction: Interaction):
        guild_id = interaction.guild.id

        db_item = DBSession.get(LogChannelChannels, guild_id=guild_id)
        if not db_item:
            await respond_or_followup(COG_STRINGS["log_warn_channel_not_set"], interaction=interaction)
            return

        channel_id = db_item.channel_id
        DBSession.delete(db_item)

        channel = interaction.guild.get_channel(channel_id)
        if not channel:
            await respond_or_followup(
                COG_STRINGS["log_error_channel_deleted"].format(channel_id=channel_id),
                interaction=interaction
            )
            return

        await respond_or_followup(
            COG_STRINGS["log_get_channel_success"].format(channel=channel.mention),
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