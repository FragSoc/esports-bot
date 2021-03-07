from discord.ext import commands
from discord.ext.commands.context import Context
from ..db_gateway import db_gateway
from .. import lib
from ..lib.client import EsportsBot
from ..reactionMenus import reactionRoleMenu


class MenusCog(commands.Cog):
    def __init__(self, bot: "EsportsBot"):
        self.bot: "EsportsBot" = bot

    
    @commands.command(name="del-menu", usage="del-menu <id>", help="Remove the specified reaction menu. You can also just delete the message, if you have permissions.\nTo get the ID of a reaction menu, enable discord's developer mode, right click on the menu, and click Copy ID.")
    @commands.has_permissions(administrator=True)
    async def admin_cmd_del_reaction_menu(self, ctx: Context, *, args: str):
        """Unregister the specified reaction menu for interactions and delete the containing message.
        This works regardless of the type of reaction menu.
        """
        msgID = int(args)
        if msgID in self.bot.reactionMenus:
            menu = self.bot.reactionMenus[msgID]
            menuTypeName = type(menu).__name__
            await self.bot.reactionMenus[msgID].delete()
            try:
                self.bot.reactionMenus.removeID(msgID)
            except KeyError:
                pass
            await ctx.send("✅ Menu deleted!")
            await self.bot.adminLog(ctx.message, {"Reaction menu deleted": "id: " + str(msgID) \
                                                    + "\nchannel: <#" + str(menu.msg.channel.id) + ">" \
                                                    + "\ntype: " + menuTypeName})
        else:
            await ctx.send(":x: Unrecognised reaction menu!")

    
    @commands.command(name="del-role-menu-option", usage="del-role-menu-option <menu-id> <emoji>", help="Remove a role from a role menu.\nTo get the ID of a reaction menu, enable discord's developer mode, right click on the menu, and click Copy ID.\nYour emoji must be an option in the menu.")
    @commands.has_permissions(administrator=True)
    async def admin_cmd_remove_role_menu_option(self, ctx: Context, *, args: str):
        """Remove an option from a reaction role menu, by its emoji.
        """
        argsSplit = args.split(" ")
        if len(argsSplit) < 2:
            await ctx.send(":x: Please provide a menu ID and an emoji!")
        elif not lib.stringTyping.strIsInt(argsSplit[0]):
            await ctx.send(":x: Invalid menu ID - please give a number!")
        elif int(argsSplit[0]) not in self.bot.reactionMenus:
            await ctx.send(":x: Unknown role menu ID!")
        else:
            menu = self.bot.reactionMenus[int(argsSplit[0])]
            try:
                roleEmoji = lib.emotes.Emote.fromStr(argsSplit[1], rejectInvalid=True)
            except lib.exceptions.UnrecognisedCustomEmoji:
                await ctx.send(":x: I don't know that emoji!\nYou can only use built in emojis, or custom emojis that are in this server.")
            else:
                if not menu.hasEmojiRegistered(roleEmoji):
                    await ctx.send(":x: That emoji is not in the menu!")
                else:
                    optionRole = menu.options[roleEmoji].role
                    adminActions = {"Reaction menu option removed": "id: " + str(menu.msg.id) + "\ntype: " + type(menu).__name__ + "\nOption: " + roleEmoji.sendable + " <@&" + str(optionRole.id) + ">\n[Menu](" + menu.msg.jump_url + ")"}
                    if len(menu.options) == 1:
                        await menu.delete()
                        await ctx.send("The menu has no more options! Menu deleted.")
                        adminActions["Reaction menu deleted (last option removed)"] = "id: " + str(menu.msg.id) \
                                                                                        + "\nchannel: <#" + str(menu.msg.channel.id) + ">" \
                                                                                        + "\ntype: " + type(menu).__name__
                    else:
                        del menu.options[roleEmoji]
                        await menu.msg.remove_reaction(roleEmoji.sendable, ctx.guild.me)
                        await menu.updateMessage(noRefreshOptions=True)
                        self.bot.reactionMenus.updateDB(menu)
                        await ctx.send("✅ Removed option " + roleEmoji.sendable + " from menu " + str(menu.msg.id) + "!")
                    await self.bot.adminLog(ctx.message, adminActions)

    
    @commands.command(name="add-role-menu-option", usage="add-role-menu-option <menu-id> <emoji> <@role mention>", help="Add a role to a role menu.\nTo get the ID of a reaction menu, enable discord's developer mode, right click on the menu, and click Copy ID.\nYour emoji must not be in the menu already.\nGive your role to grant/remove as a mention.")
    @commands.has_permissions(administrator=True)
    async def admin_cmd_add_role_menu_option(self, ctx: Context, *, args: str):
        """Add a new option to a reaction role menu, by its emoji and role to grant/remove.
        """
        argsSplit = args.split(" ")
        if len(argsSplit) < 3:
            await ctx.send(":x: Please provide a menu ID, an emoji, and a role mention!")
        elif not lib.stringTyping.strIsInt(argsSplit[0]):
            await ctx.send(":x: Invalid menu ID - please give a number!")
        elif int(argsSplit[0]) not in self.bot.reactionMenus:
            await ctx.send(":x: Unknown role menu ID!")
        elif not lib.stringTyping.strIsRoleMention(argsSplit[2]):
            await ctx.send(":x: Invalid role mention!")
        else:
            menu = self.bot.reactionMenus[int(argsSplit[0])]
            try:
                roleEmoji = lib.emotes.Emote.fromStr(argsSplit[1], rejectInvalid=True)
            except lib.exceptions.UnrecognisedCustomEmoji:
                await ctx.send(":x: I don't know that emoji!\nYou can only use built in emojis, or custom emojis that are in this server.")
            except TypeError:
                await ctx.send(":x: Invalid emoji: " + argsSplit[1])
            else:
                role = ctx.guild.get_role(int(argsSplit[2].lstrip("<@&").rstrip(">")))
                if role is None:
                    await ctx.send(":x: Unrecognised role!")
                elif menu.hasEmojiRegistered(roleEmoji):
                    await ctx.send(":x: That emoji is already being used for another role!")
                elif len(menu.options) == 20:
                    await ctx.send(":x: That menu already has the maximum of 20 options!")
                else:
                    menu.options[roleEmoji] = reactionRoleMenu.ReactionRoleMenuOption(roleEmoji, role, menu)
                    await menu.msg.add_reaction(roleEmoji.sendable)
                    await menu.updateMessage(noRefreshOptions=True)
                    self.bot.reactionMenus.updateDB(menu)
                    await ctx.send("✅ Added option " + roleEmoji.sendable + " to menu " + str(menu.msg.id) + "!")
                    await self.bot.adminLog(ctx.message, {"Reaction menu option added": "id: " + str(menu.msg.id) \
                                                                                        + "\ntype: " + type(menu).__name__ \
                                                                                        + "\nOption: " + roleEmoji.sendable + " <@&" + str(role.id)  \
                                                                                        + ">\n[Menu](" + menu.msg.jump_url + ")"})
        


    @commands.command(name="make-role-menu", usage="make-role-menu <title>\n<option1 emoji> <@option1 role>\n...    ...", help="Create a reaction role menu. Each option must be on its own new line, as an emoji, followed by a space, followed by a mention of the role to grant. The `title` is displayed at the top of the meny and is optional, to exclude your title simply give a new line.")
    @commands.has_permissions(administrator=True)
    async def admin_cmd_make_role_menu(self, ctx: Context, *, args: str):
        """Create a reaction role menu, allowing users to self-assign or remove roles by adding and removing reactions.
        Option reactions must be either unicode, or custom to the server where the menu is being created.

        args must contain a menu subject and new line, followed by a newline-separated list of emoji-option pairs, where each pair is separated with a space.
        For example: 'Number Roles\n0️⃣ @Role-1\n1️⃣ @Role-2\n2️⃣ @Role-3' will produce three options:
        - Toggling the 0️⃣ reaction will toggle user ownership of @Role-1
        - Toggling the 1️⃣ reaction will toggle user ownership of @Role-2
        - Toggling the 2️⃣ reaction will toggle user ownership of @Role-3
        Where the subject of the menu is 'Number Roles'.
        The menu subject is optional. To not provide a subject, simply start args with a new line.

        TODO: Support role IDs
        TODO: Implement single choice/grouped roles
        """
        if ctx.guild.self_role is None:
            await ctx.send(":x: I can't find my '" + ctx.guild.me.name + "' role! Have you removed it?")
            return
        botRole = ctx.guild.self_role

        reactionRoles = {}
        kwArgs = {}

        argsSplit = args.split("\n")
        if len(argsSplit) < 2:
            await ctx.send(":x: Invalid arguments! Please provide your menu title, followed by a new line, then a new line-separated series of options.\nFor more info, see `" + self.bot.command_prefix + "admin-help`")
            return
        menuSubject = argsSplit[0]
        argPos = 0

        for arg in argsSplit[1:]:
            if arg == "":
                continue
            argPos += 1
            try:
                roleStr, dumbReact = arg.strip(" ").split(" ")[1], lib.emotes.Emote.fromStr(arg.strip(" ").split(" ")[0], rejectInvalid=False)
            except (ValueError, IndexError):
                for kwArg in ["target=", "days=", "hours=", "seconds=", "minutes=", "multiplechoice="]:
                    if arg.lower().startswith(kwArg):
                        kwArgs[kwArg[:-1]] = arg[len(kwArg):]
                        break
            except lib.exceptions.InvalidStringEmoji as e:
                await ctx.send(":x: Invalid emoji: " + e.val)
                return
            except lib.exceptions.UnrecognisedCustomEmoji:
                await ctx.send(":x: I don't know your " + str(argPos) + lib.stringTyping.getNumExtension(argPos) + " emoji!\nYou can only use built in emojis, or custom emojis that are in this server.")
                return
            else:
                if dumbReact.sendable == "None":
                    await ctx.send(":x: I don't know your " + str(argPos) + lib.stringTyping.getNumExtension(argPos) + " emoji!\nYou can only use built in emojis, or custom emojis that are in this server.")
                    return
                if dumbReact is None:
                    await ctx.send(":x: Invalid emoji: " + arg.strip(" ").split(" ")[0])
                    return
                elif dumbReact.isID:
                    localEmoji = False
                    for localEmoji in ctx.guild.emojis:
                        if localEmoji.id == dumbReact.id:
                            localEmoji = True
                            break
                    if not localEmoji:
                        await ctx.send(":x: I don't know your " + str(argPos) + lib.stringTyping.getNumExtension(argPos) + " emoji!\nYou can only use built in emojis, or custom emojis that are in this server.")
                        return

                if dumbReact in reactionRoles:
                    await ctx.send(":x: Cannot use the same emoji for two options!")
                    return

                if lib.stringTyping.strIsRoleMention(roleStr):
                    roleID = int(roleStr.lstrip("<@&").rstrip(">"))
                elif lib.stringTyping.strIsInt(roleStr):
                    roleID = int(roleStr)
                else:
                    await ctx.send(":x: Invalid role given for emoji " + dumbReact.sendable + "!")
                    return

                role = ctx.guild.get_role(roleID)
                if role is None:
                    await ctx.send(":x: Unrecognised role: " + roleStr)
                    return
                elif role.position >= botRole.position:
                    await ctx.send(":x: I can't grant the **" + role.name + "** role!\nMake sure it's below my '" + botRole.name + "' role in the server roles list.")
                    return
                elif role.is_bot_managed():
                    await ctx.send(":x: I can't grant the **" + role.name + "** role!\nThis role is managed by a bot.")
                    return
                elif role.is_integration():
                    await ctx.send(":x: I can't grant the **" + role.name + "** role!\nThis role is managed by an integration.")
                    return
                reactionRoles[dumbReact] = role

        if len(reactionRoles) == 0:
            await ctx.send(":x: No roles given!")
            return
        elif len(reactionRoles) > 20:
            await ctx.send(":x: Menus can only contain a maximum of 20 options!")
            return

        targetRole = None
        if "target" in kwArgs:
            if lib.stringTyping.strIsRoleMention(kwArgs["target"]):
                targetRole = ctx.guild.get_role(int(kwArgs["target"].lstrip("<@&").rstrip(">")))
                if targetRole is None:
                    await ctx.send(":x: Unknown target role!")
                    return

            else:
                await ctx.send(":x: Invalid target role!")
                return

        menuMsg = await ctx.send("‎")

        menu = reactionRoleMenu.ReactionRoleMenu(menuMsg, self.bot, reactionRoles, targetRole=targetRole, titleTxt=menuSubject)
        await menu.updateMessage()
        self.bot.reactionMenus.add(menu)
        await ctx.send("Role menu " + str(menuMsg.id) + " has been created!")
        try:
            await self.bot.adminLog(ctx.message, {"Reaction Role Menu Created": "id: " + str(menu.msg.id) + "\ntype: " + type(menu).__name__ + "\n" + str(len(reactionRoles)) + " Options: " + "".join(e.sendable for e in reactionRoles) + "\n[Menu](" + menu.msg.jump_url + ")"})
        except Exception as e:
            print(e)
            raise e


def setup(bot):
    bot.add_cog(MenusCog(bot))