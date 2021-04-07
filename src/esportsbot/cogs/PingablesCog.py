import discord
import asyncio
from discord.ext import commands
from discord.ext.commands.context import Context
from ..db_gateway import db_gateway
from ..lib.client import EsportsBot
from .. import lib
from datetime import timedelta
from ..reactionMenus import reactionPollMenu


DEFAULT_PINGABLE_COLOUR = 0x15e012 # green
MAX_ROLE_PING_TIMEOUT = timedelta(days=30)
MAX_PINGME_CREATE_POLL_LENGTH = timedelta(days=30)
MAX_PINGME_CREATE_THRESHOLD = 100


async def changePingablePrefix(prefix: str, guild: discord.Guild, roleID: int, roleName: str):
    role = guild.get_role(roleID)
    if role:
        await role.edit(name=prefix + roleName.title(), reason="pingme role prefix updated via admin command")


class PingablesCog(commands.Cog):
    def __init__(self, bot: "EsportsBot"):
        self.bot: "EsportsBot" = bot

    @commands.group(name="pingme", invoke_without_command=True)
    async def pingme(self, ctx: Context, *, args: str):
        pass


    @pingme.command(name="register", usage="pingme register <@role> <name>", help="Convert an existing role into a !pingme role")
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


    @pingme.command(name="unregister", usage="pingme unregister <@role>", help="Unregister a role from !pingme without removing it from the server")
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
                await ctx.message.reply("✅ Role successfully unregistered for `!pingme`.")
                await self.bot.adminLog(ctx.message, {"!pingme Role Unregistered", "Role: " + role.mention})


    @pingme.command(name="delete", usage="pingme delete <@role>", help="Delete a !pingme role from the server")
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


    @pingme.command(name="reset-cooldown", usage="pingme reset-cooldown <@role>", help="Reset the pinging cooldown for a !pingme role, making it pingable again instantly")
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


    @pingme.command(name="set-cooldown", usage="pingme set-cooldown [seconds=seconds] [minutes=minutes] [hours=hours] [days=days]", help="Set the cooldown between !pingme role pings")
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


    @pingme.command(name="set-create-threshold", usage="pingme set-create-threshold <num_votes>", help="Set minimum number of votes required to create a new role during !pingme create")
    @commands.has_permissions(administrator=True)
    async def cmd_set_pingme_create_threshold(self, ctx: Context, *, args: str):
        if not args:
            await ctx.message.reply(":x: Please give the new threshold!")
        elif not lib.stringTyping.strIsInt(args):
            await ctx.message.reply(":x: Invalid threshold! It must be a number.")
        elif int(args) < 1 or int(args) > MAX_PINGME_CREATE_THRESHOLD:
            await ctx.message.reply(":x: Invalid threshold! It must be between 1 and " + str(MAX_PINGME_CREATE_THRESHOLD) + ", inclusive.")
        else:
            db_gateway().update("guild_info", {"pingme_create_threshold": int(args)}, {"guild_id": ctx.guild.id})
            await ctx.message.reply("✅ Minimum votes for `!pingme create` successfully updated to " + args + " users.")
            await self.bot.adminLog(ctx.message, {"Votes Required For !pingme create Updated": "Minimum votes for new roles: " + args})


    @pingme.command(name="set-create-poll-length", usage="pingme set-create-poll-length [seconds=seconds] [minutes=minutes] [hours=hours] [days=days]", help="Set the amount of time which !pingme create polls run for")
    @commands.has_permissions(administrator=True)
    async def cmd_set_pingme_create_poll_length(self, ctx: Context, *, args: str):
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
        if timeoutTD > MAX_PINGME_CREATE_POLL_LENGTH:
            await ctx.message.reply(":x: The maximum `!pingme create` poll length is " + lib.timeUtil.td_format_noYM(MAX_ROLE_PING_TIMEOUT))
            return
        
        db_gateway().update("guild_info", {"pingme_create_poll_length_seconds": int(timeoutTD.total_seconds())}, {"guild_id": ctx.guild.id})
        await ctx.message.reply("✅ Poll length for `!pingme create` successfully updated to " + lib.timeUtil.td_format_noYM(timeoutTD) + ".")
        await self.bot.adminLog(ctx.message, {"Poll length For !pingme create Pings Updated": lib.timeUtil.td_format_noYM(timeoutTD)})


    @pingme.command(name="set-role-emoji", usage="pingme set-role-emoji <emoji>", help="Set the emoji which appears before the names of !pingme roles. Must be a built in emoji, not custom.")
    @commands.has_permissions(administrator=True)
    async def cmd_set_pingme_role_emoji(self, ctx: Context, *, args: str):
        if not args:
            await ctx.message.reply(":x: Please give the new emoji!")
        elif not lib.emotes.strIsUnicodeEmoji(args):
            await ctx.message.reply(":x: Invalid emoji! Make sure it's a built in one rather than custom.")
        else:
            db = db_gateway()
            db.update("guild_info", {"pingme_role_emoji": args}, {"guild_id": ctx.guild.id})
            rolesData = db.get("pingable_roles", {"guild_id": ctx.guild.id})
            if rolesData:
                progressMsg = await ctx.send("Renaming " + str(len(rolesData)) + " roles... ⏳")
                renamerTasks = set()
                for roleData in rolesData:
                    renamerTasks.add(changePingablePrefix(args, ctx.guild, roleData["role_id"], roleData["name"]))
                
                await asyncio.wait(renamerTasks)
                await progressMsg.edit(content="Renaming " + str(len(rolesData)) + " roles... ✅")

            await ctx.message.reply("Emoji prefix for `!pingme create` roles now updated to " + args + "!")
            await self.bot.adminLog(ctx.message, {"Emoji Prefix For !pingme roles Updated": "New emoji: " + args})


    @pingme.command(name="remove-role-emoji", usage="pingme remove-role-emoji <emoji>", help="Remove the emoji which appears before the names of !pingme roles.")
    @commands.has_permissions(administrator=True)
    async def cmd_remove_pingme_role_emoji(self, ctx: Context, *, args: str):
        db = db_gateway()
        guildData = db.get("guild_info", {"guild_id": ctx.guild.id})
        if guildData["pingme_role_emoji"] is None:
            await ctx.message.reply(":x: There is no `!pingme` role emoji set!")
        else:
            db.update("guild_info", {"pingme_role_emoji": None}, {"guild_id": ctx.guild.id})
            rolesData = db.get("pingable_roles", {"guild_id": ctx.guild.id})
            if rolesData:
                progressMsg = await ctx.send("Renaming " + str(len(rolesData)) + " roles... ⏳")
                renamerTasks = set()
                for roleData in rolesData:
                    renamerTasks.add(changePingablePrefix("", ctx.guild, roleData["role_id"], roleData["name"]))
                
                await asyncio.wait(renamerTasks)
                await progressMsg.edit(content="Renaming " + str(len(rolesData)) + " roles... ✅")

            await ctx.message.reply("Emoji prefix for `!pingme create` roles has been removed!")
            await self.bot.adminLog(ctx.message, {"Emoji Prefix For !pingme roles Removed": "‎"})


    @pingme.command(name="create", help="Start a poll for the creation of a new !pingme role")
    async def pingme_create(self, ctx: Context, *, args: str):
        if not args:
            await ctx.message.reply(":x: Please give the name of your new role!")
        else:
            db =  db_gateway()
            roleData = db.get("pingable_roles", {"name": args.lower()})
            if roleData and roleData[0]["guild_id"] == ctx.guild.id:
                await ctx.message.reply(":x: A `!pingme` role already exists with that name!")
            else:
                pollMsg = await ctx.send("‎")
                guildData = db.get("guild_info", {"guild_id": ctx.guild.id})[0]
                requiredVotes = guildData["pingme_create_threshold"]
                rolePoll = reactionPollMenu.InlineSingleOptionPollMenu(pollMsg, guildData["pingme_create_poll_length_seconds"], requiredVotes,
                                                                        pollStarter=ctx.author, authorName=ctx.author.display_name + " wants to make a new !pingme role!",
                                                                        desc="Name: " + args + "\nRequired votes: " + str(requiredVotes) + "\n\nReact if you want the role to be created!",
                                                                        footerTxt="This menu will expire in " + lib.timeUtil.td_format_noYM(timedelta(seconds=guildData["pingme_create_poll_length_seconds"])) + ".")
                await rolePoll.doMenu()
                if rolePoll.yesesReceived >= requiredVotes:
                    roleName = (guildData["pingme_role_emoji"] + args.title()) if guildData["pingme_role_emoji"] else args.title()
                    newRole = await ctx.guild.create_role(name=roleName, colour=DEFAULT_PINGABLE_COLOUR, mentionable=True, reason="New !pingme role creation requested via poll")
                    db.insert("pingable_roles", {"name": args.lower(), "guild_id": ctx.guild.id, "role_id": newRole.id,
                                                "on_cooldown": False, "last_ping": -1, "ping_count": 0,
                                                "monthly_ping_count": 0, "creator_id": ctx.author.id, "colour": DEFAULT_PINGABLE_COLOUR})
                    await ctx.message.reply("✅ The role has been created! Get it with `!pingme for " + args.lower() + "`")
                    await self.bot.adminLog(pollMsg, {"New !pingme Role Created": "Role: " + newRole.mention + "\nName: " + args})
                else:
                    await pollMsg.reply(ctx.author.mention + " The role has not been created, as the poll did not receive enough votes.")
                await pollMsg.edit(content="This poll has now ended.", embed=rolePoll.getMenuEmbed())


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


    @pingme.command(name="list", usage="pingme list", help="List all available `!pingme` roles")
    async def pingme_for(self, ctx: Context):
        allRolesData = db_gateway().get("pingable_roles", {"guild_id": ctx.guild.id})
        if not allRolesData:
            await ctx.message.reply(f":x: This guild has no `!pingme` roles! Make a new one with `{self.bot.command_prefix}pingme create`.")
        else:
            reportEmbed = discord.Embed(title="All !pingme Roles", desc=ctx.guild.name)
            reportEmbed.colour = discord.Colour.random()
            reportEmbed.set_thumbnail(url=self.bot.user.avatar_url_as(size=128))
            for roleData in allRolesData:
                reportEmbed.add_field(name=roleData["name"].title(),
                                        value="<@&" + str(roleData["role_id"]) + ">\nCreated by: <@" + str(roleData["creator_id"]) + ">\nTotal pings: " + str(roleData["ping_count"]))
            await ctx.reply(embed=reportEmbed)


    @pingme.command(name="clear", usage="pingme clear", help="Unsubscribe from all !pingme roles, if you have any.") 
    async def pingme_clear(self, ctx: Context, *, args: str):
        db = db_gateway()
        rolesToRemove = []
        for role in ctx.author.roles:
            if db.get("pingable_roles", {"role_id": role.id}):
                rolesToRemove.append(role)
        if rolesToRemove:
            await ctx.author.remove_roles(*rolesToRemove, reason="User unsubscribed from !pingme role via command")
            await ctx.message.reply("✅ You unsubscribed from " + str(len(rolesToRemove)) + " roles!")
        else:
            await ctx.message.reply(":x: You are not subsribed to any `!pingme` roles!")


def setup(bot):
    bot.add_cog(PingablesCog(bot))
