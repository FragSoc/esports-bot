from asyncio import tasks
from typing import Tuple
from discord.ext import commands
from discord.ext.commands.context import Context
from discord import PartialMessage, Forbidden, PermissionOverwrite, RawReactionActionEvent, Colour, Embed
from ..db_gateway import db_gateway
import asyncio
from .. import lib
from ..lib.client import EsportsBot, StringTable
from ..reactionMenus.reactionRoleMenu import ReactionRoleMenu, ReactionRoleMenuOption

# Permissions overrides assigned to the shared role in closed event signin channels
CLOSED_EVENT_SIGNIN_CHANNEL_SHARED_PERMS = PermissionOverwrite(
    read_messages=False,
    read_message_history=True,
    add_reactions=False,
    send_messages=False,
    use_slash_commands=False
)
# Permissions overrides assigned to the shared role in open event signin channels
OPEN_EVENT_SIGNIN_CHANNEL_SHARED_PERMS = PermissionOverwrite(
    read_messages=True,
    read_message_history=True,
    add_reactions=False,
    send_messages=False,
    use_slash_commands=False
)
# Permissions overrides assigned to @everyone in all event category channels
EVENT_CATEGORY_EVERYONE_PERMS = PermissionOverwrite(read_messages=False)
# Permissions overrides assigned to the shared role in all event category channels
EVENT_CATEGORY_SHARED_ROLE_PERMS = PermissionOverwrite(read_messages=None)
# Permissions overrides assigned to the event role in all event category channels
EVENT_CATEGORY_EVENT_ROLE_PERMS = PermissionOverwrite(read_messages=True)
# Permissions overrides assigned to the event role in event signin channels
EVENT_SIGNIN_CHANNEL_EVENT_PERMS = PermissionOverwrite(
    read_messages=True,
    read_message_history=True,
    add_reactions=False,
    send_messages=False,
    use_slash_commands=False
)


class EventCategoriesCog(commands.Cog):
    """Cog implementing channel categories for events.
    Event categories remain invisible until the event is "opened", at which point only a "signin" channel is revealed.
    Users who "sign into" the event with a menu in this channel receive an event-specific role, and can then see all
    other channels in the category.
    When the event is "closed", the category becomes invisible again to all users, and the event role is
    removed from all users.

    .. codeauthor:: Trimatix

    :var bot: The client instance owning this cog instance
    :vartype bot: EsportsBot
    """
    def __init__(self, bot: "EsportsBot"):
        """
        :param EsportsBot bot: The client instance owning this cog instance
        """
        self.bot: "EsportsBot" = bot
        self.STRINGS = bot.STRINGS["event_categories"]

    async def getGuildEventSettings(self, ctx: Context, eventName: str) -> Tuple[dict, dict]:
        """User-facing function which fetches the configuration for the named event and the owning guild from the database.
        If an event category with the given name belonging to the calling guild can be found, the database-stored
        guild and event configurations (dictionaries) are returned in a tuple: (guild_data, event_data)

        If the guild does not have a shared role set, or an event with the given name cannot be found, a message is sent
        to the given context indicating as such, and an empty tuple is returned: ()

        :param Context ctx: A context summarising the command message which triggered the calling of this function
        :param str eventName: The name of the event to look up
        :return: A tuple with the guild and event db entries if the guild has a shared role and an event named eventName, () otherwise
        :rtype: Tuple[dict, dict] if the guild has a shared role and an event named eventName, Tuple[] otherwise
        """
        db = db_gateway()
        guildData = db.get("guild_info", params={"guild_id": ctx.guild.id})[0]
        if not guildData["shared_role_id"]:
            await ctx.message.reply(self.STRINGS['no_shared_role'].format(command_prefix=self.bot.command_prefix))
        else:
            eventData = db.get("event_categories", params={"guild_id": ctx.guild.id, "event_name": eventName})[0]
            if not eventData:
                if not (allEvents := db.get("event_categories", params={"guild_id": ctx.guild.id})):
                    await ctx.message.reply(self.STRINGS['no_event_categories'])
                else:
                    await ctx.message.reply(
                        self.STRINGS['unrecognised_event'].format(
                            events=", ".join(e["event_name"].title() for e in allEvents)
                        )
                    )
            else:
                return (guildData, eventData)
        return ()

    @commands.command(
        name="open-event",
        usage="open-event <event name>",
        help="Reveal the signin channel for the named event channel."
    )
    @commands.has_permissions(administrator=True)
    async def admin_cmd_open_event(self, ctx: Context, *, args):
        """Admin command: Open the named event category, revealing the signin channel to all users.

        :param Context ctx: A context summarising the message which called this command
        :param str args: a string containing the name of the event to open
        """
        if not args:
            await ctx.message.reply(self.STRINGS['request_event_name'])
        elif allData := await self.getGuildEventSettings(ctx, args.lower()):
            guildData, eventData = allData
            eventName = args.lower()
            signinMenu = self.bot.reactionMenus[eventData["signin_menu_id"]]
            eventChannel = signinMenu.msg.channel
            if not eventChannel.permissions_for(ctx.guild.me).manage_permissions:
                await ctx.send(self.STRINGS['no_channel_edit_perms'].format(channel_id=eventChannel.id))
            else:
                sharedRole = ctx.guild.get_role(guildData["shared_role_id"])
                if not eventChannel.overwrites_for(sharedRole).read_messages:
                    reason = self.STRINGS['event_channel_open_reason'].format(
                        author=ctx.author.name,
                        event_name=eventName,
                        command_prefix=self.bot.command_prefix
                    )
                    await eventChannel.set_permissions(sharedRole, read_messages=True, reason=reason)
                    await ctx.send(
                        self.STRINGS['success_channel'].format(channel_id=eventChannel.id,
                                                               role_name=sharedRole.name)
                    )
                    admin_message = self.STRINGS['admin_signin_visible'][1].format(channel_id=eventChannel.id)
                    await self.bot.adminLog(ctx.message, {self.STRINGS['admin_signin_visible'][0]: admin_message})
                else:
                    await ctx.send(
                        self.STRINGS['channel_already_open'].format(event_name=eventName.title(),
                                                                    channel_id=eventChannel.id)
                    )

    @commands.command(
        name="close-event",
        usage="close-event <event name>",
        help="Hide the signin channel for the named event, reset the signin menu, and remove the event's role from users."
    )
    @commands.has_permissions(administrator=True)
    async def admin_cmd_close_event(self, ctx: Context, *, args):
        """Admin command: Close the named event category, making the category invisible to all users and removing
        the event role from all users

        :param Context ctx: A context summarising the message which called this command
        :param str args: a string containing the name of the event to close
        """
        if not args:
            await ctx.message.reply(self.STRINGS['request_event_name'])
        elif allData := await self.getGuildEventSettings(ctx, args.lower()):
            guildData, eventData = allData
            signinMenu = self.bot.reactionMenus[eventData["signin_menu_id"]]
            eventChannel = signinMenu.msg.channel
            myPerms = eventChannel.permissions_for(ctx.guild.me)
            if not myPerms.manage_permissions:
                await ctx.send(self.STRINGS['no_channel_edit_perms'].format(channel_id=eventChannel.id))
            elif not myPerms.manage_roles:
                await ctx.send(self.STRINGS['no_role_edit_perms'])
            else:
                eventRole = ctx.guild.get_role(eventData["role_id"])
                if eventRole.position >= ctx.guild.self_role.position:
                    await ctx.send(
                        self.STRINGS['role_edit_perms_bad_order'].format(
                            event_role=eventRole.name,
                            role_name=ctx.guild.self_role.name
                        )
                    )
                else:
                    eventName = args.lower()
                    sharedRole = ctx.guild.get_role(guildData["shared_role_id"])
                    channelEdited = eventChannel.overwrites_for(sharedRole).read_messages
                    usersEdited = len(eventRole.members)
                    # signinMenu.msg = await signinMenu.msg.channel.fetch_message(signinMenu.msg.id)
                    menuReset = True  # len(signinMenu.msg.reactions) > 1

                    if True not in (channelEdited, usersEdited, menuReset):
                        await ctx.message.reply(
                            self.STRINGS['nothing_to_do'].format(
                                channel_id=signinMenu.msg.channel.id,
                                shared_role=sharedRole.name,
                                event_role=eventRole.name
                            )
                        )
                    else:
                        loadingTxts = [
                            "Closing channel... " + ("⏳" if channelEdited else "✅"),
                            "Unassigning role" + ((" from " + str(usersEdited) + " users... ⏳") if usersEdited else "... ✅"),
                            "Resetting signin menu... " + ("⏳" if menuReset else "✅")
                        ]
                        loadingMsg = await ctx.send("\n".join(loadingTxts))
                        adminActions = {
                            self.STRINGS['admin_event_closed'][0]:
                            self.STRINGS['admin_event_closed'][0].format(event_title=eventName.title()),
                            self.STRINGS['admin_role_menu_reset'][0]:
                            self.STRINGS['admin_role_menu_reset'][1].format(
                                menu_id=signinMenu.msg.id,
                                menu_type=type(signinMenu).__name__,
                                menu_url=signinMenu.msg.jump_url
                            )
                        }

                        if channelEdited:
                            reason = self.STRINGS['event_channel_close_reason'].format(
                                author=ctx.author.name,
                                event_name=eventName,
                                command_prefix=self.bot.command_prefix
                            )
                            await eventChannel.set_permissions(sharedRole, read_messages=False, reason=reason)
                            loadingTxts[0] = loadingTxts[0][:-1] + "✅"
                            asyncio.create_task(loadingMsg.edit(content="\n".join(loadingTxts)))
                            adminActions[self.STRINGS['admin_channel_invisible'][0]
                                         ] = self.STRINGS['admin_channel_invisible'][1].format(channel_id=eventChannel.id)
                        membersFutures = set()
                        for member in eventRole.members:
                            reason = self.STRINGS['event_channel_close_reason'].format(
                                author=ctx.author.name,
                                event_name=eventName,
                                command_prefix=self.bot.command_prefix
                            )
                            membersFutures.add(asyncio.create_task(member.remove_roles(eventRole, reason=reason)))

                        if menuReset:
                            await signinMenu.updateMessage()
                            loadingTxts[2] = loadingTxts[2][:-1] + "✅"
                            await loadingMsg.edit(content="\n".join(loadingTxts))

                        if usersEdited:
                            await asyncio.wait(membersFutures)
                            loadingTxts[1] = loadingTxts[1][:-1] + "✅"
                            await loadingMsg.edit(content="\n".join(loadingTxts))
                            adminActions["Event Role Removed"] = f"Users: {usersEdited!s}\n<@&{eventRole.id!s}>"
                            adminActions[
                                self.STRINGS['admin_role_removed'][0]
                            ] = self.STRINGS['admin_role_removed'][1].format(users=usersEdited,
                                                                             event_role_id=eventRole.id)
                        await ctx.message.reply(self.STRINGS['success_event_closed'])
                        await self.bot.adminLog(ctx.message, adminActions)

    @commands.command(
        name="set-event-signin-menu",
        usage="set-event-signin-menu <id> <event name>",
        help="Change the event signin menu to use with `open-event` and `close-event`."
    )
    @commands.has_permissions(administrator=True)
    async def admin_cmd_set_event_signin_menu(self, ctx: Context, *, args: str):
        """Admin command: Change the signin menu associated with an event.
        Must be a ReactionRoleMenu, granting users the event's role.
        
        :param Context ctx: A context summarising the message which called this command
        :param str args: a string containing the id of the new signin menu, followed by the name of the event to update
        """
        if len(args.split(" ")) < 2:
            await ctx.send(self.STRINGS['request_menu_id_event_name'])
        else:
            menuID = args.split(" ")[0]
            if not lib.stringTyping.strIsInt(menuID):
                await ctx.send(self.STRINGS['invalid_menu_id'])
            elif int(menuID) not in self.bot.reactionMenus:
                await ctx.send(self.STRINGS['unrecognised_menu_id'].format(menu_id=menuID))
            else:
                eventName = args[len(menuID) + 1:].lower()
                db = db_gateway()
                if not (eventData := db.get("event_categories", {"guild_id": ctx.guild.id, "event_name": eventName})):
                    if not (allEvents := db.get("event_categoriesevent_channels", params={"guild_id": ctx.guild.id})):
                        await ctx.message.reply(self.STRINGS['no_event_categories'])
                    else:
                        await ctx.message.reply(
                            self.STRINGS['unrecognised_event'].format(
                                events=", ".join(e["event_name"].title() for e in allEvents)
                            )
                        )
                else:
                    eventRole = ctx.guild.get_role(eventData["role_id"])
                    menu = self.bot.reactionMenus[int(menuID)]
                    if not isinstance(menu, ReactionRoleMenu):
                        await ctx.message.reply(
                            self.STRINGS['invalid_signin_menu'].format(role_name=eventRole.name if eventRole else 'event')
                        )
                    else:
                        try:
                            next(o for o in menu.options if isinstance(o, ReactionRoleMenuOption) and o.role == eventRole)
                        except StopIteration:
                            await ctx.message.reply(
                                self.STRINGS['invalid_signin_menu'].format(role_name=eventRole.name if eventRole else 'event')
                            )
                        else:
                            db.update(
                                'event_categories',
                                set_params={"signin_menu_id": menu.msg.id},
                                where_params={
                                    "guild_id": ctx.guild.id,
                                    "event_name": eventName
                                }
                            )
                            await ctx.send(
                                self.STRINGS['success_menu'].format(event_name=eventName.title,
                                                                    menu_url=menu.msg.jump_url)
                            )
                            admin_message = self.STRINGS['admin_menu_updated'][1].format(
                                event_title=eventName.title(),
                                menu_id=menuID,
                                menu_type=type(menu).__name__,
                                menu_url=menu.msg.jump_url
                            )
                            await self.bot.adminLog(ctx.message, {self.STRINGS['admin_menu_updated'][0]: admin_message})

    @commands.command(
        name="set-shared-role",
        usage="set-shared-role <role>",
        help=
        "Change the role to admit/deny into *all* event signin menus. This should NOT be the same as any event role. Role can be given as either a mention or an ID."
    )
    @commands.has_permissions(administrator=True)
    async def admin_cmd_set_shared_role(self, ctx: Context, *, args: str):
        """Admin command: Set the guild's "shared" role, which is denied visibility of the event category channels when not
        signed into the event.
        
        :param Context ctx: A context summarising the message which called this command
        :param str args: a string containing a mention or ID of the new shared role
        """
        if not args:
            await ctx.send(self.STRINGS['request_role_id'])
        else:
            if not (lib.stringTyping.strIsInt(args) or lib.stringTyping.strIsRoleMention(args)):
                await ctx.send(self.STRINGS['invalid_role'])
            else:
                roleID = int(args.lstrip("<@&").rstrip(">"))
                role = ctx.guild.get_role(roleID)
                if role is None:
                    await ctx.send(self.STRINGS['unrecognised_role'])
                else:
                    db_gateway().update(
                        'guild_info',
                        set_params={"shared_role_id": roleID},
                        where_params={"guild_id": ctx.guild.id}
                    )
                    await ctx.send(self.STRINGS['success_shared_role'].format(role_name=role.name))
                    await self.bot.adminLog(
                        ctx.message,
                        {
                            self.STRINGS['admin_shared_role_set'][0]:
                            self.STRINGS['admin_shared_role_set'][1].format(role_id=roleID)
                        }
                    )

    @commands.command(
        name="set-event-role",
        usage="set-event-role <role> <event name>",
        help=
        "Change the role to remove during `close-event`. This should NOT be the same as your shared role. Role can be given as either a mention or an ID."
    )
    @commands.has_permissions(administrator=True)
    async def admin_cmd_set_event_role(self, ctx: Context, *, args: str):
        """Admin command: Set the named event's event role, which is granted visibility of the event category channels.
        
        :param Context ctx: A context summarising the message which called this command
        :param str args: a string containing a mention or ID of the new role, followed by the name of the event to update
        """
        if len(args.split(" ")) < 2:
            await ctx.send(self.STRINGS['request_role_id'])
        else:
            roleStr = args.split(" ")[0]
            if not (lib.stringTyping.strIsInt(roleStr) or lib.stringTyping.strIsRoleMention(roleStr)):
                await ctx.send(self.STRINGS['invalid_role'])
            else:
                roleID = int(roleStr.lstrip("<@&").rstrip(">"))
                role = ctx.guild.get_role(roleID)
                if role is None:
                    await ctx.send(self.STRINGS['unrecognised_role'])
                else:
                    eventName = args[len(roleStr) + 1:].lower()
                    db = db_gateway()
                    if not db.get("event_categories", {"guild_id": ctx.guild.id, "event_name": eventName}):
                        if not (allEvents := db.get("event_categories", params={"guild_id": ctx.guild.id})):
                            await ctx.message.reply(self.STRINGS['no_event_categories'])
                        else:
                            await ctx.message.reply(
                                self.STRINGS['unrecognised_event'].format(
                                    events=", ".join(e["event_name"].title() for e in allEvents)
                                )
                            )
                    else:
                        db.update(
                            'event_categories',
                            set_params={"role_id": roleID},
                            where_params={
                                "guild_id": ctx.guild.id,
                                "event_name": eventName
                            }
                        )
                        await ctx.send(
                            self.STRINGS['success_event_role'].format(event_name=eventName.title(),
                                                                      role_name=role.name)
                        )
                        await self.bot.adminLog(
                            ctx.message,
                            {
                                self.STRINGS['admin_event_role_set'][0]:
                                self.STRINGS['admin_event_role_set'][1].format(role_id=roleID)
                            }
                        )

    @commands.command(
        name="register-event-category",
        usage="register-event-category <signin menu id> <role> <event name>",
        help=
        "Register an existing event category, menu, and role, for use with `open-event` and `close-event`. This does not setup permissions for the category or channels."
    )
    @commands.has_permissions(administrator=True)
    async def admin_cmd_register_event_category(self, ctx: Context, *, args: str):
        """Admin command: Register an existing category as an event category.
        The signin menu and role must already exist, and the new event's name must not already be taken.
        
        :param Context ctx: A context summarising the message which called this command
        :param str args: a string with the ID of the new sigin menu, a mention or ID of the new role, and the name of the event
        """
        argsSplit = args.split(" ")
        if len(argsSplit < 3):
            await ctx.send(self.STRINGS['request_menu_role_name'])
        else:
            menuIDStr = argsSplit[0]
            if not lib.stringTyping.strIsInt(menuIDStr):
                await ctx.send(self.STRINGS['invalid_menu_id'])
            elif int(menuIDStr) not in self.bot.reactionMenus:
                await ctx.send(self.STRINGS['unrecognised_menu_id'].format(menu_ud=menuIDStr))
            else:
                roleStr = argsSplit[1]
                if not (lib.stringTyping.strIsInt(roleStr) or lib.stringTyping.strIsRoleMention(roleStr)):
                    await ctx.send(self.STRINGS['invalid_role'])
                else:
                    roleID = int(roleStr.lstrip("<@&").rstrip(">"))
                    role = ctx.guild.get_role(roleID)
                    if role is None:
                        await ctx.send(self.STRINGS['unrecognised_role'])
                    else:
                        eventName = args[len(roleStr) + len(menuIDStr) + 2:].lower()
                        db = db_gateway()
                        if db.get("event_categories", {"guild_id": ctx.guild.id, "event_name": eventName}):
                            await ctx.message.reply(self.STRINGS['event_exists'].format(event_name=eventName.title()))
                        else:
                            menu = self.bot.reactionMenus[int(menuIDStr)]
                            db.insert(
                                'event_categories',
                                {
                                    "guild_id": ctx.guild.id,
                                    "event_name": eventName,
                                    "role_id": roleID,
                                    "signin_menu_id": menu.msg.id
                                }
                            )
                            await ctx.send(self.STRINGS['success_event_category'].format(event_name=eventName.title()))
                            admin_message = self.STRINGS['admin_existing_event_registered'][1].format(
                                event_title=eventName.title(),
                                menu_id=menuIDStr,
                                role_id=roleID,
                                menu_url=menu.msg.jump_url
                            )
                            await self.bot.adminLog(
                                ctx.message,
                                {self.STRINGS['admin_existing_event_registered'][0]: admin_message}
                            )

    @commands.command(
        name="create-event-category",
        usage="create-event-category <event name>",
        help=
        "Create a new event category with a signin channel and menu, event role, general channel and correct permissions, and automatically register them for use with `open-event` and `close-event`."
    )
    @commands.has_permissions(administrator=True)
    async def admin_cmd_create_event_category(self, ctx: Context, *, args: str):
        """Admin command: Automatically create and fully set up a new event category with the given name.
        
        :param Context ctx: A context summarising the message which called this command
        :param str args: a string containing the name of the event to create
        """
        if not args:
            await ctx.send(self.STRINGS['request_event_name'])
        else:
            db = db_gateway()
            eventName = args.lower()
            if db.get("event_categories", {"guild_id": ctx.guild.id, "event_name": eventName}):
                await ctx.message.reply(self.STRINGS['event_exists'].format(event_name=eventName.title()))
            else:
                guildData = db.get("guild_info", {"guild_id": ctx.guild.id})[0]
                if not guildData["shared_role_id"]:
                    await ctx.message.reply(self.STRINGS['no_shared_role'].format(command_prefix=self.bot.command_prefix))
                else:
                    if not (sharedRole := ctx.guild.get_role(guildData["shared_role_id"])):
                        await ctx.message.reply(
                            self.STRINGS['missing_shared_role'].format(command_prefix=self.bot.command_prefix)
                        )
                    else:
                        emojiSelectorMsg = await ctx.message.reply(self.STRINGS['react_start'])

                        def emojiSelectorCheck(data: RawReactionActionEvent) -> bool:
                            return data.message_id == emojiSelectorMsg.id and data.user_id == ctx.author.id and (
                                data.emoji.is_unicode_emoji or self.bot.get_emoji(data.emoji.id)
                            )

                        try:
                            signinEmoji = lib.emotes.Emote.fromPartial(
                                (await self.bot.wait_for("raw_reaction_add",
                                                         check=emojiSelectorCheck,
                                                         timeout=60)).emoji,
                                rejectInvalid=True
                            )
                        except asyncio.TimeoutError:
                            await emojiSelectorMsg.reply(self.STRINGS['react_no_time'])
                        except lib.exceptions.UnrecognisedCustomEmoji:
                            await emojiSelectorMsg.reply(self.STRINGS['react_error'])
                        else:
                            creationReason = self.STRINGS['event_category_create_reason'].format(
                                event_name=eventName,
                                command_prefix=self.bot.command_prefix
                            )
                            eventRole = await ctx.guild.create_role(name=eventName.title(), reason=creationReason)
                            categoryOverwrites = {
                                sharedRole: EVENT_CATEGORY_SHARED_ROLE_PERMS,
                                eventRole: EVENT_CATEGORY_EVENT_ROLE_PERMS
                            }
                            signinOverwrites = {
                                sharedRole: CLOSED_EVENT_SIGNIN_CHANNEL_SHARED_PERMS,
                                eventRole: EVENT_SIGNIN_CHANNEL_EVENT_PERMS
                            }
                            if eventRole != ctx.guild.default_role:
                                categoryOverwrites[ctx.guild.default_role] = EVENT_CATEGORY_EVERYONE_PERMS
                                signinOverwrites[ctx.guild.default_role] = EVENT_CATEGORY_EVERYONE_PERMS
                            newCategory = await ctx.guild.create_category(
                                eventName.title(),
                                reason=creationReason,
                                overwrites=categoryOverwrites
                            )
                            signinChannel = await ctx.guild.create_text_channel(
                                f"{eventName}-signin",
                                reason=creationReason,
                                category=newCategory,
                                overwrites=signinOverwrites
                            )
                            eventGeneral = await ctx.guild.create_text_channel(
                                f"{eventName}-general",
                                reason=creationReason,
                                category=newCategory,
                                overwrites=categoryOverwrites
                            )
                            eventVoice = await ctx.guild.create_voice_channel(
                                f"{eventName}-voice",
                                reason=creationReason,
                                category=newCategory,
                                overwrites=categoryOverwrites
                            )
                            signinMenuMsg = await signinChannel.send("​")
                            signinMenu = ReactionRoleMenu(
                                signinMenuMsg,
                                self.bot,
                                {signinEmoji: eventRole},
                                col=Colour.blue(),
                                titleTxt=self.STRINGS['menu_title'].format(event_name=eventName.title()),
                                desc=self.STRINGS['menu_description'].format(event_role=eventRole.name)
                            )
                            await signinMenu.updateMessage()
                            self.bot.reactionMenus.add(signinMenu)
                            db.insert(
                                'event_categories',
                                {
                                    "guild_id": ctx.guild.id,
                                    "event_name": eventName,
                                    "role_id": eventRole.id,
                                    "signin_menu_id": signinMenuMsg.id
                                }
                            )
                            await ctx.send(
                                self.STRINGS['success_event'].format(
                                    event_title=eventName.title(),
                                    signin_menu_id=signinMenuMsg.id,
                                    signin_channel_mention=signinChannel.mention,
                                    shared_role_name=sharedRole.name,
                                    command_prefix=self.bot.command_prefix,
                                    event_name=eventName,
                                    event_general_mention=eventGeneral.mention,
                                    event_role_mention=eventRole.mention
                                )
                            )
                            admin_message = self.STRINGS['admin_event_category_updated'][1].format(
                                event_title=eventName.title(),
                                menu_id=signinMenuMsg.id,
                                role_id=eventRole.id,
                                menu_url=signinMenuMsg.jump_url
                            )
                            await self.bot.adminLog(
                                ctx.message,
                                {self.STRINGS['admin_event_category_updated'][0]: admin_message}
                            )

    @commands.command(
        name="unregister-event-category",
        usage="unregister-event-category <event name>",
        help=
        "Unregister an event category and role so that it can no longer be used with `open-event` and `close-event`, but without deleting the channels."
    )
    @commands.has_permissions(administrator=True)
    async def admin_cmd_unregister_event_category(self, ctx: Context, *, args: str):
        """Admin command: Unregister a category, menu and role as an event category, without deleting any of them
        from the server.
        
        :param Context ctx: A context summarising the message which called this command
        :param str args: a string containing the name of the event to unregister
        """
        if not args:
            await ctx.send(self.STRINGS['request_event_name'])
        else:
            db = db_gateway()
            eventName = args.lower()
            if not db.get("event_categories", {"guild_id": ctx.guild.id, "event_name": eventName}):
                if not (allEvents := db.get("event_categories", params={"guild_id": ctx.guild.id})):
                    await ctx.message.reply(self.STRINGS['no_event_categories'])
                else:
                    await ctx.message.reply(
                        self.STRINGS['unrecognised_event'].format(
                            events=", ".join(e["event_name"].title() for e in allEvents)
                        )
                    )
            else:
                db.delete("event_categories", {"guild_id": ctx.guild.id, "event_name": eventName})
                await ctx.message.reply(self.STRINGS['success_event_role_unregister'].format(event_title=eventName.title()))
                admin_message = self.STRINGS['admin_event_category_unregistered'].format(event_title=eventName.title())
                await self.bot.adminLog(ctx.message, {self.STRINGS['admin_event_category_unregistered'][0]: admin_message})

    @commands.command(
        name="delete-event-category",
        usage="delete-event-category <event name>",
        help="Delete an event category and its role and channels from the server."
    )
    @commands.has_permissions(administrator=True)
    async def admin_cmd_delete_event_category(self, ctx: Context, *, args: str):
        """Admin command: Delete an event category, its channels and role from the server entirely.
        
        :param Context ctx: A context summarising the message which called this command
        :param str args: a string containing the name of the event to delete
        """
        if not args:
            await ctx.send(self.STRINGS['request_event_name'])
        else:
            db = db_gateway()
            eventName = args.lower()
            if not (eventData := db.get("event_categories", {"guild_id": ctx.guild.id, "event_name": eventName})):
                if not (allEvents := db.get("event_categories", params={"guild_id": ctx.guild.id})):
                    await ctx.message.reply(self.STRINGS['no_event_categories'])
                else:
                    await ctx.message.reply(
                        self.STRINGS['unrecognised_event'].format(
                            events=", ".join(e["event_name"].title() for e in allEvents)
                        )
                    )
            else:
                signinMenuID = eventData[0]["signin_menu_id"]
                eventCategory = self.bot.reactionMenus[signinMenuID].msg.channel.category
                numChannels = len(eventCategory.channels)
                eventRole = ctx.guild.get_role(eventData[0]["role_id"])
                confirmMsg = await ctx.message.reply(
                    self.STRINGS['react_delete_confirm'].format(
                        event_title=eventName.title(),
                        event_segment=(f", the {eventRole.name} role," if eventRole else ""),
                        num_channels=numChannels
                    )
                )
                asyncio.create_task(confirmMsg.add_reaction('👍'))
                asyncio.create_task(confirmMsg.add_reaction('👎'))

                def confirmCheck(data: RawReactionActionEvent) -> bool:
                    return data.message_id == confirmMsg.id and data.user_id == ctx.author.id and (
                        data.emoji.is_unicode_emoji and data.emoji.name in ['👍',
                                                                            '👎']
                    )

                try:
                    confirmResult = (await self.bot.wait_for("raw_reaction_add", check=confirmCheck, timeout=60)).emoji
                except asyncio.TimeoutError:
                    await confirmMsg.reply(self.STRINGS['react_no_time'])
                else:
                    if confirmResult.name == "👎":
                        await ctx.send(self.STRINGS['react_event_delete_cancel'])
                    else:
                        deletionReason = self.STRINGS['event_category_delete_reason'].format(
                            event_name=eventName,
                            command_prefix=self.bot.command_prefix
                        )
                        self.bot.reactionMenus.removeID(signinMenuID)
                        deletionTasks = set()
                        if eventRole:
                            deletionTasks.add(asyncio.create_task(eventRole.delete(reason=deletionReason)))
                        for currentCategory in eventCategory.channels:
                            deletionTasks.add(asyncio.create_task(currentCategory.delete(reason=deletionReason)))
                        deletionTasks.add(asyncio.create_task(eventCategory.delete(reason=deletionReason)))
                        await asyncio.wait(deletionTasks)
                        db.delete("event_categories", {"guild_id": ctx.guild.id, "event_name": eventName})
                        await ctx.message.reply(self.STRINGS['success_event_deleted'].format(event_title=eventName.title()))
                        admin_message = self.STRINGS['admin_event_category_deleted'][1].format(
                            event_title=eventName.title(),
                            num_channels=numChannels
                        ) + (f"\nRole deleted: #{eventData[0]['role_id']!s}" if eventData[0]['role_id'] else "")
                        await self.bot.adminLog(ctx.message, {self.STRINGS['admin_event_category_deleted'][0]: admin_message})


def setup(bot: "EsportsBot"):
    """Create a new instance of EventCategoriesCog, and register it to the given client instance.

    :param EsportsBot bot: The client instance to register the new cog instance with
    """
    bot.add_cog(EventCategoriesCog(bot))
