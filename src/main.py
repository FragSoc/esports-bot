import psycopg2
import discord
from discord.ext import tasks, commands
from discord.utils import get

TOKEN = 'NjQ1MDM2ODIyNzI4Mjc4MDM2.Xc8vWg.YI2rCTXrP0AOm8c7oc3P2SSmXuY'

class db_connection():
    def __init__(self):
        self.conn = psycopg2.connect(host="192.168.1.77",
                                        database="esportsbot",
                                        user="postgres",
                                        password="Pass2020!")
        self.cur = self.conn.cursor()

    def query(self, query):
        self.cur.execute(query)
        self.conn.commit()

    def close(self):
        self.cur.close()
        self.conn.close()


def add_new_vm(vc_id, guild_id, owner_id):
    db = db_connection()
    db.query(f'INSERT INTO voicemaster (vc_id, guild_id, owner_id) VALUES ({vc_id}, {guild_id}, {owner_id})')
    db.close()

def add_new_log_channel(guild_id, channel_id):
    db = db_connection()
    db.query(f'INSERT INTO loggingchannel (guild_id, channel_id) VALUES ({guild_id}, {channel_id})')
    db.close()

client = commands.Bot(command_prefix = '!')
client.remove_command('help')

@client.event
async def on_ready():
    print('Bot is now active')
    await client.change_presence(status=discord.Status.dnd, activity=discord.Activity(type=discord.ActivityType.listening, name="your commands"))

@client.command()
@commands.has_permissions(manage_messages=True)
async def setLog(ctx, givenChannelId):
    channel_id = int(givenChannelId)
    guild_id = int(ctx.author.guild.id)
    await ctx.channel.send(f"ChannelID: {channel_id}, GuildID: {guild_id}")
    add_new_log_channel(guild_id, channel_id)


client.run(TOKEN)