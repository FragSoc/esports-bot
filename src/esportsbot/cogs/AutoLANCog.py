from asyncio import tasks
from discord.ext import commands
from discord.ext.commands.context import Context
from discord import PartialMessage, Forbidden
from ..db_gateway import db_gateway
import asyncio
from .. import lib
from ..lib.client import EsportsBot


class AutoLANCog(commands.Cog):
    def __init__(self, bot: "EsportsBot"):
        self.bot: "EsportsBot" = bot


    async def getGuildEventSettings(self, ctx, eventName):
        db = db_gateway()
        guildData = db.get("guild_info", params={"guild_id": ctx.guild.id})[0]
        if not guildData["shared_role_id"]:
            await ctx.message.reply(f":x: No shared role has been set for this server! Use the `{self.bot.command_prefix}set-shared-role` command to set one.")
        else:
            eventData = db.get("event_channels", params={"guild_id": ctx.guild.id, "event_name": eventName})[0]
            if not eventData:
                if not (allEvents := db.get("event_channels", params={"guild_id": ctx.guild.id})):
                    await ctx.message.reply(":x: This server doesn't have any event categories registered!")
                else:
                    await ctx.message.reply(":x: Unrecognised event. The following events exist in this server: " + ", ".join(e["event_name"].title() for e in allEvents))
            else:
                return (guildData, eventData)
        return ()

    
    @commands.command(name="open-event", usage="open-event <event name>", help="Reveal the signin channel for the named event channel.")
    @commands.has_permissions(administrator=True)
    async def admin_cmd_open_event(self, ctx: Context, *, args):
        if not args:
            await ctx.message.reply(":x: Please give the name of the event you'd like to open!")
        elif allData := await self.getGuildEventSettings(ctx, args.lower()):
            guildData, eventData = allData
            eventName = args.lower()
            signinMenu = self.bot.reactionMenus[eventData["signin_menu_id"]]
            eventChannel = signinMenu.msg.channel
            if not eventChannel.permissions_for(ctx.guild.me).manage_permissions:
                await ctx.send(":x: I don't have permission to edit the permissions in <#" + str(eventChannel.id) + ">!")
            else:
                sharedRole = ctx.guild.get_role(guildData["shared_role_id"])
                if not eventChannel.overwrites_for(sharedRole).read_messages:
                    await eventChannel.set_permissions(sharedRole, read_messages=True,
                                                    reason=ctx.author.name + f" opened the {eventName} event via the {self.bot.command_prefix}open-event command")
                    await ctx.send("✅ <#" + str(eventChannel.id) + "> is now visible to **" + sharedRole.name + "**!")
                    await self.bot.adminLog(ctx.message, {"Event signin channel made visible": "<#" + str(eventChannel.id) + ">"})
                else:
                    await ctx.send(f":x: The {eventName} signin channel is already open! <#{eventChannel.id!s}>")


    @commands.command(name="close-event", usage="close-event <event name>",
                        help="Hide the signin channel for the named event, reset the signin menu, and remove the event's role from users.")
    @commands.has_permissions(administrator=True)
    async def admin_cmd_close_event(self, ctx: Context, *, args):
        if not args:
            await ctx.message.reply(":x: Please give the name of the event you'd like to open!")
        elif allData := await self.getGuildEventSettings(ctx, args.lower()):
            guildData, eventData = allData
            signinMenu = self.bot.reactionMenus[eventData["signin_menu_id"]]
            eventChannel = signinMenu.msg.channel
            myPerms = eventChannel.permissions_for(ctx.guild.me)
            if not myPerms.manage_permissions:
                await ctx.send(f":x: I don't have permission to edit the permissions in <#{eventChannel.id!s}>!")
            elif not myPerms.manage_roles:
                await ctx.send(":x: I don't have permission to assign roles!\nPlease give me the 'manage roles' permission.")
            else:
                eventRole = ctx.guild.get_role(eventData["role_id"])
                if eventRole.position >= ctx.guild.self_role.position:
                    await ctx.send(f":x: I don't have permission to unassign the **{eventRole.name}** role!\n" \
                                    + f"Please move it below my {ctx.guild.self_role.name} role.")
                else:
                    eventName = args.lower()
                    sharedRole = ctx.guild.get_role(guildData["shared_role_id"])
                    channelEdited = eventChannel.overwrites_for(sharedRole).read_messages
                    usersEdited = len(eventRole.members)
                    # signinMenu.msg = await signinMenu.msg.channel.fetch_message(signinMenu.msg.id)
                    menuReset = True # len(signinMenu.msg.reactions) > 1

                    if True not in (channelEdited, usersEdited, menuReset):
                        await ctx.message.reply(f"Nothing to do!\n*(<#{signinMenu.msg.channel.id!s}> already invisible to {sharedRole.name}, no reactions on signin menu, no users with {eventRole.name} role)*")
                    else:
                        loadingTxts = ("Closing channel... " + ("⏳" if channelEdited else "✅"),
                                        "Unassigning role" + ((" from " + str(usersEdited) + " users... ⏳") if usersEdited else "... ✅"),
                                        "Resetting signin menu... " + ("⏳" if menuReset else "✅"))
                        loadingMsg = await ctx.send("\n".join(loadingTxts))
                        adminActions = {"Event Closed": f"Event name: {eventName}",
                                        "Role menu reset": f"id: {signinMenu.msg.id!s}\ntype: {type(signinMenu).__name__}\n[Menu]({signinMenu.msg.jump_url})"}

                        if channelEdited:
                            await eventChannel.set_permissions(sharedRole, read_messages=False,
                                                                reason=f"{ctx.author.name} closed the {eventName} event via {self.bot.command_prefix}close-event command")
                            loadingTxts[0] = loadingTxts[0][:-1] + "✅"
                            asyncio.create_task(loadingMsg.edit(content="\n".join(loadingTxts)))
                            adminActions["Event Channel Made Invisible"] = f"<#{eventChannel.id!s}>"
                        membersFutures = set()
                        for member in eventRole.members:
                            membersFutures.add(asyncio.create_task(member.remove_roles(eventRole, reason=f"{ctx.author.name} closed the {eventName} event via {self.bot.command_prefix}close-event command")))
                        
                        if menuReset:
                            await signinMenu.updateMessage()
                            loadingTxts[2] = loadingTxts[2][:-1] + "✅"
                            await loadingMsg.edit(content="\n".join(loadingTxts))

                        if usersEdited:
                            await asyncio.wait(membersFutures)
                            loadingTxts[1] = loadingTxts[1][:-1] + "✅"
                            await loadingMsg.edit(content="\n".join(loadingTxts))
                            adminActions["Event Role Removed"] = f"Users: {usersEdited!s}\n<@&{eventRole.id!s}>"
                        await ctx.message.reply("Done!")
                        await self.bot.adminLog(ctx.message, adminActions)


    @commands.command(name="set-event-signin-menu", usage="set-event-signin-menu <id> <event name>",
                        help="Change the event signin menu to use with `open-event` and `close-event`.")
    @commands.has_permissions(administrator=True)
    async def admin_cmd_set_event_signin_menu(self, ctx: Context, *, args: str):
        if len(args.split(" ") < 2):
            await ctx.send(":x: Please provide a menu ID and event name!")
        else:
            menuID = args.split(" ")[0]
            if not lib.stringTyping.strIsInt(menuID):
                await ctx.send(":x: Invalid menu ID!\nTo get a menu ID, enable discord's developer mode, right click on the menu, and click 'copy ID'")
            elif int(menuID) not in self.bot.reactionMenus:
                await ctx.send(f":x: Unrecognised menu ID: {menuID}")
            else:
                eventName = args[len(menuID)+1:].lower()
                db = db_gateway()
                if not db.get("event_categories", {"guild_id": ctx.guild.id, "event_name": eventName}):
                    if not (allEvents := db.get("event_channels", params={"guild_id": ctx.guild.id})):
                        await ctx.message.reply(":x: This server doesn't have any event categories registered!")
                    else:
                        await ctx.message.reply(":x: Unrecognised event. The following events exist in this server: " + ", ".join(e["event_name"].title() for e in allEvents))
                else:
                    menu = self.bot.reactionMenus[int(menuID)]
                    db.update('event_channels', set_params={"signin_menu_id": menu.msg.id}, where_params={"guild_id": ctx.guild.id, "event_name": eventName})
                    await ctx.send(f"✅ The {eventName} event signin menu is now: {menu.msg.jump_url}")
                    await self.bot.adminLog(ctx.message, {"Event signin menu updated": f"Event name: {eventName}\nMenu id: {menuID}\ntype: {type(menu).__name__}\n[Menu]({menu.msg.jump_url})"})


    @commands.command(name="set-shared-role", usage="set-shared-role <role>",
                        help="Change the role to admit/deny into *all* event signin menus. This should NOT be the same as any event role. Role can be given as either a mention or an ID.")
    @commands.has_permissions(administrator=True)
    async def admin_cmd_set_shared_role(self, ctx: Context, *, args: str):
        if not args:
            await ctx.send(":x: Please provide a role to set!")
        else:
            if not (lib.stringTyping.strIsInt(args) or lib.stringTyping.strIsRoleMention(args)):
                await ctx.send(":x: Invalid role! Please give your role as either a mention or an ID.")
            else:
                roleID = int(args.lstrip("<@&").rstrip(">"))
                role = ctx.guild.get_role(roleID)
                if role is None:
                    await ctx.send(":x: Unrecognised role!")
                else:
                    db_gateway().update('guild_info', set_params={"shared_role_id": roleID}, where_params={"guild_id": ctx.guild.id})
                    await ctx.send(f"✅ The shared role is now **{role.name}**.")
                    await self.bot.adminLog(ctx.message, {"Shared role set": "<@&{roleID!s}>"})


    @commands.command(name="set-event-role", usage="set-event-role <role> <event name>",
                        help="Change the role to remove during `close-event`. This should NOT be the same as your shared role. Role can be given as either a mention or an ID.")
    @commands.has_permissions(administrator=True)
    async def admin_cmd_set_event_role(self, ctx: Context, *, args: str):
        if len(args.split(" ") < 2):
            await ctx.send(":x: Please provide a role to set!")
        else:
            roleStr = args.split(" ")[0]
            if not (lib.stringTyping.strIsInt(roleStr) or lib.stringTyping.strIsRoleMention(roleStr)):
                await ctx.send(f":x: Invalid role: {roleStr} Please give your role as either a mention or an ID.")
            else:
                roleID = int(roleStr.lstrip("<@&").rstrip(">"))
                role = ctx.guild.get_role(roleID)
                if role is None:
                    await ctx.send(":x: Unrecognised role!")
                else:
                    eventName = args[len(roleStr)+1:].lower()
                    db = db_gateway()
                    if not db.get("event_categories", {"guild_id": ctx.guild.id, "event_name": eventName}):
                        if not (allEvents := db.get("event_channels", params={"guild_id": ctx.guild.id})):
                            await ctx.message.reply(":x: This server doesn't have any event categories registered!")
                        else:
                            await ctx.message.reply(":x: Unrecognised event. The following events exist in this server: " + ", ".join(e["event_name"].title() for e in allEvents))
                    else:
                        db.update('event_categories', set_params={"role_id": roleID}, where_params={"guild_id": ctx.guild.id, "event_name": eventName})
                        await ctx.send(f"✅ The {eventName} event role is now **{role.name}**.")
                        await self.bot.adminLog(ctx.message, {"Event role set": f"<@&{roleID!s}>"})


def setup(bot):
    bot.add_cog(AutoLANCog(bot))
    