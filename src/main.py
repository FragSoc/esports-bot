import os
import discord
intents = discord.Intents.default()
intents.members = True
from discord.ext import tasks, commands
from discord.utils import get
from db_gateway import db_gateway
from base_functions import get_whether_in_vm_master, get_whether_in_vm_slave
from dotenv import load_dotenv
load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')

client = commands.Bot(command_prefix = '!', intents=intents)
client.remove_command('help')


async def send_to_log_channel(self, guild_id, msg):
    db_logging_call = db_gateway().get('guild_info', params={'guild_id': guild_id})
    if db_logging_call and db_logging_call[0]['log_channel_id']:
        await self.bot.get_channel(db_logging_call[0]['log_channel_id']).send(msg)


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
    default_role_exists = db_gateway().get('guild_info', params={'guild_id': member.guild.id})

    if default_role_exists[0]['default_role_id']:
        default_role = member.guild.get_role(default_role_exists[0]['default_role_id'])
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
            db_gateway().delete('voicemaster_slave', where_params={'guild_id': member.guild.id, 'channel_id': before_channel_id})
            await send_to_log_channel(member.guild.id, f"{member.mention} has deleted a VM slave")
        else:
            # Still others in VC
            await before.channel.edit(name=f"{before.channel.members[0].display_name}'s VC")
            db_gateway().update('voicemaster_slave', set_params={'owner_id': before.channel.members[0].id}, where_params={'guild_id': member.guild.id, 'channel_id': before_channel_id})
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


@client.command()
@commands.has_permissions(administrator=True)
async def initialsetup(ctx):
    already_in_db = True if db_gateway().get('guild_info', params={'guild_id': ctx.author.guild.id}) else False
    if already_in_db:
        await ctx.channel.send("This server is already set up")
    else:
        db_gateway().insert('guild_info', params={'guild_id': ctx.author.guild.id})
        await ctx.channel.send("This server has now been initialised")


client.load_extension('cogs.VoicemasterCog')
client.load_extension('cogs.DefaultRoleCog')
client.load_extension('cogs.LogChannelCog')
client.load_extension('cogs.AdminCog')
# client.load_extension('cogs.TwitterIntegrationCog')
client.load_extension('cogs.TwitchIntegrationCog')


client.run(TOKEN)
