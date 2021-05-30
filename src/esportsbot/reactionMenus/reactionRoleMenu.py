"""
The reactionMenus package was partially copied over from the BASED template project: https://github.com/Trimatix/BASED
It is modified and not actively synced with BASED, so will very likely be out of date.

.. codeauthor:: Trimatix
"""
from . import reactionMenu
from .. import lib
from discord import Colour, Guild, Role, Message, User, Client, Member, PartialMessage
from typing import List, Union, Dict


async def giveRole(args : List[Union[Guild, Role, int]], reactingUser : Union[User, Member] = None) -> bool:
    """Grant the given user the role described in args.
    if reactingUser already has the requested role, do nothing.

    :param dict args: A list containing the guild to grant the role in, the role to grant, and finally the message ID that triggered the role addition.
    :param discord.User reactingUser: The user to grant the role to (Default None)
    :return: The new state of role ownership; always True
    :rtype: bool
    """
    dcGuild = args[0]
    dcMember = dcGuild.get_member(reactingUser.id)
    role = args[1]
    msgID = args[2]

    if role not in dcMember.roles:
        await dcMember.add_roles(role, reason="User requested role toggle via reaction menu " + str(msgID))
    return True


async def removeRole(args : List[Union[Guild, Role, int]], reactingUser : Union[User, Member] = None) -> bool:
    """remove the role described in args from the given user.
    if reactingUser already lacks the requested role, do nothing.

    :param dict args: A list containing the guild to remove the role in, the role to grant, and finally the message ID that triggered the role addition.
    :param discord.User reactingUser: The user to remove the role from (Default None)
    :return: The new state of role ownership; always False
    :rtype: bool
    """
    dcGuild = args[0]
    dcMember = dcGuild.get_member(reactingUser.id)
    role = args[1]
    msgID = args[2]

    if role in dcMember.roles:
        await dcMember.remove_roles(role, reason="User requested role toggle via reaction menu " + str(msgID))
    return False


class ReactionRoleMenuOption(reactionMenu.ReactionMenuOption):
    """A saveable reaction menu option that stores a role, granting the reacting user the role when added,
    and removing the role when the reaction is removed.
    Constraining eligible users can be done through the ReactionMenu kwargs targetMember and targetRole.

    :var role: The role to toggle on reactions
    :vartype role: discord.Role 
    """

    def __init__(self, emoji : lib.emotes.Emote, role : Role, menu : reactionMenu.ReactionMenu):
        """
        :param lib.emotes.Emote emoji: The emoji to react to the menu with to trigger role updates
        :param Role role: The role to (un)assign reacting users
        """
        self.role = role
        super(ReactionRoleMenuOption, self).__init__(self.role.name, emoji, addFunc=giveRole, addArgs=(menu.msg.guild, self.role, menu.msg.id), removeFunc=removeRole, removeArgs=(menu.msg.guild, self.role, menu.msg.id))


    def toDict(self) -> dict:
        """Serialize the option into dictionary format for saving.
        Since reaction menu options are saved alongside their emojis, this dictionary need not contain the option emoji.

        :return: A dictionary containing all information needed to reconstruct this menu option
        :rtype: dict
        """
        return {"role": self.role.id}

    
    @classmethod
    def fromDict(self, data: dict, **kwargs) -> "ReactionRoleMenuOption":
        """Deserialize a dictionary representation of a ReactionRoleMenuOption into a functioning object.
        In order to fetch this option's role, the guild containing the role is a required kwarg for this deserializer.
        The option's emoji and owning ReactionMenu are also required kwargs.

        :param dict data: A dictionary containing the ID of this option's role
        :param Guild dcGuild: The guild containing the role with the ID given in data (Default None)
        :param Emote emoji: The emote to represent this option in the menu (Default None)
        :param ReactionMenu menu: The menu owning this option (Default None)
        :return: A ReactionRoleMenuOption that grants/removes the role identified in data
        :rtype: ReactionRoleMenuOption
        """
        params = {"dcGuild": Guild, "emoji": lib.emotes.Emote, "menu": reactionMenu.ReactionMenu}
        for oName, oType in params.items():
            if oName not in kwargs: raise NameError("Missing required kwarg: " + oName)
            if not isinstance(kwargs[oName], oType): raise TypeError("Expected type " + oType.__name__ + " for parameter " + oName + ", received " + type(kwargs[oName]).__name__)
        return ReactionRoleMenuOption(kwargs["emoji"], kwargs["dcGuild"].get_role(data["role"]), kwargs["menu"])


@reactionMenu.saveableMenu
class ReactionRoleMenu(reactionMenu.ReactionMenu):
    """A saveable reaction menu that grants and removes roles when interacted with.
    """

    def __init__(self, msg : Message, client: Client, reactionRoles : Dict[lib.emotes.Emote, Role],
            titleTxt : str = "", desc : str = "", col : Colour = None,
            footerTxt : str = "", img : str = "", thumb : str = "", icon : str = "", authorName : str = "",
            targetMember : Member = None, targetRole : Role = None):
        """
        :param discord.Message msg: the message where this menu is embedded
        :param discord.Client client: The client that instanced this menu
        :param reactionRoles: A dictionary where keys are emojis and values are the roles to grant/remove when adding/removing the emoji 
        :type reactionRoles: dict[lib.emotes.Emote, discord.Role]
        :param str titleTxt: The content of the embed title (Default "**Role Menu**")
        :param str desc: he content of the embed description; appears at the top below the title (Default "React for your desired role!")
        :param discord.Colour col: The colour of the embed's side strip (Default None)
        :param str footerTxt: Secondary description appearing in darker font at the bottom of the embed (Default "")
        :param str img: URL to a large icon appearing as the content of the embed, left aligned like a field (Default "")
        :param str thumb: URL to a larger image appearing to the right of the title (Default "")
        :param str icon: URL to a smaller image to the left of authorName. AuthorName is required for this to be displayed. (Default "")
        :param str authorName: Secondary, smaller title for the embed (Default "")
        :param discord.Member targetMember: The only discord.Member that is able to interact with this menu. All other reactions are ignored (Default None)
        :param discord.Role targetRole: In order to interact with this menu, users must possess this role. All other reactions are ignored (Default None)
        """
        self.msg = msg
        roleOptions = {}
        for reaction in reactionRoles:
            roleOptions[reaction] = ReactionRoleMenuOption(reaction, reactionRoles[reaction], self)

        if titleTxt == "":
            titleTxt = "**Role Menu**"
        if desc == "":
            desc = "React for your desired role!"

        super(ReactionRoleMenu, self).__init__(msg, client, options=roleOptions, titleTxt=titleTxt, desc=desc, col=col if col is not None else Colour.blue(), footerTxt=footerTxt, img=img, thumb=thumb, icon=icon, authorName=authorName, targetMember=targetMember, targetRole=targetRole)


    def toDict(self) -> dict:
        """Serialize this menu to dictionary format for saving to file.

        :return: A dictionary containing all information needed to reconstruct this menu object
        :rtype: dict
        """
        # TODO: Remove this method. The guild is already saved in ReactionMenu.toDict
        baseDict = super(ReactionRoleMenu, self).toDict()
        baseDict["guild"] = self.msg.guild.id
        return baseDict


    @classmethod
    def fromDict(csl, client: Client, rmDict : dict) -> "ReactionRoleMenu":
        """Reconstruct a ReactionRolePicker from its dictionary-serialized representation.

        :param dict rmDict: A dictionary containing all information needed to construct the desired ReactionRolePicker
        :return: A new ReactionRolePicker object as described in rmDict
        :rtype: ReactionRolePicker
        """
        dcGuild = client.get_guild(rmDict["guild"])
        channelGetter = client if dcGuild is None else dcGuild
        dcChannel = channelGetter.get_channel(rmDict["channel"])
        if dcChannel is None:
            raise lib.exceptions.UnrecognisedReactionMenuMessage(rmDict["guild"], rmDict["channel"], rmDict["msg"])
        msg = PartialMessage(channel=dcChannel, id=rmDict["msg"])

        reactionRoles = {}
        for reaction in rmDict["options"]:
            reactionRoles[lib.emotes.Emote.fromStr(reaction)] = dcGuild.get_role(rmDict["options"][reaction]["role"])


        return ReactionRoleMenu(msg, client, reactionRoles,
                                    titleTxt=rmDict["titleTxt"] if "titleTxt" in rmDict else "",
                                    desc=rmDict["desc"] if "desc" in rmDict else "",
                                    col=Colour.from_rgb(rmDict["col"][0], rmDict["col"][1], rmDict["col"][2]) if "col" in rmDict else Colour.blue(),
                                    footerTxt=rmDict["footerTxt"] if "footerTxt" in rmDict else "",
                                    img=rmDict["img"] if "img" in rmDict else "",
                                    thumb=rmDict["thumb"] if "thumb" in rmDict else "",
                                    icon=rmDict["icon"] if "icon" in rmDict else "",
                                    authorName=rmDict["authorName"] if "authorName" in rmDict else "",
                                    targetMember=dcGuild.get_member(rmDict["targetMember"]) if "targetMember" in rmDict else None,
                                    targetRole=dcGuild.get_role(rmDict["targetRole"]) if "targetRole" in rmDict else None)
