from discord.ext import commands
from discord.ext.commands.context import Context
from db_gateway import db_gateway
from .client import EsportsBot
import asyncio
from . import lib


class AutoLANCog(commands.Cog):
    def __init__(self, bot: "EsportsBot"):
        self.bot: "EsportsBot" = bot


    async def verifyLANSettings(self, ctx, guildData):
        for att, name, cmd in ( (guildData["lan_signin_menu_id"],               "LAN signin menu",  "set-lan-signin-menu"),
                                (None if guildData["lan_signin_menu_id"] in self.bot.reactionMenus else 1, "LAN signin menu", "set-lan-signin-menu"),
                                (guildData["shared_role_id"],                   "shared role",      "set-shared-role"),
                                (ctx.guild.get_role(guildData["shared_role_id"]), "shared role",    "set-shared-role"),
                                (guildData["lan_role_id"],                      "LAN role",         "set-lan-role"),
                                (ctx.guild.get_role(guildData["lan_role_id"]),  "LAN role",         "set-lan-role")):
            if att is None:
                await ctx.send(":x: No " + name + " has been set for this server, or it no longer exists!\n" \
                                + "Use the `" + self.bot.command_prefix + cmd + "` command to set one.")
                return False
        return True

    
    @commands.command(name="open-lan", usage="open-lan", help="Reveal the LAN signin channel of the server.")
    @commands.has_permissions(administrator=True)
    async def admin_cmd_open_lan(self, ctx: Context, *, args: str):
        guildData = db_gateway().get('guild_info', params={"guild_id": ctx.guild.id})
        if await self.verifyLANSettings(ctx, guildData):
            lanChannel = guildData["lan_signin_menu_id"].msg.channel
            if not lanChannel.permissions_for(ctx.guild.me).manage_permissions:
                await ctx.send(":x: I don't have permission to edit the permissions in <#" + lanChannel.id + ">!")
            else:
                sharedRole = ctx.guild.get_role(guildData["shared_role_id"])
                if not lanChannel.overwrites_for(sharedRole).read_messages:
                    await lanChannel.set_permissions(sharedRole, read_messages=True,
                                                        reason=ctx.author.name + " used the " + self.bot.command_prefix + "open-lan command")
                    await ctx.send("✅ <#" + lanChannel.id + "> is now visible to **" + sharedRole.name + "**!")
                else:
                    await ctx.send(":x: The lan channel is already open! <#" + lanChannel.id + ">")


    @commands.command(name="close-lan", usage="close-lan",
                        help="Hide the LAN signin channel of the server, reset the signin menu, and remove the LAN role from users.")
    @commands.has_permissions(administrator=True)
    async def admin_cmd_close_lan(self, ctx: Context, *, args: str):
        guildData = db_gateway().get('guild_info', params={"guild_id": ctx.guild.id})
        if await self.verifyLANSettings(ctx, guildData):
            signinMenu = self.bot.reactionMenus[guildData["lan_signin_menu_id"]]
            lanChannel = signinMenu.msg.channel
            myPerms = lanChannel.permissions_for(ctx.guild.me)
            if not myPerms.manage_permissions:
                await ctx.send(":x: I don't have permission to edit the permissions in <#" + lanChannel.id + ">!")
            elif not myPerms.manage_roles:
                await ctx.send(":x: I don't have permission to assign roles!\nPlease give me the 'manage roles' permission.")
            else:
                lanRole = ctx.guild.get_role(guildData["lan_role_id"])
                if lanRole.position >= ctx.guild.self_role.position:
                    await ctx.send(":x: I don't have permission to unassign the **" + lanRole.name + "** role!\n" \
                                    + "Please move it below my " + ctx.guild.self_role.name + " role.")
                else:
                    sharedRole = ctx.guild.get_role(guildData["shared_role_id"])
                    channelEdited = not lanChannel.overwrites_for(sharedRole).read_messages
                    usersEdited = len(lanRole.members)
                    loadingTxts = ["Closing channel... " + ("⏳" if channelEdited else "✅"),
                                    "Unassigning role" + ((" from " + str(usersEdited) + " users... ⏳") if usersEdited else "... ✅"),
                                    "Reseting signin menu... ⏳"]
                    loadingMsg = await ctx.send("\n".join(loadingTxts))

                    if channelEdited:
                        await lanChannel.set_permissions(sharedRole, read_messages=False,
                                                            reason=ctx.author.name + " used the " + self.bot.command_prefix + "close-lan command")
                        loadingTxts[0] = loadingTxts[0][:-1] + "✅"
                        asyncio.ensure_future(loadingMsg.edit(content="\n".join(loadingTxts)))
                    membersFutures = set()
                    for member in lanRole.members:
                        membersFutures.add(asyncio.ensure_future(member.remove_roles(lanRole, reason=ctx.author.name + " used the " + self.bot.command_prefix + "close-lan command")))
                    await signinMenu.msg.clear_reactions()
                    await signinMenu.updateMessage()
                    loadingTxts[2] = loadingTxts[2][:-1] + "✅"
                    await loadingMsg.edit(content="\n".join(loadingTxts))
                    if usersEdited:
                        asyncio.wait(membersFutures)
                        loadingTxts[1] = loadingTxts[1][:-1] + "✅"
                        await loadingMsg.edit(content="\n".join(loadingTxts))
                    await ctx.message.reply("Done!")


    @commands.command(name="set-lan-signin-menu", usage="set-lan-signin-menu <id>", help="Set the LAN signin menu to use with `open-lan` and `close-lan`.")
    @commands.has_permissions(administrator=True)
    async def admin_cmd_set_lan_signin_menu(self, ctx: Context, *, args: str):
        if not args:
            await ctx.send(":x: Please provide a menu ID to set!")
        else:
            if not lib.stringTyping.strIsInt(args):
                await ctx.send(":x: Invalid menu ID!\nTo get a menu ID, enable discord's developer mode, right click on the menu, and click 'copy ID'")
            else:
                menuID = int(args)
                if menuID not in self.bot.reactionMenus:
                    await ctx.send(":x: Unrecognised menu ID!")
                else:
                    db_gateway().update('guild_info', set_params={"lan_signin_menu_id": menuID}, where_params={"guild_id": ctx.guild.id})
                    await ctx.send("✅ The LAN signin menu is now: " + self.bot.reactionMenus[menuID].msg.jump_url)


    @commands.command(name="set-shared-role", usage="set-shared-role <role>",
                        help="Set the role to admit/deny into the LAN signin menu. This should NOT be the same as your LAN role. Role can be given as either a mention or an ID.")
    @commands.has_permissions(administrator=True)
    async def admin_cmd_set_shared_role(self, ctx: Context, *, args: str):
        if not args:
            await ctx.send(":x: Please provide a role to set!")
        else:
            if not (lib.stringTyping.strIsInt(args) or lib.stringTyping.strIsRoleMention(args)):
                await ctx.send(":x: Invalid role! Please give your role as either a mention or an ID.")
            else:
                roleID = int(args.lstrip("<&").rstrip(">"))
                role = ctx.guild.get_role(roleID)
                if role is None:
                    await ctx.send(":x: Unrecognised role!")
                else:
                    guildData = db_gateway().update('guild_info', set_params={"shared_role_id": roleID}, where_params={"guild_id": ctx.guild.id})
                    await ctx.send("✅ The shared role is now **" + role.name + "**.")


    @commands.command(name="set-lan-role", usage="set-lan-role <role>",
                        help="Set the role to remove during `close-lan`. This should NOT be the same as your shared role. Role can be given as either a mention or an ID.")
    @commands.has_permissions(administrator=True)
    async def admin_cmd_set_lan_role(self, ctx: Context, *, args: str):
        if not args:
            await ctx.send(":x: Please provide a role to set!")
        else:
            if not (lib.stringTyping.strIsInt(args) or lib.stringTyping.strIsRoleMention(args)):
                await ctx.send(":x: Invalid role! Please give your role as either a mention or an ID.")
            else:
                roleID = int(args.lstrip("<&").rstrip(">"))
                role = ctx.guild.get_role(roleID)
                if role is None:
                    await ctx.send(":x: Unrecognised role!")
                else:
                    db_gateway().update('guild_info', set_params={"lan_role_id": roleID}, where_params={"guild_id": ctx.guild.id})
                    await ctx.send("✅ The LAN role is now **" + role.name + "**.")


def setup(bot):
    bot.add_cog(AutoLANCog(bot))