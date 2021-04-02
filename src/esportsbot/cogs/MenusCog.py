from discord.ext import commands
from discord.ext.commands.context import Context
from ..db_gateway import db_gateway
from .. import lib
from ..lib.client import EsportsBot
from ..reactionMenus import reactionRoleMenu, reactionPollMenu
from datetime import timedelta
import traceback


MAX_POLLS_PER_GUILD = 5
MAX_POLL_TIMEOUT = timedelta(days=31)
DEFAULT_POLL_TIMEOUT = timedelta(minutes=5)


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
            menuTypeName = type(self.bot.reactionMenus[msgID]).__name__
            await self.bot.reactionMenus[msgID].delete()
            try:
                self.bot.reactionMenus.removeID(msgID)
            except KeyError:
                pass
            await ctx.send("✅ Menu deleted!")
            await self.bot.adminLog(ctx.message, {"Reaction menu deleted": "id: " + str(msgID) + "\ntype: " + menuTypeName})
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
            except lib.exceptions.UnrecognisedEmoji:
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
                        adminActions["Reaction menu deleted (last option removed)"] = "id: " + str(menu.msg.id) + "\ntype: " + type(menu).__name__
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
            except lib.exceptions.UnrecognisedEmoji:
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
                    await self.bot.adminLog(ctx.message, {"Reaction menu option added": "id: " + str(menu.msg.id) + "\ntype: " + type(menu).__name__ + "\nOption: " + roleEmoji.sendable + " <@&" + str(role.id) + ">\n[Menu](" + menu.msg.jump_url + ")"})
        


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
            # except lib.emojis.UnrecognisedCustomEmoji:
                # await message.channel.send(":x: I don't know your " + str(argPos) + lib.stringTyping.getNumExtension(argPos) + " emoji!\nYou can only use built in emojis, or custom emojis that are in this server.")
                # return
            else:
                if dumbReact.sendable == "None":
                    await ctx.send(":x: I don't know your " + str(argPos) + lib.stringTyping.getNumExtension(argPos) + " emoji!\nYou can only use built in emojis, or custom emojis that are in this server.")
                    return
                if dumbReact is None:
                    await ctx.send(":x: Invalid emoji: " + arg.strip(" ").split(" ")[1])
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
                    await ctx.send(":x: Invalid role given for option " + dumbReact.sendable + "!")
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

    
    @commands.command(name="poll", usage="poll <subject>\n<option1 emoji> <option1 name>\n...    ...\n<optional args>", help="Start a reaction-based poll. Each option must be on its own new line, as an emoji, followed by a space, followed by the option name. The `subject` is the question that users answer in the poll and is optional, to exclude your subject simply give a new line.\n\n__Optional Arguments__\nOptional arguments should be given by `name=value`, with each arg on a new line.\n- Give `multiplechoice=no` to only allow one vote per person (default: yes).\n- Give the length of the poll, with each time division on a new line. Acceptable time divisions are: `seconds`, `minutes`, `hours`, `days`. (default: minutes=5)")
    async def cmd_poll(self, ctx: Context, *, args: str):
        """Run a reaction-based poll, allowing users to choose between several named options.
        Users may not create more than one poll at a time, anywhere.
        Option reactions must be either unicode, or custom to the server where the poll is being created.

        args must contain a poll subject (question) and new line, followed by a newline-separated list of emoji-option pairs, where each pair is separated with a space.
        For example: 'Which one?\n0️⃣ option a\n1️⃣ my second option\n2️⃣ three' will produce three options:
        - 'option a'         which participants vote for by adding the 0️⃣ reaction
        - 'my second option' which participants vote for by adding the 1️⃣ reaction
        - 'three'            which participants vote for by adding the 2️⃣ reaction
        and the subject of the poll is 'Which one?'
        The poll subject is optional. To not provide a subject, simply begin args with a new line.

        args may also optionally contain the following keyword arguments, given as argname=value
        - multiplechoice : Whether or not to allow participants to vote for multiple poll options. Must be true or false.
        - days           : The number of days that the poll should run for. Must be at least one, or unspecified.
        - hours          : The number of hours that the poll should run for. Must be at least one, or unspecified.
        - minutes        : The number of minutes that the poll should run for. Must be at least one, or unspecified.
        - seconds        : The number of seconds that the poll should run for. Must be at least one, or unspecified.
        """
        currentPollsNum = db_gateway().get('guild_info', params={'guild_id': ctx.author.guild.id})[0]['num_running_polls'] - 1
        if currentPollsNum >= MAX_POLLS_PER_GUILD:
            await ctx.message.reply("This server already has " + str(currentPollsNum) \
                                    + " polls running! Please wait for one to finish before starting another.")
            return

        pollOptions = {}
        kwArgs = {}

        argsSplit = args.split("\n")
        if len(argsSplit) < 2:
            await ctx.message.reply(":x: Invalid arguments! Please provide your poll subject, followed by a new line, " \
                                    + "then a new line-separated series of poll options.\nFor more info, see `" \
                                    + self.bot.command_prefix + "help poll`")
            return
        pollSubject = argsSplit[0]
        argPos = 0
        for arg in argsSplit[1:]:
            if arg == "":
                continue
            arg = arg.strip()
            argSplit = arg.split(" ")
            argPos += 1
            try:
                optionName, dumbReact = arg[arg.index(" ")+1:], lib.emotes.Emote.fromStr(argSplit[0], rejectInvalid=True)
            except (ValueError, IndexError):
                for kwArg in ["days=", "hours=", "seconds=", "minutes=", "multiplechoice="]:
                    if arg.lower().startswith(kwArg):
                        kwArgs[kwArg[:-1]] = arg[len(kwArg):]
                        break
            except lib.exceptions.UnrecognisedEmoji:
                await ctx.message.reply(":x: I don't know your " + str(argPos) + lib.stringTyping.getNumExtension(argPos) \
                                        + " emoji!\nYou can only use built in emojis, or custom emojis that are in this server.")
                return
            else:
                if dumbReact.sendable == "None":
                    await ctx.message.reply(":x: I don't know your " + str(argPos) + lib.stringTyping.getNumExtension(argPos) \
                                                + " emoji!\nYou can only use built in emojis, or custom emojis that are in this server.")
                    return
                if dumbReact is None:
                    await ctx.message.reply(":x: Invalid emoji: " + argSplit[1])
                    return
                elif dumbReact.isID:
                    localEmoji = False
                    for localEmoji in ctx.guild.emojis:
                        if localEmoji.id == dumbReact.id:
                            localEmoji = True
                            break
                    if not localEmoji:
                        await ctx.message.reply(":x: I don't know your " + str(argPos) + lib.stringTyping.getNumExtension(argPos) \
                                                + " emoji!\nYou can only use built in emojis, or custom emojis that are in this server.")
                        return

                if dumbReact in pollOptions:
                    await ctx.message.reply(":x: Cannot use the same emoji for two options!")
                    return

                pollOptions[dumbReact] = optionName

        if len(pollOptions) == 0:
            await ctx.message.reply(":x: You need to give some options to vote on!\nFor more info, see `" \
                                    + self.bot.command_prefix + "help poll`")
            return
        
        timeoutDict = {}

        for timeName in ["days", "hours", "minutes", "seconds"]:
            if timeName in kwArgs:
                if not lib.stringTyping.strIsInt(kwArgs[timeName]) or int(kwArgs[timeName]) < 1:
                    await ctx.message.reply(":x: Invalid number of " + timeName + " before timeout!")
                    return

                timeoutDict[timeName] = int(kwArgs[timeName])

        multipleChoice = True
        if "multiplechoice" in kwArgs:
            if kwArgs["multiplechoice"].lower() in ["off", "no", "false", "single", "one"]:
                multipleChoice = False
            elif kwArgs["multiplechoice"].lower() not in ["on", "yes", "true", "multiple", "many"]:
                await ctx.message.reply("Invalid `multiplechoice` setting: '" + kwArgs["multiplechoice"] \
                                        + "'\nPlease use either `multiplechoice=yes` or `multiplechoice=no`")
                return

        timeoutTD = lib.timeUtil.timeDeltaFromDict(timeoutDict if timeoutDict else DEFAULT_POLL_TIMEOUT)
        if timeoutTD > MAX_POLL_TIMEOUT:
            await ctx.message.reply(":x: Invalid poll length! The maximum poll lenght is **" \
                                    + lib.timeUtil.td_format_noYM(MAX_POLL_TIMEOUT) + ".**")
            return

        menuMsg = await ctx.send("‎")

        menu = reactionPollMenu.InlineReactionPollMenu(menuMsg, pollOptions, timeoutTD.total_seconds(),
                                                        pollStarter=ctx.author, multipleChoice=multipleChoice,
                                                        desc=pollSubject, footerTxt="This poll will end in " \
                                                            + lib.timeUtil.td_format_noYM(timeoutTD) + ".")

        # Update guild polls counter
        runningPolls = db_gateway().get("guild_info", {"guild_id": ctx.guild.id})[0]["num_running_polls"]
        db_gateway().update("guild_info", {"num_running_polls": runningPolls + 1}, {"guild_id": ctx.guild.id})

        await menu.doMenu()

        # Allow the creation of another poll
        runningPolls = db_gateway().get("guild_info", {"guild_id": ctx.guild.id})[0]["num_running_polls"]
        db_gateway().update("guild_info", {"num_running_polls": runningPolls - 1}, {"guild_id": ctx.guild.id})

        await reactionPollMenu.showPollResults(menu)


def setup(bot):
    bot.add_cog(MenusCog(bot))