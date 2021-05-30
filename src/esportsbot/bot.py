from typing import Dict, Any
from dotenv import load_dotenv
from . import lib
from .base_functions import get_whether_in_vm_master, get_whether_in_vm_slave
from .generate_schema import generate_schema
from .db_gateway import db_gateway
from discord.ext import commands
from discord.ext.commands import CommandNotFound, MissingRequiredArgument
from discord.ext.commands.context import Context
from discord import NotFound, HTTPException, Forbidden
import os
import discord
from datetime import datetime, timedelta
import asyncio


# Value to assign new guilds in their role_ping_cooldown_seconds attribute
DEFAULT_ROLE_PING_COOLDOWN = timedelta(hours=5)
# Value to assign new guilds in their pingme_create_poll_length_seconds attribute
DEFAULT_PINGME_CREATE_POLL_LENGTH = timedelta(hours=1)
# Value to assign new guilds in their pingme_create_threshold attribute
DEFAULT_PINGME_CREATE_THRESHOLD = 6

# EsportsBot client instance
client = lib.client.instance()
# TODO
client.remove_command('help')


def make_guild_init_data(guild: discord.Guild) -> Dict[str, Any]:
    """Construct default data for a guild database registration.

    :param discord.Guild guild: The guild to be registered
    :return: A dictionary with default guild attributes, including the guild ID
    :rtype: Dict[str, Any]
    """
    return {'guild_id': guild.id, 'num_running_polls': 0, 'role_ping_cooldown_seconds': int(DEFAULT_ROLE_PING_COOLDOWN.total_seconds()),
            "pingme_create_threshold": DEFAULT_PINGME_CREATE_THRESHOLD, "pingme_create_poll_length_seconds": int(DEFAULT_PINGME_CREATE_POLL_LENGTH.total_seconds())}


async def send_to_log_channel(guild_id, msg):
    db_logging_call = db_gateway().get(
        'guild_info', params={'guild_id': guild_id})
    if db_logging_call and db_logging_call[0]['log_channel_id']:
        await client.get_channel(db_logging_call[0]['log_channel_id']).send(msg)


@client.event
async def on_ready():
    # Initialize the reactionMenuDB, since this can't be done synchronously
    await client.init()
    await client.change_presence(status=discord.Status.dnd, activity=discord.Activity(type=discord.ActivityType.listening, name="your commands"))


@client.event
async def on_guild_join(guild):
    print(f"Joined the guild: {guild.name}")
    db_gateway().insert('guild_info', params=make_guild_init_data(guild))


@client.event
async def on_guild_remove(guild):
    print(f"Left the guild: {guild.name}")
    db_gateway().delete('guild_info', where_params={'guild_id': guild.id})


@client.event
async def on_member_join(member):
    default_role_exists = db_gateway().get(
        'guild_info', params={'guild_id': member.guild.id})

    if default_role_exists[0]['default_role_id']:
        default_role = member.guild.get_role(
            default_role_exists[0]['default_role_id'])
        await member.add_roles(default_role)
        await send_to_log_channel(member.guild.id, f"{member.mention} has joined the server and received the {default_role.mention} role")
    else:
        await send_to_log_channel(member.guild.id, f"{member.mention} has joined the server")


@client.event
async def on_voice_state_update(member, before, after):
    before_channel_id = before.channel.id if before.channel != None else False
    after_channel_id = after.channel.id if after.channel != None else False

    if before_channel_id and get_whether_in_vm_slave(member.guild.id, before_channel_id):
        # If you were in a slave VM VC
        if not before.channel.members:
            # Nobody else in VC
            await before.channel.delete()
            db_gateway().delete('voicemaster_slave', where_params={
                'guild_id': member.guild.id, 'channel_id': before_channel_id})
            await send_to_log_channel(member.guild.id, f"{member.mention} has deleted a VM slave")
        else:
            # Still others in VC
            await before.channel.edit(name=f"{before.channel.members[0].display_name}'s VC")
            db_gateway().update('voicemaster_slave', set_params={'owner_id': before.channel.members[0].id}, where_params={
                'guild_id': member.guild.id, 'channel_id': before_channel_id})
    elif after_channel_id and get_whether_in_vm_master(member.guild.id, after_channel_id):
        # Moved into a master VM VC
        slave_channel_name = f"{member.display_name}'s VC"
        new_slave_channel = await member.guild.create_voice_channel(slave_channel_name, category=after.channel.category)
        db_gateway().insert('voicemaster_slave', params={'guild_id': member.guild.id,
                                                         'channel_id': new_slave_channel.id,
                                                         'owner_id': member.id,
                                                         'locked': False,
                                                         })
        await member.move_to(new_slave_channel)
        await send_to_log_channel(member.guild.id, f"{member.mention} has created a VM slave")


@client.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    """Called every time a reaction is added to a message.
    If the message is a reaction menu, and the reaction is an option for that menu, trigger the menu option's behaviour.

    :param discord.RawReactionActionEvent payload: An event describing the message and the reaction added
    """
    # ignore bot reactions
    if payload.user_id != client.user.id:
        # Get rich, useable reaction data
        _, user, emoji = await lib.discordUtil.reactionFromRaw(client, payload)
        if None in [user, emoji]:
            return

        # If the message reacted to is a reaction menu
        if payload.message_id in client.reactionMenus and \
                client.reactionMenus[payload.message_id].hasEmojiRegistered(emoji):
            # Envoke the reacted option's behaviour
            await client.reactionMenus[payload.message_id].reactionAdded(emoji, user)


@client.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    """Called every time a reaction is removed from a message.
    If the message is a reaction menu, and the reaction is an option for that menu, trigger the menu option's behaviour.

    :param discord.RawReactionActionEvent payload: An event describing the message and the reaction removed
    """
    # ignore bot reactions
    if payload.user_id != client.user.id:
        # Get rich, useable reaction data
        _, user, emoji = await lib.discordUtil.reactionFromRaw(client, payload)
        if None in [user, emoji]:
            return

        # If the message reacted to is a reaction menu
        if payload.message_id in client.reactionMenus and \
                client.reactionMenus[payload.message_id].hasEmojiRegistered(emoji):
            # Envoke the reacted option's behaviour
            await client.reactionMenus[payload.message_id].reactionRemoved(emoji, user)


@client.event
async def on_raw_message_delete(payload: discord.RawMessageDeleteEvent):
    """Called every time a message is deleted.
    If the message was a reaction menu, deactivate and unschedule the menu.

    :param discord.RawMessageDeleteEvent payload: An event describing the message deleted.
    """
    if payload.message_id in client.reactionMenus:
        menu = client.reactionMenus[payload.message_id]
        try:
            client.reactionMenus.removeID(payload.message_id)
        except KeyError:
            pass
        else:
            await client.adminLog(None, {"Reaction menu deleted": "id: " + str(payload.message_id) \
                                                + "\nchannel: <#" + str(menu.msg.channel.id) + ">"
                                                + "\ntype: " + type(menu).__name__},
                                    guildID=payload.guild_id)


@client.event
async def on_raw_bulk_message_delete(payload: discord.RawBulkMessageDeleteEvent):
    """Called every time a group of messages is deleted.
    If any of the messages were a reaction menus, deactivate and unschedule those menus.

    :param discord.RawBulkMessageDeleteEvent payload: An event describing all messages deleted.
    """
    for msgID in payload.message_ids:
        if msgID in client.reactionMenus:
            menu = client.reactionMenus[payload.message_id]
            try:
                client.reactionMenus.removeID(msgID)
            except KeyError:
                pass
            else:
                await client.adminLog(None, {"Reaction menu deleted": "id: " + str(payload.message_id) \
                                                    + "\nchannel: <#" + str(menu.msg.channel.id) + ">"
                                                    + "\ntype: " + type(menu).__name__},
                                        guildID=payload.guild_id)


@client.event
async def on_command_error(ctx: Context, exception: Exception):
    """Handles printing errors to users if their command failed to call, E.g incorrect numbr of arguments
    Also prints exceptions to stdout, since the event loop usually consumes these.

    :param Context ctx: A context summarising the message which caused the error
    :param Exception exception: The exception caused by the message in ctx
    """
    if isinstance(exception, MissingRequiredArgument):
        await ctx.message.reply("Arguments are required for this command! See `" + client.command_prefix + "help " + ctx.invoked_with + "` for more information.")
    elif isinstance(exception, CommandNotFound):
        try:
            await ctx.message.add_reaction(client.unknownCommandEmoji.sendable)
        except (Forbidden, HTTPException):
            pass
        except NotFound:
            raise ValueError("Invalid unknownCommandEmoji: "
                             + client.unknownCommandEmoji.sendable)
    else:
        sourceStr = str(ctx.message.id)
        try:
            sourceStr += "/" + ctx.channel.name + "#" + str(ctx.channel.id) \
                + "/" + ctx.guild.name + "#" + str(ctx.guild.id)
        except AttributeError:
            sourceStr += "/DM@" + ctx.author.name + "#" + str(ctx.author.id)
        print(datetime.now().strftime("%m/%d/%Y %H:%M:%S - Caught "
                                      + type(exception).__name__ + " '") + str(exception) + "' from message " + sourceStr)
        lib.exceptions.print_exception_trace(exception)


@client.event
async def on_message(message):
    if not message.author.bot:
        # Ignore self messages
        guild_id = message.guild.id
        music_channel_in_db = db_gateway().get('music_channels', params={'guild_id': guild_id})
        if len(music_channel_in_db) > 0 and message.channel.id == music_channel_in_db[0].get('channel_id'):
            # The message was in a music channel and a song should be found
            music_cog_instance = client.cogs.get('MusicCog')
            await music_cog_instance.on_message_handle(message)

    # If message was command, perform the command
    await client.process_commands(message)


@client.command()
@commands.has_permissions(administrator=True)
async def initialsetup(ctx):
    already_in_db = db_gateway().get(
        'guild_info', params={'guild_id': ctx.author.guild.id})
    if already_in_db:
        await ctx.channel.send("This server is already set up")
    else:
        db_gateway().insert('guild_info', make_guild_init_data(ctx.guild))
        await ctx.channel.send("This server has now been initialised")


@client.event
async def on_message(message: discord.Message):
    if message.guild is not None and message.role_mentions:
        roleUpdateTasks = client.handleRoleMentions(message)
        await client.process_commands(message)
        if roleUpdateTasks:
            await asyncio.wait(roleUpdateTasks)
            for task in roleUpdateTasks:
                if e := task.exception():
                    lib.exceptions.print_exception_trace(e)
    else:
        await client.process_commands(message)


@client.event
async def on_guild_role_delete(role: discord.Role):
    """Handles unregistering of pingme roles when deleted directly in discord instead of via admin command

    :param Role role: The role which was removed
    """
    db = db_gateway()
    if db.get("pingable_roles", {"role_id": role.id}):
        db.delete("pingable_roles", {"role_id": role.id})
        logEmbed = discord.Embed()
        logEmbed.set_author(icon_url=client.user.avatar_url_as(size=64), name="Admin Log")
        logEmbed.set_footer(text=datetime.now().strftime("%m/%d/%Y, %H:%M:%S"))
        logEmbed.colour = discord.Colour.random()
        for aTitle, aDesc in {"!pingme Role Deleted": "Role: " + role.mention + "\nName: " + role.name + "\nDeleting user unknown, please see the server's audit log."}.items():
            logEmbed.add_field(name=str(aTitle), value=str(aDesc), inline=False)
        await client.adminLog(None, embed=logEmbed)


def launch():
    load_dotenv()
    TOKEN = os.getenv('DISCORD_TOKEN')

    # Generate Database Schema
    generate_schema()

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
