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

    @commands.command(name="add-pingable-role", usage="add-pingable-role <@role>")
    @commands.has_permissions(administrator=True)
    async def cmd_add_pingable_role(self, ctx: Context, *, args: str):
        if len(ctx.message.role_mentions) != 1:
            await ctx.message.reply("please mention one role")
        else:
            role= ctx.message.role_mentions[0]
            db = db_gateway()
            roleData = db.get("pingable_roles", {"role_id": role.id})
            if roleData:
                await ctx.message.reply("that role is already pingable!")
            else:
                db.insert("pingable_roles", {"role_id": role.id, "on_cooldown": False,
                                            "last_ping": -1, "ping_count": 0, "monthly_ping_count": 0,
                                            "creator_id": ctx.author.id, "colour": DEFAULT_PINGABLE_COLOUR})
                db.insert("guild_pingables", {"guild_id": ctx.guild.id, "role_id": role.id})
                if not role.mentionable:
                    await role.edit(mentionable=True, colour=discord.Colour.green(), reason="setting up new pingable role")
                await ctx.message.reply("pingable role setup complete!")
                await self.bot.adminLog(ctx.message, {"New !pingme Role Registered", role.mention})


    @commands.command(name="reset-role-ping-cooldown", usage="reset-role-ping-cooldown <@role>")
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
                await ctx.message.reply("role has been made pingable again!")
                await self.bot.adminLog(ctx.message, {"Ping Cooldown Manually Reset For !pingme Role", role.mention})


    @commands.command(name="set-role-ping-cooldown", usage="reset-role-ping-cooldown [seconds=seconds] [minutes=minutes] [hours=hours] [days=days]")
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




def setup(bot):
    bot.add_cog(PingablesCog(bot))
