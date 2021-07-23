from discord.ext import commands
from esportsbot.base_functions import send_to_log_channel
import os

devs = os.getenv("DEV_IDS").replace(" ", "").split(",")


class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.STRINGS = bot.STRINGS["admin"]

    def is_dev(ctx):
        if not devs:
            return ctx.author.guild_permissions.administrator
        return str(ctx.author.id) in devs

    @commands.command(
        name="clear_messages",
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
        await send_to_log_channel(
            self,
            ctx.author.guild.id,
            self.STRINGS['channel_cleared'].format(author_mention=ctx.author.mention,
                                                   message_amount=amount)
        )

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
    @commands.command(name="remove-cog")
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
    @commands.command(name="add-cog")
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
    @commands.command(name="reload-cog")
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


def setup(bot):
    bot.add_cog(AdminCog(bot))
