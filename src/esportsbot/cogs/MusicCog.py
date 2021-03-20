import os

import youtube_dl
import re
from youtubesearchpython import VideosSearch

from discord import Message
from discord.ext import commands
from discord.ext.commands import Context, CommandNotFound, MissingRequiredArgument

from src.esportsbot.db_gateway import db_gateway


class MusicCog(commands.Cog):

    def __init__(self, bot, max_search_results=100):
        print("Loaded music module")
        self._bot = bot
        self._max_results = max_search_results
        self._song_location = 'songs\\'

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setmusicchannel(self, ctx: Context, given_channel_id=None):
        if given_channel_id is None:
            # No given channel id.. exit
            raise MissingRequiredArgument("No id was given when setting the music channel id")

        is_valid_channel_id = (len(given_channel_id) == 18) and given_channel_id.isdigit()

        if not is_valid_channel_id:
            # The channel id given is not valid.. exit
            raise MissingRequiredArgument("The id given to set the music channel was not valid")

        guild_text_channel_ids = [str(x.id) for x in ctx.guild.text_channels]

        if str(given_channel_id) not in guild_text_channel_ids:
            # The channel id given not for a text channel.. exit
            raise MissingRequiredArgument("The id given to set the music channel was not a text channel")

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

        search = message.content
        if self.__determine_url(search):
            # Currently only supports youtube links
            # Searching youtube with the video id gets the original video
            # Means we can have the same data is if it were searched for by name
            search = message.content.split('v=')[-1]

        youtube_results = self.__search_youtube(search)

        if len(youtube_results) > 0:
            self.__download_video(youtube_results[0])

            await message.channel.send(youtube_results[0].get('link'))
        else:
            await message.channel.send("Unable to find " + message.content)

    def __search_youtube(self, message: str):
        results = VideosSearch(message, limit=self._max_results).result().get('result')

        music_results = []

        # Get results that have words "lyric" or "audio" as it filters out music videos
        for result in results:
            title_lower = result.get('title').lower()
            if 'lyric' in title_lower or 'audio' in title_lower:
                music_results.append(result)

        # Remove useless data
        cleaned_results = self.__clean_youtube_results(music_results)

        # Sort the list by view count
        sorted_results = sorted(cleaned_results,
                                key=lambda k: int(k['viewCount']['text'].replace(' views', '').replace(',', '')),
                                reverse=True)

        return sorted_results

    def __clean_youtube_results(self, results):
        cleaned_data = []

        # Gets the data that is actually useful and discards the rest of the data
        for result in results:
            new_result = {'title': result.get('title'),
                          'duration': result.get('duration'),
                          'thumbnail': result.get('thumbnails')[-1],
                          'link': result.get('link'),
                          'id': result.get('id'),
                          'viewCount': result.get('viewCount')}
            new_result['localfile'] = self._song_location + "" + new_result.get('title') + '-' + new_result.get('id') \
                                      + '.mp3'

            cleaned_data.append(new_result)

        return cleaned_data

    def __determine_url(self, string: str):
        # This is for matching all urls
        # re_string = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+] |[!*\(\), ]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        # As we only want to match actual youtube urls
        re_string = r'(http[s]?://)?youtube.com/watch\?v='
        found_urls = re.findall(re_string, string)

        if len(found_urls) > 0:
            # url is present in the string
            return True
        return False

    def __download_video(self, video_info):
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': self._song_location + '%(title)s-%(id)s.mp3',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
        url = video_info.get('link')
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            if not os.path.isfile(video_info.get('localfile')):
                ydl.download([url])


def setup(bot):
    bot.add_cog(MusicCog(bot))
