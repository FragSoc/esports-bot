import os

from discord import Member, TextChannel, CategoryChannel, PermissionOverwrite
from discord.ext import commands

devs = os.getenv("DEV_IDS").replace(" ", "").split(",")


class AdminCog(commands.Cog):
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
        if not devs:
            return ctx.author.guild_permissions.administrator
        return str(ctx.author.id) in devs

    @commands.command(
        name="clear",
        aliases=['cls',
                 'purge',
                 'delete',
                 'Cls',
                 'Purge',
                 'Delete'],
        usage="<number_of_messages>",
        help="Clears the specified number of messages from the channel. Default value of 5."
    )
    @commands.has_permissions(manage_messages=True)
    async def clear_messages(self, ctx, amount=5):
        await ctx.channel.purge(limit=int(amount) + 1)
        await self.bot.adminLog(
            ctx.message,
            {
                "Cog": str(type(self)),
                "Message": self.STRINGS['channel_cleared'].format(author_mention=ctx.author.mention,
                                                                  message_amount=amount)
            }
        )

    @commands.check(is_dev)
    @commands.command(name="version", help="Print the bot's version string", hidden=True)
    async def print_version(self, ctx):
        await ctx.channel.send(self.bot_version)

    @commands.command(
        name="members",
        aliases=['Members'],
        usage="",
        help="Calculates the number of members in the current server"
    )
    @commands.has_permissions(manage_messages=True)
    async def members(self, ctx):
        await ctx.channel.send(self.STRINGS['members'].format(member_count=ctx.guild.member_count))

    @commands.check(is_dev)
    @commands.command(name="remove-cog", hidden=True)
    async def remove_cog(self, context: commands.Context, cog_name: str):
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

    @commands.check(is_dev)
    @commands.command(name="add-cog", hidden=True)
    async def add_cog(self, context: commands.Context, cog_name: str):
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

    @commands.check(is_dev)
    @commands.command(name="reload-cog", hidden=True)
    async def reload_cog(self, context: commands.Context, cog_name: str):
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

    @commands.has_permissions(administrator=True)
    @commands.command(name="set-rep")
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
        await context.send(f"Successfully set the permissions for `{user.display_name}#{user.discriminator}` "
                           f"in the following channels/categories: `{response_string}`")

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
