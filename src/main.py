import os
from dotenv import load_dotenv
import discord
intents = discord.Intents.default()
intents.members = True
from discord.ext import tasks, commands
from discord.utils import get
from db_gateway import db_gateway
from base_functions import *
load_dotenv()
import time

TOKEN = os.getenv('DISCORD_TOKEN')

client = commands.Bot(command_prefix = '!', intents=intents)
client.remove_command('help')

def add_new_vm(guild_id, owner_id, channel_id):
    db = db_connection()
    db.exec_query(f'INSERT INTO voicemaster (guild_id, owner_id, channel_id) VALUES ({guild_id}, {owner_id}, {channel_id})')
    db.close()


def is_vm(guild_id, channel_id):
    db = db_connection()
    returned = db.return_query(f'SELECT * FROM voicemaster WHERE guild_id = {guild_id} AND channel_id = {channel_id}')
    db.close()
    print(returned)


@client.command()
@commands.has_permissions(manage_messages=True)
async def thisChannelIn(ctx):
    channel_id = int(ctx.channel.id)
    guild_id = int(ctx.author.guild.id)
    is_vm(guild_id, channel_id)


@client.command()
@commands.has_permissions(manage_messages=True)
async def addChannel(ctx):
    channel_id = int(ctx.channel.id)
    guild_id = int(ctx.author.guild.id)
    owner_id = ctx.author.id
    add_new_vm(guild_id, owner_id, channel_id)


######### REWRITE #########


@client.event
async def on_ready():
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
    print(f"User {member.name} joined the guild {member.guild.name}")

    default_role_exists = db_gateway().get('guild_info', params={'guild_id': member.guild.id})

    if default_role_exists[0]['default_role_id']:
        await member.add_roles(member.guild.get_role(default_role_exists[0]['default_role_id']))
    else:
        print("No default role set")


@client.command()
@commands.has_permissions(administrator=True)
async def setlogchannel(ctx, given_channel_id=None):
    start_time = time.time()

    cleaned_channel_id = get_cleaned_id(given_channel_id) if given_channel_id else ctx.channel.id
    log_channel_exists = db_gateway().get('guild_info', params={'guild_id': ctx.author.guild.id})
    if bool(log_channel_exists):
        if log_channel_exists[0]['log_channel_id'] != cleaned_channel_id:
            db_gateway().update('guild_info', set_params={'log_channel_id': cleaned_channel_id}, where_params={'guild_id': ctx.author.guild.id})
            mention_log_channel = client.get_channel(cleaned_channel_id).mention
            await ctx.channel.send(f"Logging channel has been set to {mention_log_channel}")
        else:
            await ctx.channel.send("Logging channel already set to this channel")
    else:
        db_gateway().insert('guild_info', params={'guild_id': ctx.author.guild.id, 'log_channel_id': cleaned_channel_id})
        await ctx.channel.send("Logging channel has been set")

    end_time = time.time()
    await ctx.channel.send(f'Action took: {round(end_time-start_time, 3)}s')


@client.command()
@commands.has_permissions(administrator=True)
async def getlogchannel(ctx):
    start_time = time.time()

    log_channel_exists = db_gateway().get('guild_info', params={'guild_id': ctx.author.guild.id})

    if log_channel_exists[0]['log_channel_id']:
        mention_log_channel = client.get_channel(log_channel_exists[0]['log_channel_id']).mention
        await ctx.channel.send(f"Logging channel is set to {mention_log_channel}")
    else:
        await ctx.channel.send("Logging channel has not been set")

    end_time = time.time()
    await ctx.channel.send(f'Action took: {round(end_time-start_time, 3)}s')


@client.command()
@commands.has_permissions(administrator=True)
async def removelogchannel(ctx):
    start_time = time.time()

    log_channel_exists = db_gateway().get('guild_info', params={'guild_id': ctx.author.guild.id})

    if log_channel_exists[0]['log_channel_id']:
        db_gateway().update('guild_info', set_params={'log_channel_id': 'NULL'}, where_params={'guild_id': ctx.author.guild.id})
        await ctx.channel.send("Log channel has been removed")
    else:
        await ctx.channel.send("Log channel has not been set")

    end_time = time.time()
    await ctx.channel.send(f'Action took: {round(end_time-start_time, 3)}s')


@client.command()
@commands.has_permissions(administrator=True)
async def setdefaultrole(ctx, given_role_id=None):
    start_time = time.time()

    cleaned_role_id = get_cleaned_id(given_role_id) if given_role_id else False
    if cleaned_role_id:
        # Given a role, update record
        db_gateway().update('guild_info', set_params={'default_role_id': cleaned_role_id}, where_params={'guild_id': ctx.author.guild.id})
        await ctx.channel.send(f"Default role has been set to {cleaned_role_id}")
    else:
        # Not given a role
        await ctx.channel.send("You need to either @ a role or paste the ID")

    end_time = time.time()
    await ctx.channel.send(f'Action took: {round(end_time-start_time, 3)}s')


@client.command()
@commands.has_permissions(administrator=True)
async def getdefaultrole(ctx):
    start_time = time.time()

    default_role_exists = db_gateway().get('guild_info', params={'guild_id': ctx.author.guild.id})

    if default_role_exists[0]['default_role_id']:
        await ctx.channel.send(f"Default role is set to {default_role_exists[0]['default_role_id']}")
    else:
        await ctx.channel.send("Default role has not been set")

    end_time = time.time()
    await ctx.channel.send(f'Action took: {round(end_time-start_time, 3)}s')


@client.command()
@commands.has_permissions(administrator=True)
async def removedefaultrole(ctx):
    start_time = time.time()

    default_role_exists = db_gateway().get('guild_info', params={'guild_id': ctx.author.guild.id})

    if default_role_exists[0]['default_role_id']:
        db_gateway().update('guild_info', set_params={'default_role_id': 'NULL'}, where_params={'guild_id': ctx.author.guild.id})
        await ctx.channel.send("Default role has been removed")
    else:
        await ctx.channel.send("Default role has not been set")

    end_time = time.time()
    await ctx.channel.send(f'Action took: {round(end_time-start_time, 3)}s')


client.run(TOKEN)
