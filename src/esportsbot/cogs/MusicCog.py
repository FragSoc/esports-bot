from discord.ext import commands
from discord.ext.commands import Context

from src.esportsbot.db_gateway import db_gateway


class MusicCog(commands.Cog):

    def __init__(self, bot):
        print("Loaded music module")
        self._bot = bot

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setmusicchannel(self, ctx: Context, given_channel_id=None):
        if given_channel_id is None:
            # No given channel id.. exit
            print("No id given")
            return

        is_valid_channel_id = (len(given_channel_id) == 18) and given_channel_id.isdigit()

        if not is_valid_channel_id:
            # The channel id given is not valid.. exit
            print("invalid id: " + str(given_channel_id))
            return

        guild_text_channel_ids = [str(x.id) for x in ctx.guild.text_channels]

        if str(given_channel_id) not in guild_text_channel_ids:
            # The channel id given not for a text channel.. exit
            print("id is not a text channel")
            return

        current_channel_for_guild = db_gateway().get('music_channels', params={
            'guild_id': ctx.author.guild.id})

        if len(current_channel_for_guild) > 0:
            # There is already a channel set.. update
            db_gateway().update('music_channels', set_params={
                'channel_id': given_channel_id}, where_params={'guild_id': ctx.author.guild.id})
            return

        # Validation checks complete
        db_gateway().insert('music_channels', params={
            'guild_id': ctx.author.guild.id, 'channel_id': given_channel_id})

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def getmusicchannel(self, ctx, *args):
        current_channel_for_guild = db_gateway().get('music_channels', params={
            'guild_id': ctx.author.guild.id})

        if current_channel_for_guild[0]['default_role_id']:
            await ctx.channel.send(f"Music channel is set to {current_channel_for_guild[0]['channel_id']}")
        else:
            await ctx.channel.send("Music channel has not been set")


def setup(bot):
    bot.add_cog(MusicCog(bot))
