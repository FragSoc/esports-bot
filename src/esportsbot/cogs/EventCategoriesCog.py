from asyncio import tasks
from discord.ext import commands
from discord.ext.commands.context import Context
from discord import PartialMessage, Forbidden, PermissionOverwrite, RawReactionActionEvent, Colour, Embed
from ..db_gateway import db_gateway
import asyncio
from .. import lib
from ..lib.client import EsportsBot
from ..reactionMenus.reactionRoleMenu import ReactionRoleMenu

CLOSED_EVENT_SIGNIN_CHANNEL_SHARED_PERMS = PermissionOverwrite(read_messages=False, read_message_history=True, add_reactions=False, send_messages=False, use_slash_commands=False)
OPEN_EVENT_SIGNIN_CHANNEL_SHARED_PERMS = PermissionOverwrite(read_messages=True, read_message_history=True, add_reactions=False, send_messages=False, use_slash_commands=False)
EVENT_CATEGORY_EVERYONE_PERMS = PermissionOverwrite(read_messages=False)
EVENT_CATEGORY_SHARED_ROLE_PERMS = PermissionOverwrite(read_messages=None)
EVENT_CATEGORY_EVENT_ROLE_PERMS = PermissionOverwrite(read_messages=True)
EVENT_SIGNIN_CHANNEL_EVENT_PERMS = PermissionOverwrite(read_messages=True, read_message_history=True, add_reactions=False, send_messages=False, use_slash_commands=False)


class EventCategoriesCog(commands.Cog):
    def __init__(self, bot: "EsportsBot"):
        self.bot: "EsportsBot" = bot


    async def getGuildEventSettings(self, ctx, eventName):
        db = db_gateway()
        guildData = db.get("guild_info", params={"guild_id": ctx.guild.id})[0]
        if not guildData["shared_role_id"]:
            await ctx.message.reply(f":x: No shared role has been set for this server! Use the `{self.bot.command_prefix}set-shared-role` command to set one.")
        else:
            eventData = db.get("event_categories", params={"guild_id": ctx.guild.id, "event_name": eventName})[0]
            if not eventData:
                if not (allEvents := db.get("event_categories", params={"guild_id": ctx.guild.id})):
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
                    await ctx.send(f":x: The {eventName.title()} signin channel is already open! <#{eventChannel.id!s}>")


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
                        loadingTxts = ["Closing channel... " + ("⏳" if channelEdited else "✅"),
                                        "Unassigning role" + ((" from " + str(usersEdited) + " users... ⏳") if usersEdited else "... ✅"),
                                        "Resetting signin menu... " + ("⏳" if menuReset else "✅")]
                        loadingMsg = await ctx.send("\n".join(loadingTxts))
                        adminActions = {"Event Closed": f"Event name: {eventName.title()}",
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
                    if not (allEvents := db.get("event_categoriesevent_channels", params={"guild_id": ctx.guild.id})):
                        await ctx.message.reply(":x: This server doesn't have any event categories registered!")
                    else:
                        await ctx.message.reply(":x: Unrecognised event. The following events exist in this server: " + ", ".join(e["event_name"].title() for e in allEvents))
                else:
                    menu = self.bot.reactionMenus[int(menuID)]
                    db.update('event_categories', set_params={"signin_menu_id": menu.msg.id}, where_params={"guild_id": ctx.guild.id, "event_name": eventName})
                    await ctx.send(f"✅ The {eventName.title()} event signin menu is now: {menu.msg.jump_url}")
                    await self.bot.adminLog(ctx.message, {"Event signin menu updated": f"Event name: {eventName.title()}\nMenu id: {menuID}\ntype: {type(menu).__name__}\n[Menu]({menu.msg.jump_url})"})


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
                        if not (allEvents := db.get("event_categories", params={"guild_id": ctx.guild.id})):
                            await ctx.message.reply(":x: This server doesn't have any event categories registered!")
                        else:
                            await ctx.message.reply(":x: Unrecognised event. The following events exist in this server: " + ", ".join(e["event_name"].title() for e in allEvents))
                    else:
                        db.update('event_categories', set_params={"role_id": roleID}, where_params={"guild_id": ctx.guild.id, "event_name": eventName})
                        await ctx.send(f"✅ The {eventName.title()} event role is now **{role.name}**.")
                        await self.bot.adminLog(ctx.message, {"Event role set": f"<@&{roleID!s}>"})


    @commands.command(name="register-event-category", usage="register-event-category <signin menu id> <role> <event name>",
                        help="Register an existing event category, menu, and role, for use with `open-event` and `close-event`. This does not setup permissions for the category or channels.")
    @commands.has_permissions(administrator=True)
    async def admin_cmd_register_event_category(self, ctx: Context, *, args: str):
        argsSplit = args.split(" ")
        if len(argsSplit < 3):
            await ctx.send(":x: Please provide a menu ID, followed by a role, and the name of your event!")
        else:
            menuIDStr = argsSplit[0]
            if not lib.stringTyping.strIsInt(menuIDStr):
                await ctx.send(":x: Invalid menu ID!\nTo get a menu ID, enable discord's developer mode, right click on the menu, and click 'copy ID'")
            elif int(menuIDStr) not in self.bot.reactionMenus:
                await ctx.send(f":x: Unrecognised menu ID: {menuIDStr}")
            else:
                roleStr = argsSplit[1]
                if not (lib.stringTyping.strIsInt(roleStr) or lib.stringTyping.strIsRoleMention(roleStr)):
                    await ctx.send(f":x: Invalid role: {roleStr} Please give your role as either a mention or an ID.")
                else:
                    roleID = int(roleStr.lstrip("<@&").rstrip(">"))
                    role = ctx.guild.get_role(roleID)
                    if role is None:
                        await ctx.send(":x: Unrecognised role!")
                    else:
                        eventName = args[len(roleStr)+len(menuIDStr)+2:].lower()
                        db = db_gateway()
                        if db.get("event_categories", {"guild_id": ctx.guild.id, "event_name": eventName}):
                            await ctx.message.reply(f":x: An event category with the name '{eventName.title()}' already exists!")
                        else:
                            menu = self.bot.reactionMenus[int(menuIDStr)]
                            db.insert('event_categories', set_params={"guild_id": ctx.guild.id, "event_name": eventName, "role_id": roleID, "signin_menu_id": menu.msg.id})
                            await ctx.send(f"✅ Event category '{eventName.title()}' registered successfuly!")
                            await self.bot.adminLog(ctx.message, {"Existing Event Category Registered": f"Event name: {eventName.title()}\nMenu id: {menuIDStr}\nRole: <@&{roleID!s}>\n[Menu]({menu.msg.jump_url})"})
                        
    
    @commands.command(name="create-event-category", usage="create-event-category <event name>",
                        help="Create a new event category with a signin channel and menu, event role, general channel and correct permissions, and automatically register them for use with `open-event` and `close-event`.")
    @commands.has_permissions(administrator=True)
    async def admin_cmd_create_event_category(self, ctx: Context, *, args: str):
        if not args:
            await ctx.send(":x: Please give name of your event!")
        else:
            db = db_gateway()
            eventName = args.lower()
            if db.get("event_categories", {"guild_id": ctx.guild.id, "event_name": eventName}):
                await ctx.message.reply(":x: An event with that name already exists!")
            else:
                guildData = db.get("guild_info", {"guild_id": ctx.guild.id})[0]
                if not guildData["shared_role_id"]:
                    await ctx.message.reply(f":x: This server does not have a **shared role** set. Please use the `{self.bot.command_prefix}set-shared-role` command to set one!")
                else:
                    if not (sharedRole := ctx.guild.get_role(guildData["shared_role_id"])):
                        await ctx.message.reply(f":x: I can't find the server's shared role! Was it deleted?\nPlease use the `{self.bot.command_prefix}set-shared-role` command to set a new one.")
                    else:
                        emojiSelectorMsg = await ctx.message.reply("Please react to this message within 60 seconds, with the emoji which you would like users to react with to receive the event role:")
                        def emojiSelectorCheck(data: RawReactionActionEvent) -> bool:
                            return data.message_id == emojiSelectorMsg.id and data.user_id == ctx.author.id and (data.emoji.is_unicode_emoji or self.bot.get_emoji(data.emoji.id))
                        
                        try:
                            signinEmoji = lib.emotes.Emote.fromPartial((await self.bot.wait_for("raw_reaction_add", check=emojiSelectorCheck, timeout=60)).emoji, rejectInvalid=True)
                        except asyncio.TimeoutError:
                            await emojiSelectorMsg.reply("Out of time, please try the command again.")
                        except lib.exceptions.UnrecognisedCustomEmoji:
                            await emojiSelectorMsg.reply("An error occurred when loading your reaction, please try the command again with a different emoji.")
                        else:
                            creationReason = f"Creating new event category '{eventName}' requested via {self.bot.command_prefix}create-event-category command"
                            eventRole = await ctx.guild.create_role(name=eventName.title(), reason=creationReason)
                            categoryOverwrites = {sharedRole: EVENT_CATEGORY_SHARED_ROLE_PERMS, eventRole: EVENT_CATEGORY_EVENT_ROLE_PERMS}
                            signinOverwrites = {sharedRole: CLOSED_EVENT_SIGNIN_CHANNEL_SHARED_PERMS, eventRole: EVENT_SIGNIN_CHANNEL_EVENT_PERMS}
                            if eventRole != ctx.guild.default_role:
                                categoryOverwrites[ctx.guild.default_role] = EVENT_CATEGORY_EVERYONE_PERMS
                                signinOverwrites[ctx.guild.default_role] = EVENT_CATEGORY_EVERYONE_PERMS
                            newCategory = await ctx.guild.create_category(eventName.title(), reason=creationReason, overwrites=categoryOverwrites)
                            signinChannel = await ctx.guild.create_text_channel(f"{eventName}-signin", reason=creationReason, category=newCategory, overwrites=signinOverwrites)
                            eventGeneral = await ctx.guild.create_text_channel(f"{eventName}-general", reason=creationReason, category=newCategory, overwrites=categoryOverwrites)
                            eventVoice = await ctx.guild.create_voice_channel(f"{eventName}-voice", reason=creationReason, category=newCategory, overwrites=categoryOverwrites)
                            signinMenuMsg = await signinChannel.send(embed=Embed())
                            signinMenu = ReactionRoleMenu(signinMenuMsg, self.bot, {signinEmoji: eventRole}, col=Colour.blue(), titleTxt=f"Sign Into {eventName.title()}",
                                                            desc=f"If you're attending this event, react to this message to get the '{eventRole.name}' role, and access to secret event channels!")
                            await signinMenu.updateMessage()
                            self.bot.reactionMenus.add(signinMenu)
                            db.insert('event_categories', {"guild_id": ctx.guild.id, "event_name": eventName, "role_id": eventRole.id, "signin_menu_id": signinMenuMsg.id})
                            await ctx.send(f"✅ New event category '{eventName.title()}' created successfuly!\n" \
                                            + f"The event role is {eventRole.mention}, and the signin menu is ID `{signinMenuMsg.id!s}`, in {signinChannel.mention}.\n\n" \
                                            + f"The event is currently **closed**, and invisible to your shared role, `{sharedRole.name}`. Open the event when you're ready with `{self.bot.command_prefix}open-event {eventName}`!\n" \
                                            + "Feel free to customise the category, channels and roles, but do not synchronise the category permissions.\n\n" \
                                            + "You can create a new channel in the category with the correct permissions by either:\n" \
                                                + "- Using the `+` icon next to the category,\n" \
                                                + "- Dragging your channel into the category and synchronising **just that channel**'s permissions with the category, or\n" \
                                                + f"- Duplicating {eventGeneral.mention}.")
                            await self.bot.adminLog(ctx.message, {"New Event Category Created": f"Event name: {eventName.title()}\nMenu id: {signinMenuMsg.id!s}\nRole: <@&{eventRole.id!s}>\n[Menu]({signinMenuMsg.jump_url})"})


    @commands.command(name="unregister-event-category", usage="unregister-event-category <event name>",
                        help="Unregister an event category and role so that it can no longer be used with `open-event` and `close-event`, but without deleting the channels.")
    @commands.has_permissions(administrator=True)
    async def admin_cmd_unregister_event_category(self, ctx: Context, *, args: str):
        if not args:
            await ctx.send(":x: Please give name of your event!")
        else:
            db = db_gateway()
            eventName = args.lower()
            if not db.get("event_categories", {"guild_id": ctx.guild.id, "event_name": eventName}):
                if not (allEvents := db.get("event_categories", params={"guild_id": ctx.guild.id})):
                    await ctx.message.reply(":x: This server doesn't have any event categories registered!")
                else:
                    await ctx.message.reply(":x: Unrecognised event. The following events exist in this server: " + ", ".join(e["event_name"].title() for e in allEvents))
            else:
                db.delete("event_categories", {"guild_id": ctx.guild.id, "event_name": eventName})
                await ctx.message.reply(f"✅ {eventName.title()} event category successfuly unregistered.")
                await self.bot.adminLog(ctx.message, {"Event Category Unregistered": f"Event name: {eventName.title()}\nCategory/channels left undeleted."})
    

    @commands.command(name="delete-event-category", usage="delete-event-category <event name>",
                        help="Delete an event category and its role and channels from the server.")
    @commands.has_permissions(administrator=True)
    async def admin_cmd_delete_event_category(self, ctx: Context, *, args: str):
        if not args:
            await ctx.send(":x: Please give name of your event!")
        else:
            db = db_gateway()
            eventName = args.lower()
            if not (eventData := db.get("event_categories", {"guild_id": ctx.guild.id, "event_name": eventName})):
                if not (allEvents := db.get("event_categories", params={"guild_id": ctx.guild.id})):
                    await ctx.message.reply(":x: This server doesn't have any event categories registered!")
                else:
                    await ctx.message.reply(":x: Unrecognised event. The following events exist in this server: " + ", ".join(e["event_name"].title() for e in allEvents))
            else:
                signinMenuID = eventData[0]["signin_menu_id"]
                eventCategory = self.bot.reactionMenus[signinMenuID].msg.channel.category
                numChannels = len(eventCategory.channels)
                eventRole = ctx.guild.get_role(eventData[0]["role_id"])
                confirmMsg = await ctx.message.reply(f"React within 60 seconds: Are you sure you want to delete the '{eventName}' category" + (f", the {eventRole.name} role," if eventRole else "") + f" and the {numChannels!s} event channels?")
                asyncio.create_task(confirmMsg.add_reaction('👍'))
                asyncio.create_task(confirmMsg.add_reaction('👎'))
                def confirmCheck(data: RawReactionActionEvent) -> bool:
                    return data.message_id == confirmMsg.id and data.user_id == ctx.author.id and (data.emoji.is_unicode_emoji and data.emoji.name in ['👍', '👎'])

                try:
                    confirmResult = (await self.bot.wait_for("raw_reaction_add", check=confirmCheck, timeout=60)).emoji
                except asyncio.TimeoutError:
                    await confirmMsg.reply("Out of time, please try the command again.")
                else:
                    if confirmResult.name == "👎":
                        await ctx.send("Event category deletion cancelled.")
                    else:
                        deletionReason = f"Event category '{eventName}' deletion requested via {self.bot.command_prefix}delete-event-category command"
                        self.bot.reactionMenus.removeID(signinMenuID)
                        deletionTasks = set()
                        if eventRole:
                            deletionTasks.add(asyncio.create_task(eventRole.delete(reason=deletionReason)))
                        for currentCategory in eventCategory.channels:
                            deletionTasks.add(asyncio.create_task(currentCategory.delete(reason=deletionReason)))
                        deletionTasks.add(asyncio.create_task(eventCategory.delete(reason=deletionReason)))
                        await asyncio.wait(deletionTasks)
                        db.delete("event_categories", {"guild_id": ctx.guild.id, "event_name": eventName})
                        await ctx.message.reply(f"✅ {eventName.title()} event category and role successfuly deleted.")
                        await self.bot.adminLog(ctx.message, {"Event Category Deleted": f"Event name: {eventName.title()}\nChannels deleted: {numChannels!s}" + (f"\nRole deleted: #{eventData[0]['role_id']!s}" if eventData[0]['role_id'] else "")})


def setup(bot):
    bot.add_cog(EventCategoriesCog(bot))
    