from esportsbot import lib

from esportsbot.db_gateway import DBGatewayActions
from esportsbot.models import Guild_info

from discord.ext.commands import CommandNotFound, MissingRequiredArgument
from discord.ext.commands.context import Context
from discord import NotFound, HTTPException, Forbidden
import os
import discord
from datetime import datetime, timedelta

# Value to assign new guilds in their role_ping_cooldown_seconds attribute
DEFAULT_ROLE_PING_COOLDOWN = timedelta(hours=5)
# Value to assign new guilds in their pingme_create_poll_length_seconds attribute
DEFAULT_PINGME_CREATE_POLL_LENGTH = timedelta(hours=1)
# Value to assign new guilds in their pingme_create_threshold attribute
DEFAULT_PINGME_CREATE_THRESHOLD = 6

# EsportsBot client instance
client = lib.client.instance()


@client.event
async def on_ready():
    """Initialize the reactionMenuDB and pingme role cooldowns, since this can't be done synchronously
    """
    await client.change_presence(
        status=discord.Status.dnd,
        activity=discord.Activity(type=discord.ActivityType.listening,
                                  name="your commands")
    )


@client.event
async def on_guild_remove(guild):
    guild_from_db = DBGatewayActions().get(Guild_info, guild_id=guild.id)
    if guild_from_db:
        DBGatewayActions().delete(guild_from_db)
        print(f"Left the guild: {guild.name}")


@client.event
async def on_command_error(ctx: Context, exception: Exception):
    """Handles printing errors to users if their command failed to call, E.g incorrect numbr of arguments
    Also prints exceptions to stdout, since the event loop usually consumes these.

    :param Context ctx: A context summarising the message which caused the error
    :param Exception exception: The exception caused by the message in ctx
    """
    if isinstance(exception, MissingRequiredArgument):
        await ctx.message.reply(
            "Arguments are required for this command! See `" + client.command_prefix + "help " + ctx.invoked_with
            + "` for more information."
        )
    elif isinstance(exception, CommandNotFound):
        try:
            await ctx.message.add_reaction(client.unknown_command_emoji.sendable)
        except (Forbidden, HTTPException):
            pass
        except NotFound:
            raise ValueError("Invalid unknownCommandEmoji: " + client.unknown_command_emoji.sendable)
    else:
        sourceStr = str(ctx.message.id)
        try:
            sourceStr += "/" + ctx.channel.name + "#" + str(ctx.channel.id) \
                + "/" + ctx.guild.name + "#" + str(ctx.guild.id)
        except AttributeError:
            sourceStr += "/DM@" + ctx.author.name + "#" + str(ctx.author.id)
        print(
            datetime.now().strftime("%m/%d/%Y %H:%M:%S - Caught " + type(exception).__name__ + " '") + str(exception)
            + "' from message " + sourceStr
        )
        lib.exceptions.print_exception_trace(exception)


@client.event
async def on_message(message):
    if not message.author.bot:
        await client.process_commands(message)


def launch():

    TOKEN = os.getenv('DISCORD_TOKEN')

    client.load_extension('esportsbot.cogs.VoicemasterCog')
    client.load_extension('esportsbot.cogs.DefaultRoleCog')
    client.load_extension('esportsbot.cogs.LogChannelCog')
    client.load_extension('esportsbot.cogs.AdminCog')
    client.load_extension('esportsbot.cogs.MenusCog')
    client.load_extension('esportsbot.cogs.PingablesCog')
    client.load_extension('esportsbot.cogs.EventCategoriesCog')
    if os.getenv('ENABLE_TWITTER').lower() == 'true':
        client.load_extension('esportsbot.cogs.TwitterIntegrationCog')
    if os.getenv('ENABLE_TWITCH').lower() == 'true':
        client.load_extension('esportsbot.cogs.TwitchIntegrationCog')
    if os.getenv('ENABLE_MUSIC') == 'TRUE':
        client.load_extension('esportsbot.cogs.MusicCog')

    client.run(TOKEN)
