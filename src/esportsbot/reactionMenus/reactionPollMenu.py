from __future__ import annotations
from . import reactionMenu
from .. import lib
from ..db_gateway import db_gateway
from discord import Colour, Emoji, PartialEmoji, Message, Embed, User, Member, Role
from datetime import datetime
from typing import Dict, Union, TYPE_CHECKING


def makePollBar(name: str, numVotes: int, maxNameLength: int, maxVotes: int, maxBarLength: int) -> str:
    """Make a bar for a poll results bar chart for a the statistics of a given poll option.

    :param str name: The name of the poll option
    :param int numVotes: The number of votes that the option received
    :param int maxNameLenth: The length of the longest option name in the poll
    :param int maxVotes: The number of votes received by the winning option
    :param int maxBarLength: The maximum length a bar may be
    :return: A string containing the name of the option, followed by a number of = characters proportional to the number of
            votes this option received in relation to the winning option, followed by the nuber of votes.
    :rtype: str
    """
    winner = numVotes == maxVotes
    nameSpacing = maxNameLength - len(name)
    barLength = int((numVotes / maxVotes) * maxBarLength)
    return name + (" " * nameSpacing) + " | " \
            + ("=" * barLength) + ("" if numVotes else " ") \
            + ("🏆" if winner else "") + " +" + str(numVotes) + " Vote" + ("" if numVotes == 1 else "s")


async def printAndExpirePollResults(msgID : int):
    """Menu expiring method specific to ReactionPollMenus. Count the reactions on the menu, selecting only one per user
    in the case of single-choice mode polls, and replace the menu embed content with a bar chart summarising
    the results of the poll.

    :param int msgID: The id of the discord message containing the menu to expire
    """
    client = lib.client.instance()
    menu = client.reactionMenus[msgID]

    # Update message cache for latest reactions
    menu.msg = await menu.msg.channel.fetch_message(menu.msg.id)
    # Which users voted for which option
    results = {option: [] for option in menu.options.values()}
    # The character length of longest option name, for table formatting purposes
    maxOptionLen = max(len(option.name) for option in menu.options.values())

    # Allow the creation of another poll
    runningPolls = db_gateway().get("guild_info", {"guild_id": menu.msg.guild.id})[0]["num_running_polls"]
    db_gateway().update("guild_info", {"num_running_polls", runningPolls - 1}, {"guild_id", menu.msg.guild.id})
    # Unregister this reaction menu
    if msgID in client.reactionMenus:
        del client.reactionMenus[msgID]

    # Collect votes
    for reaction in menu.msg.reactions:
        try:
            currentEmoji = lib.emotes.Emote.fromReaction(reaction.emoji, rejectInvalid=True)
        # Reject custom emojis that are not accessible to the bot
        except lib.exceptions.UnrecognisedEmoji:
            continue
        
        # Validate emotes
        if currentEmoji is None:
            print("[reactionPollMenu.printAndExpirePollResults] Failed to fetch Emote for reaction: " + str(reaction))
            pollEmbed = menu.msg.embeds[0]
            pollEmbed.set_footer(text="This poll has ended.")
            await menu.msg.edit(content="An error occured when calculating the results of this poll. " \
                                        + "The error has been logged.", embed=pollEmbed)
            return

        # Associate reactions with poll options
        menuOption = None
        for currentOption in results:
            if currentOption.emoji == currentEmoji:
                menuOption = currentOption
                break
        
        # Ignore reactions which do not correspond to poll options
        if menuOption is None:
            continue
        
        # Collate votes for this poll option
        async for user in reaction.users():
            if user != client.user:
                # Used in single-choice polls to indicate that this user has not yet voted
                validVote = True
                if not menu.multipleChoice:
                    # Ensure this user hasn't already voted
                    for currentOption in results:
                        if currentOption.emoji != currentEmoji and user in results[currentOption]:
                            validVote = False
                            break
                # Record this user's vote
                if validVote and user not in results[menuOption]:
                    results[menuOption].append(user)
    
    # Mark the poll as expired
    pollEmbed = menu.msg.embeds[0]
    pollEmbed.set_footer(text="This poll has ended.")

    # Find the maximum number of votes
    try:
        maxCount = max(len(votes) for votes in results.values())
    # No votes received
    except ValueError:
        pollEmbed.add_field(name="Results", value="No votes received!", inline=False)
    else:
        # Construct results chart
        maxBarLength = 10
        resultsStr = "```\n" \
            + "\n".join(makePollBar(option.name, len(results[option]), maxOptionLen, maxCount, maxBarLength) \
                        for option in results) \
            + "```"

        pollEmbed.add_field(name="Results", value=resultsStr, inline=False)

    await menu.msg.edit(embed=pollEmbed)

    for reaction in menu.msg.reactions:
        await reaction.remove(menu.msg.guild.me)
    

class ReactionPollMenu(reactionMenu.ReactionMenu):
    """A saveable reaction menu taking a vote from its participants on a selection of option strings.
    On menu expiry, the menu's TimedTask should call printAndExpirePollResults. This edits to menu embed to provide a summary and bar chart of the votes submitted to the poll.
    The poll options have no functionality, all vote counting takes place after menu expiry.
    TODO: change pollOptions from dict[Emote, ReactionMenuOption] to dict[Emote, str] which is used to spawn DummyReactionMenuOptions

    :var multipleChoice: Whether to accept votes for multiple options from the same user, or to restrict users to one option vote per poll.
    :vartype multipleChoice: bool
    :var owningBasedUser: The bbUser who started the poll
    :vartype owningBasedUser: bbUser
    """
    def __init__(self, msg : Message, pollOptions : dict, timeout : timedTask.TimedTask, pollStarter : Union[User, Member] = None,
            multipleChoice : bool = False, titleTxt : str = "", desc : str = "", col : Colour = Colour.blue(), footerTxt : str = "",
            img : str = "", thumb : str = "", icon : str = "", authorName : str = "", targetMember : Member = None,
            targetRole : Role = None, owningBasedUser : basedUser.BasedUser = None):
        """
        :param discord.Message msg: the message where this menu is embedded
        :param options: A dictionary storing all of the poll options. Poll option behaviour functions are not called. TODO: Add reactionAdded/Removed overloads that just return and dont check anything
        :type options: dict[lib.emotes.Emote, ReactionMenuOption]
        :param TimedTask timeout: The TimedTask responsible for expiring this menu
        :param discord.Member pollStarter: The user who started the poll, for printing in the menu embed. Optional. (Default None)
        :param bool multipleChoice: Whether to accept votes for multiple options from the same user, or to restrict users to one option vote per poll.
        :param str titleTxt: The content of the embed title (Default "")
        :param str desc: he content of the embed description; appears at the top below the title (Default "")
        :param discord.Colour col: The colour of the embed's side strip (Default None)
        :param str footerTxt: Secondary description appearing in darker font at the bottom of the embed (Default time until menu expiry if timeout is not None, "" otherwise)
        :param str img: URL to a large icon appearing as the content of the embed, left aligned like a field (Default "")
        :param str thumb: URL to a larger image appearing to the right of the title (Default "")
        :param str icon: URL to a smaller image to the left of authorName. AuthorName is required for this to be displayed. (Default "")
        :param str authorName: Secondary, smaller title for the embed (Default "Poll")
        :param discord.Member targetMember: The only discord.Member that is able to interact with this menu. All other reactions are ignored (Default None)
        :param discord.Role targetRole: In order to interact with this menu, users must possess this role. All other reactions are ignored (Default None)
        :param bbUser owningBasedUser: The bbUser who started the poll. Used for resetting whether or not a user can make a new poll (Default None)
        """
        self.multipleChoice = multipleChoice
        self.owningBasedUser = owningBasedUser

        if pollStarter is not None and authorName == "":
            authorName = str(pollStarter) + " started a poll!"
        else:
            authorName = authorName if authorName else "Poll"

        if icon == "":
            if pollStarter is not None:
                icon = str(pollStarter.avatar_url_as(size=64))
        else:
            icon = icon if icon else "https://emojipedia-us.s3.dualstack.us-west-1.amazonaws.com/thumbs/120/twitter/259/ballot-box-with-ballot_1f5f3.png"

        if desc == "":
            desc = "React to this message to vote!"
        else:
            desc = "*" + desc + "*"

        super(ReactionPollMenu, self).__init__(msg, options=pollOptions, titleTxt=titleTxt, desc=desc, col=col, footerTxt=footerTxt, img=img, thumb=thumb, icon=icon, authorName=authorName, timeout=timeout, targetMember=targetMember, targetRole=targetRole)
        self.saveable = True


    def getMenuEmbed(self) -> Embed:
        """Generate the discord.Embed representing the reaction menu, and that
        should be embedded into the menu's message.
        Contains a short description of the menu, its options, the poll starter (if given), whether it accepts multiple choice votes, and its expiry time.

        :return: A discord.Embed representing the menu and its options
        :rtype: discord.Embed 
        """
        baseEmbed = super(ReactionPollMenu, self).getMenuEmbed()
        if self.multipleChoice:
            baseEmbed.add_field(name="This is a multiple choice poll!", value="Voting for more than one option is allowed.", inline=False)
        else:
            baseEmbed.add_field(name="This is a single choice poll!", value="If you vote for more than one option, only one will be counted.", inline=False)

        return baseEmbed

    
    def toDict(self, **kwargs) -> dict:
        """Serialize this menu to dictionary format for saving.

        :return: A dictionary containing all information needed to recreate this menu
        :rtype: dict
        """
        baseDict = super(ReactionPollMenu, self).toDict(**kwargs)
        baseDict["multipleChoice"] = self.multipleChoice
        baseDict["owningBasedUser"] = self.owningBasedUser.id
        return baseDict
    

    @classmethod
    def fromDict(cls, rmDict : dict, **kwargs) -> ReactionPollMenu:
        """Reconstruct a ReactionPollMenu object from its dictionary-serialized representation - the opposite of ReactionPollMenu.toDict

        :param dict rmDict: A dictionary containing all information needed to recreate the desired ReactionPollMenu
        :return: A new ReactionPollMenu object as described in rmDict
        :rtype: ReactionPollMenu
        """
        if "msg" not in kwargs:
            raise NameError("Required kwarg not given: msg")
        msg = kwargs["msg"]

        options = {}
        for emojiName in rmDict["options"]:
            emoji = lib.emotes.Emote.fromStr(emojiName, rejectInvalid=True)
            options[emoji] = reactionMenu.DummyReactionMenuOption(rmDict["options"][emojiName], emoji)

        timeoutTT = None
        if "timeout" in rmDict:
            expiryTime = datetime.utcfromtimestamp(rmDict["timeout"])
            botState.reactionMenusTTDB.scheduleTask(timedTask.TimedTask(expiryTime=expiryTime, expiryFunction=printAndExpirePollResults, expiryFunctionArgs=msg.id))

        return ReactionPollMenu(msg, options, timeoutTT, multipleChoice=rmDict["multipleChoice"] if "multipleChoice" in rmDict else False,
                                    titleTxt=rmDict["titleTxt"] if "titleTxt" in rmDict else "",
                                    desc=rmDict["desc"] if "desc" in rmDict else "",
                                    col=Colour.from_rgb(rmDict["col"][0], rmDict["col"][1], rmDict["col"][2]) if "col" in rmDict else Colour.blue(),
                                    footerTxt=rmDict["footerTxt"] if "footerTxt" in rmDict else "",
                                    img=rmDict["img"] if "img" in rmDict else "",
                                    thumb=rmDict["thumb"] if "thumb" in rmDict else "",
                                    icon=rmDict["icon"] if "icon" in rmDict else "",
                                    authorName=rmDict["authorName"] if "authorName" in rmDict else "",
                                    targetMember=msg.guild.get_member(rmDict["targetMember"]) if "targetMember" in rmDict else None,
                                    targetRole=msg.guild.get_role(rmDict["targetRole"]) if "targetRole" in rmDict else None,
                                    owningBasedUser=botState.usersDB.getUser(rmDict["owningBasedUser"]) if "owningBasedUser" in rmDict and botState.usersDB.userIDExists(rmDict["owningBasedUser"]) else None)
