import os
from datetime import datetime

from discord import Member, TextChannel, CategoryChannel, PermissionOverwrite, Embed, Color
from discord.ext import commands

devs = os.getenv("DEV_IDS").replace(" ", "").split(",")


class AdminCog(commands.Cog):
    """
    Adds a few commands useful for admin operations.

    This module makes use of a custom command check for if the user is a develop of the bot. Dev users are defined in the
    *.env file.
    """
    def __init__(self, bot):
        self.bot = bot
        self.STRINGS = bot.STRINGS["admin"]

        # Get bot version from text file
        try:
            version_file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "version.txt")
            with open(version_file_path, "rt") as version_file:
                self.bot_version = "`" + version_file.readline().strip() + "`"
        except FileNotFoundError:
            self.bot_version = self.STRINGS['no_version']

    def is_dev(ctx):
        """
        The command check used to check if a user executing the command is a developer of the bot.
        :return:
        """
        if not devs:
            return ctx.author.guild_permissions.administrator
        return str(ctx.author.id) in devs

    @commands.group(name="admin")
    @commands.has_permissions(administrator=True)
    async def admin_group(self, context):
        pass

    @commands.group(name="dev")
    @commands.check(is_dev)
    async def dev_group(self, context):
        pass

    @admin_group.command(
        name="clear",
        aliases=['cls',
                 'purge',
                 'delete',
                 'Cls',
                 'Purge',
                 'Delete']
    )
    async def clear_messages(self, ctx, amount=5):
        """
        Clears the given number of messages from the current channel. If no number is given, this command will delete 5
        messages.
        :param ctx: The context of the command.
        :param amount: The number of messages to delete.
        """
        await ctx.channel.purge(limit=int(amount) + 1)
        await self.bot.admin_log(
            responsible_user=ctx.author,
            guild_id=ctx.guild.id,
            actions={
                "command": ctx.message,
                "Message": self.STRINGS["channel_cleared"].format(author_mention=ctx.author.mention,
                                                                  message_amount=amount)
            }
        )

    @dev_group.command(name="version", hidden=True)
    async def print_version(self, ctx):
        """
        Get the version the bot is running on.
        :param ctx: The context of the command.
        """
        await ctx.channel.send(self.bot_version)

    @admin_group.command(
        name="members",
        aliases=['Members']
    )
    async def members(self, ctx):
        """
        Get the number of members in the current server.
        :param ctx: The context of the command.
        """
        await ctx.channel.send(self.STRINGS['members'].format(member_count=ctx.guild.member_count))

    @admin_group.command(name="user-info", aliases=["info", "get-user", "user"])
    async def get_user_info(self, context, user: Member):
        user_embed = Embed(
            title=f"{user.name} — User Info",
            description=f"Showing the user info for {user.mention}\n",
            colour=Color.random()
        )

        user_embed.add_field(name="​", value=f"• Pending Status? `{user.pending}`", inline=False)
        user_embed.add_field(name="​", value=f"• Current Display Name — {user.display_name}", inline=False)
        user_embed.add_field(name="​", value=f"• Date Joined — {user.joined_at.strftime('%m/%d/%Y, %H:%M:%S')}", inline=False)
        user_embed.add_field(name="​", value=f"• Account Creation Date — {user.created_at.strftime('%m/%d/%Y, %H:%M:%S')}", inline=False)

        user_embed.set_thumbnail(url=user.default_avatar_url)

        user_embed.set_footer(text=datetime.now().strftime("%m/%d/%Y, %H:%M:%S"))

        await context.send(embed=user_embed)

    @dev_group.command(name="remove-cog", hidden=True)
    async def remove_cog(self, context: commands.Context, cog_name: str):
        """
        Unloads a cog. This removes all commands/functionality associated with that cog until the bot is restarted.
        :param context: The context of the command.
        :param cog_name: The name of the cog to disable.
        """
        if "AdminCog" in cog_name:
            return
        try:
            package = "esportsbot.cogs."
            if package not in cog_name:
                self.bot.unload_extension(package + cog_name)
            else:
                self.bot.unload_extension(cog_name)
            await context.send(f"Unloaded cog with name `{cog_name}`")
        except commands.ExtensionNotFound:
            await context.send(f"There is no cog with the name `{cog_name}`.")
        except commands.ExtensionNotLoaded:
            await context.send(f"The cog with name `{cog_name}` is not loaded.")

    @dev_group.command(name="add-cog", hidden=True)
    async def add_cog(self, context: commands.Context, cog_name: str):
        """
        Loads a cog. This adds a cogs commands/functionality to the bot dynamically. This lasts until the bot is restarted.
        If a cog makes use of `on_ready` it will not run, which can cause issues for those that load data in that method.
        :param context: The context of the command.
        :param cog_name: The name of the cog to enable.
        """
        if "AdminCog" in cog_name:
            return
        try:
            package = "esportsbot.cogs."
            if package not in cog_name:
                self.bot.load_extension(package + cog_name)
            else:
                self.bot.load_extension(cog_name)
            await context.send(f"Loaded cog with name `{cog_name}`")
        except commands.ExtensionNotFound:
            await context.send(f"There is no cog with the name `{cog_name}`.")
        except commands.ExtensionAlreadyLoaded:
            await context.send(f"The cog with name `{cog_name}` is already loaded.")

    @dev_group.command(name="reload-cog", hidden=True)
    async def reload_cog(self, context: commands.Context, cog_name: str):
        """
        Reload a cog. Firsts unloads, then loads the cog. If a cog makes use of `on_ready` it will not run, which can cause
        issues for those that load data in that method.
        :param context: The context of the command.
        :param cog_name: The name of the command to reload.
        """
        try:
            package = "esportsbot.cogs."
            if package not in cog_name:
                self.bot.reload_extension(package + cog_name)
            else:
                self.bot.reload_extension(cog_name)
            await context.send(f"Reloaded cog with name `{cog_name}`")
        except commands.ExtensionNotFound:
            await context.send(f"There is no cog with the name `{cog_name}`.")
        except commands.ExtensionNotLoaded:
            await context.send(f"The cog with name `{cog_name}` is not loaded.")

    @admin_group.command(name="set-rep")
    async def set_rep_perms(self, context: commands.Context, user: Member, *args):
        """
        Sets the permissions for a game rep given a list of category or channel ids.
        :param context: The context of the command.
        :param user: The user to give the permissions to.
        """

        channel_names = []

        for category in args:
            try:
                category_id = int(category)
                discord_category = context.guild.get_channel(category_id)
                if not discord_category:
                    discord_category = await self.bot.fetch_channel(category_id)
                # First remove any existing reps/overwrites.
                await self.remove_user_permissions(discord_category)
                # Then add the new user's permissions.
                if await self.set_rep_permissions(user, discord_category):
                    channel_names.append(discord_category.name)
            except ValueError:
                continue

        response_string = str(channel_names).replace("[", "").replace("]", "").strip()
        await context.send(
            f"Successfully set the permissions for `{user.display_name}#{user.discriminator}` "
            f"in the following channels/categories: `{response_string}`"
        )

    async def remove_user_permissions(self, guild_channel):
        """
        Removes permission overrides that are for specific users for a given GuildChannel.
        :param guild_channel: The channel to remove any user-based permission overrides.
        :return True if any user-based permissions were removed, False if this process failed.
        """
        if not await self.check_editable(guild_channel):
            return False

        for permission_group in guild_channel.overwrites:
            if isinstance(permission_group, Member):
                await guild_channel.set_permissions(target=permission_group, overwrite=None)

        # If the channel provided is category, go through the channels inside the category and remove the permissions.
        if not isinstance(guild_channel, CategoryChannel):
            return True

        for channel in guild_channel.channels:
            await self.remove_user_permissions(channel)

        return True

    async def set_rep_permissions(self, user, guild_channel):
        """
        Sets the permissions of a user to those that a rep would need in the given category/channel.
        :param user: The user to give the permissions to.
        :param guild_channel: The GuildChannel to set the permissions of.
        :return True if the permissions were set for the given user, False otherwise.
        """
        if not await self.check_editable(guild_channel):
            return False

        overwrite = PermissionOverwrite(
            view_channel=True,
            manage_channels=True,
            manage_permissions=True,
            send_messages=True,
            manage_messages=True,
            connect=True,
            speak=True,
            mute_members=True,
            deafen_members=True,
            move_members=True,
        )
        await guild_channel.set_permissions(target=user, overwrite=overwrite)

        # If the channel provided is a category, ensure that the rep can type in any announcement channels.
        if not isinstance(guild_channel, CategoryChannel):
            return True

        for channel in guild_channel.channels:
            if isinstance(channel, TextChannel) and channel.is_news():
                await channel.set_permissions(target=user, send_messages=True)

        return True

    @staticmethod
    async def check_editable(guild_channel):
        """
        Checks if the bot has permission to edit the permissions of a channel.
        :param guild_channel: The channel to check the permissions of.
        :return: True if the bot is able to edit the permissions of the channel, else False.
        """
        bot_perms = guild_channel.permissions_for(guild_channel.guild.me)
        bot_overwrites = guild_channel.overwrites_for(guild_channel.guild.me)
        if not bot_perms.manage_permissions:
            return False
        # Explicitly check for False, as None means no overwrite.
        if bot_overwrites.manage_permissions is False:
            return False
        return True


def setup(bot):
    bot.add_cog(AdminCog(bot))
