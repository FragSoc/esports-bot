import os
from dotenv import load_dotenv
import discord
from discord.ext import tasks, commands
from discord.utils import get
from db_gateway import db_gateway
from base_functions import *
load_dotenv()
import time

TOKEN = os.getenv('DISCORD_TOKEN')

client = commands.Bot(command_prefix = '!')
client.remove_command('help')

def add_new_vm(guild_id, owner_id, channel_id):
    db = db_connection()
    db.exec_query(f'INSERT INTO voicemaster (guild_id, owner_id, channel_id) VALUES ({guild_id}, {owner_id}, {channel_id})')
    db.close()


def add_new_log_channel(guild_id, channel_id):
    db = db_connection()
    db.exec_query(f'INSERT INTO loggingchannel (guild_id, channel_id) VALUES ({guild_id}, {channel_id})')
    db.close()


def is_vm(guild_id, channel_id):
    db = db_connection()
    returned = db.return_query(f'SELECT * FROM voicemaster WHERE guild_id = {guild_id} AND channel_id = {channel_id}')
    db.close()
    print(returned)


@client.event
async def on_ready():
    print('Bot is now active')
    await client.change_presence(status=discord.Status.dnd, activity=discord.Activity(type=discord.ActivityType.listening, name="to my tears"))


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


@client.command()
@commands.has_permissions(manage_messages=True)
async def setlogchannel(ctx, givenChannelId=None):
    start_time = time.time()
    log_to_channel = givenChannelId if givenChannelId else ctx.channel.id
    log_channel_exists = db_gateway().get('loggingchannel', params={'guild_id': ctx.author.guild.id})
    if bool(log_channel_exists):
        db_gateway().update('loggingchannel', set_params={'channel_id': log_to_channel}, where_params={'guild_id': ctx.author.guild.id})
        await ctx.channel.send("Updated")
    else:
        db_gateway().insert('loggingchannel', params={'guild_id': ctx.author.guild.id, 'channel_id': log_to_channel})
        await ctx.channel.send("Inserted")
    end_time = time.time()
    await ctx.channel.send(f'Action took: {round(end_time-start_time, 3)}s')


client.run(TOKEN)
