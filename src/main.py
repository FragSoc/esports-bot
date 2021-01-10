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

TOKEN = os.getenv('DISCORD_TOKEN')

client = commands.Bot(command_prefix = '!', intents=intents)
client.remove_command('help')


async def send_to_log_channel(guild_id, msg):
    db_logging_call = db_gateway().get('guild_info', params={'guild_id': guild_id})
    if db_logging_call:
        await client.get_channel(db_logging_call[0]['log_channel_id']).send(msg)


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
        # print("No default role set")
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
async def setlogchannel(ctx, given_channel_id=None):
    cleaned_channel_id = get_cleaned_id(given_channel_id) if given_channel_id else ctx.channel.id
    log_channel_exists = db_gateway().get('guild_info', params={'guild_id': ctx.author.guild.id})
    if bool(log_channel_exists):
        if log_channel_exists[0]['log_channel_id'] != cleaned_channel_id:
            db_gateway().update('guild_info', set_params={'log_channel_id': cleaned_channel_id}, where_params={'guild_id': ctx.author.guild.id})
            mention_log_channel = client.get_channel(cleaned_channel_id).mention
            await ctx.channel.send(f"Logging channel has been set to {mention_log_channel}")
            await send_to_log_channel(ctx.author.guild.id, f"{ctx.author.mention} has set this channel as the logging channel")
        else:
            await ctx.channel.send("Logging channel already set to this channel")
    else:
        db_gateway().insert('guild_info', params={'guild_id': ctx.author.guild.id, 'log_channel_id': cleaned_channel_id})
        mention_log_channel = client.get_channel(cleaned_channel_id).mention
        await ctx.channel.send(f"Logging channel has been set to {mention_log_channel}")
        await send_to_log_channel(ctx.author.guild.id, f"{ctx.author.mention} has set this channel as the logging channel")


@client.command()
@commands.has_permissions(administrator=True)
async def getlogchannel(ctx):
    log_channel_exists = db_gateway().get('guild_info', params={'guild_id': ctx.author.guild.id})

    if log_channel_exists[0]['log_channel_id']:
        mention_log_channel = client.get_channel(log_channel_exists[0]['log_channel_id']).mention
        await ctx.channel.send(f"Logging channel is set to {mention_log_channel}")
    else:
        await ctx.channel.send("Logging channel has not been set")


@client.command()
@commands.has_permissions(administrator=True)
async def removelogchannel(ctx):
    log_channel_exists = db_gateway().get('guild_info', params={'guild_id': ctx.author.guild.id})

    if log_channel_exists[0]['log_channel_id']:
        db_gateway().update('guild_info', set_params={'log_channel_id': 'NULL'}, where_params={'guild_id': ctx.author.guild.id})
        await ctx.channel.send("Log channel has been removed")
    else:
        await ctx.channel.send("Log channel has not been set")


@client.command()
@commands.has_permissions(administrator=True)
async def setdefaultrole(ctx, given_role_id=None):
    cleaned_role_id = get_cleaned_id(given_role_id) if given_role_id else False
    if cleaned_role_id:
        # Given a role, update record
        db_gateway().update('guild_info', set_params={'default_role_id': cleaned_role_id}, where_params={'guild_id': ctx.author.guild.id})
        await ctx.channel.send(f"Default role has been set to {cleaned_role_id}")
        default_role = ctx.author.guild.get_role(cleaned_role_id)
        await send_to_log_channel(ctx.author.guild.id, f"{ctx.author.mention} has set the default role to {default_role.mention}")
    else:
        # Not given a role
        await ctx.channel.send("You need to either @ a role or paste the ID")


@client.command()
@commands.has_permissions(administrator=True)
async def getdefaultrole(ctx):
    default_role_exists = db_gateway().get('guild_info', params={'guild_id': ctx.author.guild.id})

    if default_role_exists[0]['default_role_id']:
        await ctx.channel.send(f"Default role is set to {default_role_exists[0]['default_role_id']}")
    else:
        await ctx.channel.send("Default role has not been set")


@client.command()
@commands.has_permissions(administrator=True)
async def removedefaultrole(ctx):
    default_role_exists = db_gateway().get('guild_info', params={'guild_id': ctx.author.guild.id})

    if default_role_exists[0]['default_role_id']:
        db_gateway().update('guild_info', set_params={'default_role_id': 'NULL'}, where_params={'guild_id': ctx.author.guild.id})
        await ctx.channel.send("Default role has been removed")
        await send_to_log_channel(ctx.author.guild.id, f"{ctx.author.mention} has removed the default role")
    else:
        await ctx.channel.send("Default role has not been set")


@client.command()
@commands.has_permissions(administrator=True)
async def setvmchannel(ctx, given_channel_id=None):
    if given_channel_id:
        # Given a channel ID, update record
        channel_exists = db_gateway().get('voicemaster_master', params={'guild_id': ctx.author.guild.id, 'channel_id': given_channel_id})
        if channel_exists:
            await ctx.channel.send("This VC is already set as a VM master")
        else:
            db_gateway().insert('voicemaster_master', params={'guild_id': ctx.author.guild.id, 'channel_id': given_channel_id})
            await ctx.channel.send("This VC has now been set as a VM master")
            new_vm_master_channel = client.get_channel(int(given_channel_id))
            await send_to_log_channel(ctx.author.guild.id, f"{ctx.author.mention} has made {new_vm_master_channel.name} - {new_vm_master_channel.id} a VM master VC")
    else:
        # Not given a channel ID
        await ctx.channel.send("You need to include the VC ID")


@client.command()
@commands.has_permissions(administrator=True)
async def getvmchannel(ctx):
    master_vm_exists = db_gateway().get('voicemaster_master', params={'guild_id': ctx.author.guild.id})

    if master_vm_exists:
        master_vm_str = str()
        for record in master_vm_exists:
            master_vm_str += f"{client.get_channel(record['channel_id']).name} - {str(record['channel_id'])}\n"
        await ctx.channel.send(f"Current VM master VCs in this server:\n{master_vm_str}")
    else:
        await ctx.channel.send("No VCs in this server currently set as VM masters")


@client.command()
@commands.has_permissions(administrator=True)
async def removevmchannel(ctx, given_channel_id=None):
    if given_channel_id:
        # Given a channel ID, check it exists
        channel_exists = db_gateway().get('voicemaster_master', params={'guild_id': ctx.author.guild.id, 'channel_id': given_channel_id})
        if channel_exists:
            db_gateway().delete('voicemaster_master', where_params={'guild_id': ctx.author.guild.id, 'channel_id': given_channel_id})
            await ctx.channel.send("This VC is no longer a VM master")
            await send_to_log_channel(ctx.author.guild.id, f"{ctx.author.mention} has removed {new_vm_master_channel.name} - {new_vm_master_channel.id} from VM master VC")
        else:
            await ctx.channel.send("This VC is not currently a VM master")
    else:
        # Not given a channel ID
        await ctx.channel.send("You need to include the VC ID")


@client.command()
@commands.has_permissions(administrator=True)
async def removeallmasters(ctx):
    all_vm_masters = db_gateway().get('voicemaster_master', params={'guild_id': ctx.author.guild.id})
    for vm_master in all_vm_masters:
        db_gateway().delete('voicemaster_master', where_params={'channel_id': vm_master['channel_id']})
    await ctx.channel.send("Cleared all VM masters from this server")
    await send_to_log_channel(ctx.author.guild.id, f"{ctx.author.mention} has removed all VM masters")


@client.command()
@commands.has_permissions(administrator=True)
async def killvmslaves(ctx):
    all_vm_slaves = db_gateway().get('voicemaster_slave', params={'guild_id': ctx.author.guild.id})
    for vm_slave in all_vm_slaves:
        vm_slave_channel = client.get_channel(vm_slave['channel_id'])
        if vm_slave_channel:
            await vm_slave_channel.delete()
        db_gateway().delete('voicemaster_slave', where_params={'channel_id': vm_slave['channel_id']})
    await ctx.channel.send("Cleared all VM slaves from this server")
    await send_to_log_channel(ctx.author.guild.id, f"{ctx.author.mention} has removed all VM slaves")


@client.command()
#@commands.has_permissions(administrator=True)
async def lockvm(ctx):
    in_vm_slave = db_gateway().get('voicemaster_slave', params={'guild_id': ctx.author.guild.id,'channel_id': ctx.author.voice.channel.id})

    if in_vm_slave:
        if in_vm_slave[0]['owner_id'] == ctx.author.id:
            if not in_vm_slave[0]['locked']:
                db_gateway().update('voicemaster_slave', set_params={'locked': True}, where_params={'guild_id': ctx.author.guild.id,'channel_id': ctx.author.voice.channel.id})
                await ctx.author.voice.channel.edit(user_limit = len(ctx.author.voice.channel.members))
                await ctx.channel.send("Your VM slave has been locked 🔒")
                await send_to_log_channel(ctx.author.guild.id, f"{ctx.author.mention} has locked their VM slave")
            else:
                await ctx.channel.send("Your VM slave is already locked")
        else:
            await ctx.channel.send("You are not the owner of this VM slave")
    else:
        await ctx.channel.send("You are not currently in a VM slave")


@client.command()
#@commands.has_permissions(administrator=True)
async def unlockvm(ctx):
    in_vm_slave = db_gateway().get('voicemaster_slave', params={'guild_id': ctx.author.guild.id,'channel_id': ctx.author.voice.channel.id})

    if in_vm_slave:
        if in_vm_slave[0]['owner_id'] == ctx.author.id:
            if in_vm_slave[0]['locked']:
                # Unlock it
                db_gateway().update('voicemaster_slave', set_params={'locked': False}, where_params={'guild_id': ctx.author.guild.id,'channel_id': ctx.author.voice.channel.id})
                await ctx.author.voice.channel.edit(user_limit = 0)
                await ctx.channel.send("Your VM slave has been unlocked 🔓")
                await send_to_log_channel(ctx.author.guild.id, f"{ctx.author.mention} has unlocked their VM slave")
            else:
                # Not locked
                await ctx.channel.send("Your VM slave is already unlocked")
        else:
            await ctx.channel.send("You are not the owner of this VM slave")
    else:
        await ctx.channel.send("You are not currently in a VM slave")


client.run(TOKEN)
