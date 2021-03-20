import urllib.parse
from bs4 import BeautifulSoup
import re
from youtubesearchpython import VideosSearch

import requests
from discord import Message
from discord.ext import commands
from discord.ext.commands import Context

from src.esportsbot.db_gateway import db_gateway


class MusicCog(commands.Cog):

    def __init__(self, bot, max_search_results=100):
        print("Loaded music module")
        self._bot = bot
        self._max_results = max_search_results

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
    async def getmusicchannel(self, ctx):
        current_channel_for_guild = db_gateway().get('music_channels', params={
            'guild_id': ctx.author.guild.id})

        if current_channel_for_guild[0].get('channel_id'):
            id_as_channel = [x for x in ctx.guild.channels if x.id == current_channel_for_guild[0].get('channel_id')][0]
            await ctx.channel.send(f"Music channel is set to {id_as_channel.mention}")
        else:
            await ctx.channel.send("Music channel has not been set")

    async def find_song(self, message: Message):

        if message.content.startswith(self._bot.command_prefix):
            # Ignore commands
            return

        if self.__determine_url(message.content):
            # Download the url directly...
            return
        else:
            # Search for the string on youtube
            youtube_results = self.__search_youtube(message.content)

    def __search_youtube(self, message: str):
        results = VideosSearch(message, limit=self._max_results).result().get('result')

        music_results = []

        # Get results that have words "lyric" or "audio" as it filters out music videos
        for result in results:
            title_lower = result.get('title').lower()
            if 'lyric' in title_lower or 'audio' in title_lower:
                music_results.append(result)

        # Sort the list by view count
        sorted_results = sorted(music_results,
                                key=lambda k: int(k['viewCount']['text'].replace(' views', '').replace(',', '')),
                                reverse=True)

        return sorted_results

    def __determine_url(self, string: str):
        re_string = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+] |[!*\(\), ]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        found_urls = re.findall(re_string, string)

        if len(found_urls) > 0:
            # url is present in the string
            return True
        return False


def setup(bot):
    bot.add_cog(MusicCog(bot))
