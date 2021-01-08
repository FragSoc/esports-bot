import os
from dotenv import load_dotenv
import discord
from discord.ext import tasks, commands
from discord.utils import get
from db_gateway import db_gateway
load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')

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

client = commands.Bot(command_prefix = '!')
client.remove_command('help')

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
    # if not givenChannelId:
    #     # They provided an ID
    # else:
    #     # They did not provide an ID

    channel_id = int(givenChannelId)
    guild_id = int(ctx.author.guild.id)
    add_new_log_channel(guild_id, channel_id)
    await ctx.channel.send(f"ChannelID: {channel_id}, GuildID: {guild_id}")


#client.run(TOKEN)
