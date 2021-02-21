from dotenv import load_dotenv
from base_functions import get_whether_in_vm_master, get_whether_in_vm_slave
from generate_schema import generate_schema
from db_gateway import db_gateway
from discord.utils import get
from discord.ext import tasks, commands
import os
import discord
load_dotenv()
from typing import Dict

from trimatix import client as discordClient
from trimatix import lib
from trimatix.reactionMenus.reactionMenu import ReactionMenu


TOKEN = os.getenv('DISCORD_TOKEN')

client = discordClient.instance()
client.remove_command('help')

async def send_to_log_channel(self, guild_id, msg):
    db_logging_call = db_gateway().get(
        'guild_info', params={'guild_id': guild_id})
    if db_logging_call and db_logging_call[0]['log_channel_id']:
        await self.bot.get_channel(db_logging_call[0]['log_channel_id']).send(msg)


@client.event
async def on_ready():
    client.init()
    print('Bot is now active')
    await client.change_presence(status=discord.Status.dnd, activity=discord.Activity(type=discord.ActivityType.listening, name="to my tears"))


@client.event
async def on_guild_join(guild):
    print(f"Joined the guild: {guild.name}")
    db_gateway().insert('guild_info', params={'guild_id': guild.id})


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
        client.reactionMenus.removeID(payload.message_id)


@client.event
async def on_raw_bulk_message_delete(payload: discord.RawBulkMessageDeleteEvent):
    """Called every time a group of messages is deleted.
    If any of the messages were a reaction menus, deactivate and unschedule those menus.

    :param discord.RawBulkMessageDeleteEvent payload: An event describing all messages deleted.
    """
    for msgID in payload.message_ids:
        if msgID in client.reactionMenus:
            client.reactionMenus.removeID(msgID)


@client.command()
@commands.has_permissions(administrator=True)
async def initialsetup(ctx):
    already_in_db = True if db_gateway().get(
        'guild_info', params={'guild_id': ctx.author.guild.id}) else False
    if already_in_db:
        await ctx.channel.send("This server is already set up")
    else:
        db_gateway().insert('guild_info', params={
            'guild_id': ctx.author.guild.id})
        await ctx.channel.send("This server has now been initialised")

# Generate Database Schema
generate_schema()

client.load_extension('cogs.VoicemasterCog')
client.load_extension('cogs.DefaultRoleCog')
client.load_extension('cogs.LogChannelCog')
client.load_extension('cogs.AdminCog')
client.load_extension('trimatix.MenusCog')
if os.getenv('ENABLE_TWITTER') == "True":
    client.load_extension('cogs.TwitterIntegrationCog')
if os.getenv('ENABLE_TWITCH') == "True":
    client.load_extension('cogs.TwitchIntegrationCog')

client.run(TOKEN)
