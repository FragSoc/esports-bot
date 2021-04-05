import discord
from discord.ext import commands
from discord.ext.commands.context import Context
from discord.ext.commands.context import Context
from ..db_gateway import db_gateway
from ..lib.client import EsportsBot
from .. import lib
from datetime import timedelta


DEFAULT_PINGABLE_COLOUR = 0x15e012 # green
MAX_ROLE_PING_TIMEOUT = timedelta(days=30)


class PingablesCog(commands.Cog):
    def __init__(self, bot: "EsportsBot"):
        self.bot: "EsportsBot" = bot

    @commands.command(name="add-pingable-role", usage="add-pingable-role <@role> <name>", help="Convert an existing role into a !pingme role")
    @commands.has_permissions(administrator=True)
    async def cmd_add_pingable_role(self, ctx: Context, *, args: str):
        argsSplit = args.split(" ")
        if len(argsSplit) < 2:
            await ctx.message.reply("Please provide a role ping and a name for your `!pingme` role!")
        elif not lib.stringTyping.strIsRoleMention(argsSplit[0]):
            await ctx.message.reply("Invalid role mention: " + argsSplit[0])
        elif len(ctx.message.role_mentions) != 1:
            await ctx.message.reply("Please only give one role mention!")
        else:
            roleName = args[len(argsSplit[0])+1:].lower()
            role = ctx.message.role_mentions[0]
            db = db_gateway()
            if db.get("pingable_roles", {"role_id": role.id}):
                await ctx.message.reply("that role is already pingable!")
            elif db.get("pingable_roles", {"name": roleName}):
                await ctx.message.reply("A `!pingme` role already exists with the name '" + roleName + "'!")
            else:
                db.insert("pingable_roles", {"guild_id": ctx.guild.id, "role_id": role.id, "on_cooldown": False,
                                            "last_ping": -1, "ping_count": 0, "monthly_ping_count": 0,
                                            "creator_id": ctx.author.id, "colour": DEFAULT_PINGABLE_COLOUR,
                                            "name": roleName})
                if not role.mentionable:
                    await role.edit(mentionable=True, colour=discord.Colour.green(), reason="setting up new pingable role")
                await ctx.message.reply("pingable role setup complete!")
                await self.bot.adminLog(ctx.message, {"New !pingme Role Registered", "Name: " + roleName + "\nRole: " + role.mention})


    @commands.command(name="remove-pingable-role", usage="remove-pingable-role <@role>", help="Unregister a role from !pingme without removing it from the server")
    @commands.has_permissions(administrator=True)
    async def cmd_remove_pingable_role(self, ctx: Context, *, args: str):
        if len(ctx.message.role_mentions) != 1:
            await ctx.message.reply("Please give one role mention!")
        else:
            db = db_gateway()
            role = ctx.message.role_mentions[0]
            if not db.get("pingable_roles", {"role_id": role.id}):
                await ctx.message.reply("that role is not pingable!")
            else:
                db.delete("pingable_roles", {"role_id": role.id})
                await ctx.message.reply("The role is no longer registered for `!pingme`!")
                await self.bot.adminLog(ctx.message, {"!pingme Role Unregistered", "Role: " + role.mention})


    @commands.command(name="delete-pingable-role", usage="delete-pingable-role <@role>", help="Delete a !pingme role from the server")
    @commands.has_permissions(administrator=True)
    async def cmd_delete_pingable_role(self, ctx: Context, *, args: str):
        if len(ctx.message.role_mentions) != 1:
            await ctx.message.reply("Please give one role mention!")
        else:
            db = db_gateway()
            role = ctx.message.role_mentions[0]
            if not db.get("pingable_roles", {"role_id": role.id}):
                await ctx.message.reply("that role is not pingable!")
            else:
                db.delete("pingable_roles", {"role_id": role.id})
                await role.delete(reason="role deletion requested via admin command")
                await ctx.message.reply("The role as been deleted!")
                await self.bot.adminLog(ctx.message, {"!pingme Role Deleted", "Name: " + role.name + "\nID: " + str(role.id)})


    @commands.command(name="reset-role-ping-cooldown", usage="reset-role-ping-cooldown <@role>", help="Reset the pinging cooldown for a !pingme role, making it pingable again instantly")
    @commands.has_permissions(administrator=True)
    async def cmd_reset_role_ping_cooldown(self, ctx: Context, *, args: str):
        if len(ctx.message.role_mentions) != 1:
            await ctx.message.reply("please mention one role")
        else:
            role = ctx.message.role_mentions[0]
            db = db_gateway()
            roleData = db.get("pingable_roles", {"role_id": role.id})
            if not roleData:
                await ctx.message.reply("that role is not pingable!")
            elif not roleData[0]["on_cooldown"]:
                await ctx.message.reply("that role is not on cooldown!")
            else:
                db.update("pingable_roles", {"on_cooldown": False}, {"role_id": role.id})
                if not role.mentionable:
                    await role.edit(mentionable=True, colour=discord.Colour.green(), reason="manual cooldown reset by user " + str(ctx.author.name) + "#" + str(ctx.author.id))
                await ctx.message.reply("The " + role.name + " role is now pingable again!")
                await self.bot.adminLog(ctx.message, {"Ping Cooldown Manually Reset For !pingme Role": role.mention})


    @commands.command(name="set-role-ping-cooldown", usage="set-role-ping-cooldown [seconds=seconds] [minutes=minutes] [hours=hours] [days=days]", help="Set the cooldown between !pingme role pings")
    @commands.has_permissions(administrator=True)
    async def cmd_set_role_ping_cooldown(self, ctx: Context, *, args: str):
        if not args:
            await ctx.message.reply(":x: Please give the new cooldown!")
            return

        argsSplit = args.split(" ")
        kwArgs = {}
        for arg in argsSplit:
            arg = arg.strip().lower()
            for kwArg in ["days=", "hours=", "seconds=", "minutes="]:
                if arg.startswith(kwArg):
                    kwArgs[kwArg[:-1]] = arg[len(kwArg):]
                    break
        
        timeoutDict = {}
        for timeName in ["days", "hours", "minutes", "seconds"]:
            if timeName in kwArgs:
                if not lib.stringTyping.strIsInt(kwArgs[timeName]) or int(kwArgs[timeName]) < 1:
                    await ctx.message.reply(":x: Invalid number of " + timeName + "!")
                    return

                timeoutDict[timeName] = int(kwArgs[timeName])
        
        timeoutTD = lib.timeUtil.timeDeltaFromDict(timeoutDict)
        if timeoutTD > MAX_ROLE_PING_TIMEOUT:
            await ctx.message.reply(":x: The maximum ping cooldown is " + lib.timeUtil.td_format_noYM(MAX_ROLE_PING_TIMEOUT))
            return
        
        db_gateway().update("guild_info", {"role_ping_cooldown_seconds": int(timeoutTD.total_seconds())}, {"guild_id": ctx.guild.id})
        await ctx.message.reply("Cooldown for !pingme roles now updated to " + lib.timeUtil.td_format_noYM(timeoutTD) + "!")
        await self.bot.adminLog(ctx.message, {"Cooldown For !pingme Role Pings Updated": lib.timeUtil.td_format_noYM(timeoutTD)})


    @commands.group(name="pingme", invoke_without_command=True)
    async def pingme(self, ctx: Context, *, args: str):
        await ctx.message.reply('Invalid sub command passed...')
        # await ctx.message.reply("No subcommand given")

    @pingme.command(name="create", help="Start a poll for the creation of a new !pingme role")
    async def pingme_create(self, ctx: Context, *, args: str):
        await ctx.message.reply("creating")

    @pingme.command(name="for", usage="pingme for <role name or alias>", help="Get yourself a !pingme role, to be notified about events and games.")
    async def pingme_for(self, ctx: Context, *, args: str):
        if not args:
            await ctx.message.reply(":x: Please give the name of the role you would like!")
        else:
            roleData = db_gateway().get("pingable_roles", {"name": args.lower()})
            if not roleData or roleData[0]["guild_id"] != ctx.guild.id:
                await ctx.message.reply(":x: Unrecognised role name!")
            else:
                role = ctx.guild.get_role(roleData[0]["role_id"])
                if role is None:
                    await ctx.message.reply(":x: I couldn't find the role! Please contact an administrator.")
                elif role in ctx.author.roles:
                    await ctx.author.remove_roles(role, reason="User unsubscribed from !pingme role via command")
                    await ctx.message.reply("✅ You removed the " + role.name + " role!")
                else:
                    await ctx.author.add_roles(role, reason="User subscribed to !pingme role via command")
                    await ctx.message.reply("✅ You got the " + role.name + " role!")


def setup(bot):
    bot.add_cog(PingablesCog(bot))
