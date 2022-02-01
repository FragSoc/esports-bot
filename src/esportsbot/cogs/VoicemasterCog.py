import re
from discord.ext import commands
from esportsbot.base_functions import (get_whether_in_vm_parent, get_whether_in_vm_child)
from esportsbot.db_gateway import DBGatewayActions
from esportsbot.models import VoicemasterMaster, VoicemasterSlave


class VoicemasterCog(commands.Cog):
    """
    Voicemaster is used as a way to have a dynamic number of voice channels. By having a single parent voice channel, users can
    easily create their own room/channel by joining, allowing them to easily talk with just the people they want to.

    This module implements commands used to manage the parent and child channels, all commands require the administrator
    permission in a server.
    """
    def __init__(self, bot):
        self.bot = bot
        self.STRINGS = bot.STRINGS['voicemaster']
        self.banned_words = []
        with open("esportsbot/banned_words.txt", "r") as f:
            for line in f.readlines():
                if not line.startswith("#"):
                    self.banned_words.append(line.strip())

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """
        When any users voice state changes, such as joining, leaving or moving voice channels, check if the voice channel they
        are in is a parent or child, and if so perform the necessary actions.

        - If the user was the last to leave a child voice channel, delete it.
        - If the user was the owner of the child voice channel, transfer the ownership to another user in the channel.
        - If the user joined the parent voice channel, create a new child channel that they own.
        :param member: The member whose voice state has changed.
        :param before: The member's voice state before the change.
        :param after: The member's voice state after the change.
        """
        if not member.guild.me.guild_permissions.move_members:
            await self.bot.admin_log(
                guild_id=member.guild.id,
                actions={
                    "Cog": self.__class__.__name__,
                    "Message": "I need the permission `move members` in this guild to be able to perform Voicemaster"
                }
            )
            return

        if not before.channel and not after.channel:
            return

        if before.channel:
            # The user has either disconnected or moved voice channels.
            if get_whether_in_vm_child(before.channel.guild.id, before.channel.id):
                # If the user was in a VM child.
                vm_child = DBGatewayActions().get(VoicemasterSlave, guild_id=member.guild.id, channel_id=before.channel.id)
                if not before.channel.members:
                    # The VM is empty, delete it.
                    await before.channel.delete()
                    DBGatewayActions().delete(vm_child)
                elif vm_child.owner_id == member.id:
                    # It was the owner of the channel that left, transfer ownership.
                    if not vm_child.custom_name:
                        await before.channel.edit(name=f"{before.channel.members[0].display_name}'s VC")
                    vm_child.owner_id = before.channel.members[0].id
                    DBGatewayActions().update(vm_child)

        if after.channel and get_whether_in_vm_parent(after.channel.guild.id, after.channel.id):
            child_channel = await member.guild.create_voice_channel(
                f"{member.display_name}'s VC",
                category=after.channel.category
            )
            child_db_entry = VoicemasterSlave(
                guild_id=member.guild.id,
                channel_id=child_channel.id,
                owner_id=member.id,
                locked=False,
                custom_name=False
            )
            DBGatewayActions().create(child_db_entry)
            await member.move_to(child_channel)

    @commands.group("voice", aliases=["vm"])
    async def command_group(self, ctx):
        """
        The command group used to make all commands sub-commands .
        :param ctx: The context of the command .
        """
        pass

    @command_group.command(name="setparent", aliases=["setvmparent"])
    @commands.has_permissions(administrator=True)
    async def setvmparent(self, ctx, given_channel_id=None):
        """
        Set the given voice channel as a parent voice channel. There can be more than one parent voice channel in a server.
        :param ctx: The context of the command.
        :param given_channel_id: The ID of the voice channel to set as the parent voice channel.
        """
        is_a_valid_id = given_channel_id and given_channel_id.isdigit() and len(given_channel_id) == 18

        if is_a_valid_id:
            is_a_parent = DBGatewayActions().get(VoicemasterMaster, guild_id=ctx.author.guild.id, channel_id=given_channel_id)
            is_voice_channel = hasattr(self.bot.get_channel(int(given_channel_id)), 'voice_states')
            is_a_child = DBGatewayActions().get(VoicemasterSlave, guild_id=ctx.author.guild.id, channel_id=given_channel_id)

            if is_voice_channel and not (is_a_parent or is_a_child):
                # Not currently a Parent and is voice channel, add it
                DBGatewayActions().create(VoicemasterMaster(guild_id=ctx.author.guild.id, channel_id=given_channel_id))
                await ctx.channel.send("This VC has now been set as a VM parent")
                new_vm_parent_channel = self.bot.get_channel(int(given_channel_id))
                await self.bot.admin_log(
                    responsible_user=ctx.author,
                    guild_id=ctx.guild.id,
                    actions={
                        "Cog": self.__class__.__name__,
                        "command": ctx.message,
                        "Message": self.STRINGS["log_vm_parent_added"].format(
                                author=ctx.author.mention,
                                channel=new_vm_parent_channel.name,
                                channel_id=new_vm_parent_channel.id
                        )
                    }
                )
            elif is_a_parent:
                # This already exists as a parent
                await ctx.channel.send(self.STRINGS['error_already_set_parent'])
            elif is_a_child:
                # This is a child VC
                await ctx.channel.send(self.STRINGS['error_already_set_child'])
            elif not is_voice_channel:
                # This is not a VC ID
                await ctx.channel.send(self.STRINGS['error_bad_id'])

        else:
            # Invalid input
            if not given_channel_id:
                await ctx.channel.send(self.STRINGS['error_no_id'])
            else:
                await ctx.channel.send(self.STRINGS['error_bad_id_format'])

    @command_group.command(name="getparents", aliases=["getvmparents"])
    @commands.has_permissions(administrator=True)
    async def getvmparents(self, ctx):
        """
        Get a list of the current voice channels set as parent voice channels.
        :param ctx: The context of the command.
        """
        parent_vm_exists = DBGatewayActions().list(VoicemasterMaster, guild_id=ctx.author.guild.id)

        if parent_vm_exists:
            parent_vm_str = str()
            for record in parent_vm_exists:
                parent_vm_str += f"{self.bot.get_channel(record.channel_id).name} - {record.channel_id}\n"
            await ctx.channel.send(self.STRINGS['show_current_vcs'].format(parent_vms=parent_vm_str))
        else:
            await ctx.channel.send(self.STRINGS['error_no_vms'])

    @command_group.command(name="removeparent", aliases=["removevmparent"])
    @commands.has_permissions(administrator=True)
    async def removevmmaster(self, ctx, given_channel_id=None):
        """
        Remove a voice channel from being a parent voice channel.
        :param ctx: The context of the command.
        :param given_channel_id: The ID of the voice channel to remove from being a parent voice channel.
        """
        if given_channel_id:
            channel_exists = DBGatewayActions().get(
                VoicemasterMaster,
                guild_id=ctx.author.guild.id,
                channel_id=given_channel_id
            )
            if channel_exists:
                DBGatewayActions().delete(channel_exists)
                await ctx.channel.send(self.STRINGS['success_vm_unset'])
                removed_vm_parent = self.bot.get_channel(given_channel_id)
                await self.bot.admin_log(
                    responsible_user=ctx.author,
                    guild_id=ctx.guild.id,
                    actions={
                        "Cog": self.__class__.__name__,
                        "command": ctx.message,
                        "Message": self.STRINGS['log_vm_parent_removed'].format(
                            mention=ctx.author.guild.id,
                            channel_name=removed_vm_parent.name,
                            channel_id=removed_vm_parent.id
                         )
                    }
                )
            else:
                await ctx.channel.send(self.STRINGS['error_not_vm'])
        else:
            await ctx.channel.send(self.STRINGS['error_no_id'])

    @command_group.command(name="removeallparents")
    @commands.has_permissions(administrator=True)
    async def removeallparents(self, ctx):
        """
        Remove all the current parent voice channels from the current server.
        :param ctx: The context of the command.
        """
        all_vm_parents = DBGatewayActions().list(VoicemasterMaster, guild_id=ctx.author.guild.id)
        for vm_parent in all_vm_parents:
            DBGatewayActions().delete(vm_parent)
        await ctx.channel.send(self.STRINGS['success_vm_parents_cleared'])
        await self.bot.admin_log(
            responsible_user=ctx.author,
            guild_id=ctx.guild.id,
            actions={
                "Cog": self.__class__.__name__,
                "command": ctx.message,
                "Message": self.STRINGS['log_vm_parents_cleared'].format(mention=ctx.author.mention)
            }
        )

    @command_group.command(name="removeallchildren")
    @commands.has_permissions(administrator=True)
    async def removeallchildren(self, ctx):
        """
        Delete all the child voice channels, no matter if there are users in them or not.
        :param ctx: THe context of the command.
        """
        all_vm_children = DBGatewayActions().list(VoicemasterSlave, guild_id=ctx.author.guild.id)
        for vm_child in all_vm_children:
            vm_child_channel = self.bot.get_channel(vm_child.channel_id)
            if vm_child_channel:
                await vm_child_channel.delete()
            DBGatewayActions().delete(vm_child)
        await ctx.channel.send(self.STRINGS['success_vm_children_cleared'])
        await self.bot.admin_log(
            responsible_user=ctx.author,
            guild_id=ctx.guild.id,
            actions={
                "Cog": self.__class__.__name__,
                "command": ctx.message,
                "Message": self.STRINGS['log_vm_children_cleared'].format(mention=ctx.author.mention)
            }
        )

    @command_group.command(name="lock", aliases=["lockvm"])
    async def lockvm(self, ctx):
        """
        Locks a child voice channel to the current number of users. This command can only be run by the owner of the child
        voice channel.
        :param ctx: The context of the command.
        """
        if not ctx.author.voice:
            await ctx.channel.send(self.STRINGS['error_not_in_vm_child'])
            return
        in_vm_child = DBGatewayActions().get(
            VoicemasterSlave,
            guild_id=ctx.author.guild.id,
            channel_id=ctx.author.voice.channel.id
        )

        if in_vm_child:
            if in_vm_child.owner_id == ctx.author.id:
                if not in_vm_child.locked:
                    in_vm_child.locked = True
                    DBGatewayActions().update(in_vm_child)
                    await ctx.author.voice.channel.edit(user_limit=len(ctx.author.voice.channel.members))
                    await ctx.channel.send(self.STRINGS['success_child_locked'])
                    await self.bot.admin_log(
                        responsible_user=ctx.author,
                        guild_id=ctx.guild.id,
                        actions={
                            "Cog": self.__class__.__name__,
                            "command": ctx.message,
                            "Message": self.STRINGS["log_child_locked"].format(mention=ctx.author.mention)
                        }
                    )
                else:
                    await ctx.channel.send(self.STRINGS['error_already_locked'])
            else:
                await ctx.channel.send(self.STRINGS['error_not_owned'])
        else:
            await ctx.channel.send(self.STRINGS['error_not_in_vm_child'])

    @command_group.command(name="unlock", aliases=["unlockvm"])
    async def unlockvm(self, ctx):
        """
        Stops the restriction on the number of users allowed in a child voice channel. This command can only be run by the
        owner of the child voice channel.
        :param ctx: The context of the command.
        """
        if not ctx.author.voice:
            await ctx.channel.send(self.STRINGS['error_not_in_vm_child'])
            return
        in_vm_child = DBGatewayActions().get(
            VoicemasterSlave,
            guild_id=ctx.author.guild.id,
            channel_id=ctx.author.voice.channel.id
        )

        if in_vm_child:
            if in_vm_child.owner_id == ctx.author.id:
                if in_vm_child.locked:
                    in_vm_child.locked = False
                    DBGatewayActions().update(in_vm_child)
                    await ctx.author.voice.channel.edit(user_limit=0)
                    await ctx.channel.send(self.STRINGS['success_child_unlocked'])
                    await self.bot.admin_log(
                        responsible_user=ctx.author,
                        guild_id=ctx.guild.id,
                        actions={
                            "Cog": self.__class__.__name__,
                            "command": ctx.message,
                            "Message": self.STRINGS["log_child_unlocked"].format(mention=ctx.author.mention)
                        }
                    )
                else:
                    await ctx.channel.send(self.STRINGS['error_already_unlocked'])
            else:
                await ctx.channel.send(self.STRINGS['error_not_owned'])
        else:
            await ctx.channel.send(self.STRINGS['error_not_in_vm_child'])

    @command_group.command(name="rename", aliases=["renamevm"])
    async def renamevm(self, ctx):
        """
        Sets the name of the voice channel to the string given after the command. If no string is given, the name is set back
        to the default name of a voicemaster child channel.
        :param ctx: The context of the command.
        """
        if not ctx.author.voice:
            await ctx.channel.send(self.STRINGS['error_not_in_vm_child'])
            return
        in_vm_child = DBGatewayActions().get(
            VoicemasterSlave,
            guild_id=ctx.author.guild.id,
            channel_id=ctx.author.voice.channel.id
        )

        command_invoke_string_index = ctx.message.content.index(ctx.invoked_with) + len(ctx.invoked_with)
        new_name = ctx.message.content[command_invoke_string_index:].strip()

        if not self.check_vm_name(new_name):
            await ctx.channel.send(self.STRINGS['error_bad_vm_name'])
            await ctx.message.delete()
            await self.bot.admin_log(
                responsible_user=ctx.author,
                guild_id=ctx.guild.id,
                actions={
                    "Cog": self.__class__.__name__,
                    "Message": f"The user {ctx.author.mention} tried to rename a voice channel using banned words.",
                    "Attempted Rename": f"Hidden for safety: ||{new_name}||"
                }
            )
            return

        if in_vm_child:
            if in_vm_child.owner_id == ctx.author.id:
                if new_name:
                    await ctx.author.voice.channel.edit(name=new_name)
                    in_vm_child.custom_name = True
                    set_name = new_name
                else:
                    await ctx.author.voice.channel.edit(name=f"{ctx.author.display_name}'s VC")
                    in_vm_child.custom_name = False
                    set_name = f"{ctx.author.display_name}'s VC"
                await self.bot.admin_log(
                    responsible_user=ctx.author,
                    guild_id=ctx.guild.id,
                    actions={
                        "Cog": self.__class__.__name__,
                        "command": ctx.message,
                        "Message": self.STRINGS["log_child_renamed"].format(mention=ctx.author.mention,
                                                                            new_name=set_name)
                    }
                )
                DBGatewayActions().update(in_vm_child)
            else:
                await ctx.channel.send(self.STRINGS['error_not_owned'])
        else:
            await ctx.channel.send(self.STRINGS['error_not_in_vm_child'])

    def check_vm_name(self, vm_name):
        hidden_chars = r"[\s​   ﻿]*"
        removed_hidden = re.sub(hidden_chars, "", vm_name)
        leet_word = self.simple_leet_translation(removed_hidden)
        for bad_word in self.banned_words:
            if bad_word in leet_word or bad_word in removed_hidden:
                return False
        return True

    @staticmethod
    def simple_leet_translation(word):
        characters = {
            "a": ["4", "@"],
            "b": ["8", "ß", "l3"],
            "e": ["3"],
            "g": ["6"],
            "i": ["1", "!"],
            "r": ["2"],
            "s": ["5"],
            "t": ["7", "+"],
            "": ["_", "-", "'", "|", "~", "\""]
        }

        translated = word
        for character, replaces in characters.items():
            for i in replaces:
                translated = translated.replace(i, character)

        return translated


def setup(bot):
    bot.add_cog(VoicemasterCog(bot))
