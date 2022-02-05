from esportsbot.lib import client, exceptions

from esportsbot.db_gateway import DBGatewayActions
from esportsbot.models import GuildInfo

from discord.ext.commands import CommandNotFound, MissingRequiredArgument
from discord.ext.commands.context import Context
from discord import NotFound, HTTPException, Forbidden
import os
import discord
from datetime import datetime

# EsportsBot client instance
client = client.instance()


@client.event
async def on_ready():
    """Initialize the reactionMenuDB and pingme role cooldowns, since this can't be done synchronously
    """
    await client.change_presence(
        status=discord.Status.dnd,
        activity=discord.Activity(type=discord.ActivityType.listening,
                                  name=f"commands using {os.getenv('COMMAND_PREFIX')}")
    )


@client.event
async def on_guild_join(guild):
    """
    When the bot joins a new server, initialise the DB entry for that guild in the GuildInfo table in the DB.
    :param guild: The server the bot just joined.
    """
    exists = DBGatewayActions().get(GuildInfo, guild_id=guild.id)
    if not exists:
        db_item = GuildInfo(guild_id=guild.id)
        DBGatewayActions().create(db_item)


@client.event
async def on_guild_remove(guild):
    """
    When the bot leaves a server, remove the data in the GuildInfo table in the DB.
    :param guild: The server the bot just left.
    """
    guild_from_db = DBGatewayActions().get(GuildInfo, guild_id=guild.id)
    if guild_from_db:
        DBGatewayActions().delete(guild_from_db)
        print(client.STRINGS["guild_leave"].format(guild_name=guild.name))


@client.event
async def on_command_error(ctx: Context, exception: Exception):
    """Handles printing errors to users if their command failed to call, E.g incorrect number of arguments
    Also prints exceptions to stdout, since the event loop usually consumes these.

    :param Context ctx: A context summarising the message which caused the error
    :param Exception exception: The exception caused by the message in ctx
    """
    if isinstance(exception, MissingRequiredArgument):
        await ctx.message.reply(
            client.STRINGS["command_error_required_arguments"].format(
                command_prefix=client.command_prefix,
                command_used=ctx.invoked_with
            )
        )

    elif isinstance(exception, CommandNotFound):
        try:
            await ctx.message.add_reaction(client.unknown_command_emoji.discord_emoji)
        except (Forbidden, HTTPException):
            pass
        except NotFound:
            raise ValueError("Invalid unknownCommandEmoji: " + client.unknown_command_emoji.discord_emoji)
    else:
        source_str = str(ctx.message.id)
        try:
            source_str += "/" + ctx.channel.name + "#" + str(ctx.channel.id) \
                + "/" + ctx.guild.name + "#" + str(ctx.guild.id)
            await client.admin_log(
                responsible_user=ctx.author,
                guild_id=ctx.guild.id,
                actions={
                    "command": ctx.message,
                    "Error Name": exception.__class__.__name__,
                    "Error Message": str(exception)
                },
                colour=discord.Colour.red()
            )
        except AttributeError:
            source_str += "/DM@" + ctx.author.name + "#" + str(ctx.author.id)
        print(
            datetime.now().strftime("%m/%d/%Y %H:%M:%S - Caught " + type(exception).__name__ + " '") + str(exception)
            + "' from message " + source_str
        )
        exceptions.print_exception_trace(exception)


@client.event
async def on_message(message):
    """
    When a message is sent, and it is not from a bot, check if the message was a command and if it was, execute the command.
    :param message: The message that was sent.
    """
    if not message.author.bot:
        await client.process_commands(message)


def launch():
    """
    Load all the enabled cogs, and start the bot.
    """
    if os.getenv("ENABLE_MUSIC", "FALSE").lower() == "true":
        client.load_extension("esportsbot.cogs.MusicCog")

    if os.getenv("ENABLE_TWITCH", "FALSE").lower() == "true":
        client.load_extension("esportsbot.cogs.TwitchCog")

    if os.getenv("ENABLE_TWITTER", "FALSE").lower() == "true":
        client.load_extension("esportsbot.cogs.TwitterCog")

    if os.getenv("ENABLE_PINGME", "FALSE").lower() == "true":
        client.load_extension("esportsbot.cogs.PingableRolesCog")

    if os.getenv("ENABLE_VOICEMASTER", "FALSE").lower() == "true":
        client.load_extension("esportsbot.cogs.VoicemasterCog")

    if os.getenv("ENABLE_DEFAULTROLE", "FALSE").lower() == "true":
        client.load_extension("esportsbot.cogs.DefaultRoleCog")

    if os.getenv("ENABLE_EVENTCATEGORIES", "FALSE").lower() == "true":
        client.load_extension("esportsbot.cogs.EventCategoriesCog")

    if os.getenv("ENABLE_ROLEREACTIONS", "FALSE").lower() == "true":
        client.load_extension("esportsbot.cogs.RoleReactCog")

    if os.getenv("ENABLE_VOTINGMENUS", "FALSE").lower() == "true":
        client.load_extension("esportsbot.cogs.VotingCog")

    client.load_extension("esportsbot.cogs.AdminCog")
    client.load_extension("esportsbot.cogs.LogChannelCog")

    client.run(os.getenv("DISCORD_TOKEN"))
