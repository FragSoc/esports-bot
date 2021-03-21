import asyncio
import os
import time

import youtube_dl
import re
from youtubesearchpython import VideosSearch

from discord import Message, VoiceClient, FFmpegPCMAudio
from discord.ext import commands, tasks
from discord.ext.commands import Context, UserInputError

from src.esportsbot.db_gateway import db_gateway


class MusicCog(commands.Cog):

    def __init__(self, bot, max_search_results=100):
        print("Loaded music module")
        self._bot = bot
        self._max_results = max_search_results
        self._song_location = 'songs\\'
        self._currently_active = {}
        self._marked_channels = {}

        self.check_active_channels.start()
        self.check_marked_channels.start()

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setmusicchannel(self, ctx: Context, given_channel_id=None):
        if given_channel_id is None:
            # No given channel id.. exit
            raise UserInputError(message="A channel id is a required argument")

        is_valid_channel_id = (len(given_channel_id) == 18) and given_channel_id.isdigit()

        if not is_valid_channel_id:
            # The channel id given is not valid.. exit
            raise UserInputError(message="The id given was not a valid id")

        guild_text_channel_ids = [str(x.id) for x in ctx.guild.text_channels]

        if str(given_channel_id) not in guild_text_channel_ids:
            # The channel id given not for a text channel.. exit
            raise UserInputError(message="The id given must be of a text channel")

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

    @commands.command()
    async def removesong(self, ctx: Context, song_index=None):
        if not self.__check_valid_user_vc(ctx):
            return

        if len(self._currently_active.get(ctx.guild.id).get('queue')) < int(song_index):
            # Index out of bounds
            return

        self._currently_active[ctx.guild.id]['queue'].pop(int(song_index))

    @commands.command()
    async def pausesong(self, ctx: Context):
        if not self.__check_valid_user_vc(ctx):
            # Checks if the user is in a valid voice channel
            return

        self.__pause_song(ctx.guild.id)

    @commands.command()
    async def resumesong(self, ctx: Context):
        if not self.__check_valid_user_vc(ctx):
            # Checks if the user is in a valid voice channel
            return

        self.__resume_song(ctx.guild.id)

    @commands.command()
    async def kickbot(self, ctx: Context):
        if not self.__check_valid_user_vc(ctx):
            # Checks if the user is in a valid voice channel
            return

        await self.__remove_active_channel(ctx.guild.id)

    @commands.command()
    async def skip(self, ctx: Context):
        if not self.__check_valid_user_vc(ctx):
            # Checks if the user is in a valid voice channel
            return

        if len(self._currently_active.get(ctx.guild.id).get('queue')) == 1:
            # Skipping when only one song in the queue will just kick the bot
            await self.__remove_active_channel(ctx.guild.id)
            return

        self.check_next_song(ctx.guild.id)

    @commands.command()
    async def listqueue(self, ctx: Context):
        if not self.__check_valid_user_vc(ctx):
            # Checks if the user is in a valid voice channel
            return

        await ctx.channel.send(str(self._currently_active.get(ctx.guild.id).get('queue')))

    async def on_message_handle(self, message: Message):
        if message.content.startswith(self._bot.command_prefix):
            # Ignore commands, any MusicCog commands will get handled in the usual way
            return

        if not message.author.voice:
            # User is not in a voice channel.. exit
            return

        if not self._currently_active.get(message.guild.id):
            # We aren't in a voice channel in the given guild
            voice_client = await message.author.voice.channel.connect()
            self.__add_new_active_channel(message.guild.id, voice_client=voice_client,
                                          channel_id=message.author.voice.channel.id)
        else:
            if self._currently_active.get(message.guild.id).get('channel_id') != message.author.voice.channel.id:
                # The bot is already in a different channel
                return

        if message.guild.id in self._marked_channels:
            # Remove the channel from marked channels as it is no longer inactive
            self._marked_channels.pop(message.guild.id)

        song_data = self.find_song(message.content)

        self._currently_active[message.guild.id]['queue'].append(song_data)

        if not self._currently_active.get(message.guild.id).get('voice_client').is_playing():
            # If we are not currently playing, start playing
            self.__start_queue(message.guild.id)

    async def __remove_active_channel(self, guild_id) -> bool:
        if guild_id in self._currently_active:
            voice_client: VoiceClient = self._currently_active.get(guild_id).get('voice_client')
            await voice_client.disconnect()
            self._currently_active.pop(guild_id)
            return True
        return False

    def find_song(self, search_term) -> dict:
        if self.__determine_url(search_term):
            # Currently only supports youtube links
            # Searching youtube with the video id gets the original video
            # Means we can have the same data is if it were searched for by name
            search_term = search_term.split('v=')[-1]

        youtube_results = self.__search_youtube(search_term)

        if len(youtube_results) > 0:
            self.__download_video(youtube_results[0])

            return youtube_results[0]
        else:
            return {}

    def __search_youtube(self, message: str) -> list:
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

    def __clean_youtube_results(self, results) -> list:
        cleaned_data = []

        # Gets the data that is actually useful and discards the rest of the data
        for result in results:
            new_result = {'title': result.get('title'),
                          'thumbnail': result.get('thumbnails')[-1],
                          'link': result.get('link'),
                          'id': result.get('id'),
                          'viewCount': result.get('viewCount'),
                          'duration': result.get('duration')
                          }
            new_result['localfile'] = self._song_location + "" + new_result.get('title') + '-' + new_result.get('id') \
                                      + '.mp3'

            cleaned_data.append(new_result)

        return cleaned_data

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

    def __add_new_active_channel(self, guild_id, channel_id=None, voice_client=None) -> bool:
        if guild_id not in self._currently_active:
            self._currently_active[guild_id] = {}
            self._currently_active[guild_id]['channel_id'] = channel_id
            self._currently_active[guild_id]['voice_client'] = voice_client
            self._currently_active[guild_id]['queue'] = []
            return True
        return False

    def __start_queue(self, guild_id):
        if len(self._currently_active.get(guild_id).get('queue')) < 1:
            # Queue is empty
            return

        voice_client: VoiceClient = self._currently_active.get(guild_id).get('voice_client')

        if voice_client.is_playing():
            # Stop the bot if it is playing
            voice_client.stop()

        song_file = self._currently_active.get(guild_id).get('queue')[0].get('localfile')
        voice_client.play(FFmpegPCMAudio(song_file))
        voice_client.volume = 100

    def __pause_song(self, guild_id):
        if self._currently_active.get(guild_id).get('voice_client').is_playing():
            # Can't pause if the bot isn't playing
            voice_client: VoiceClient = self._currently_active.get(guild_id).get('voice_client')
            voice_client.pause()

    def __resume_song(self, guild_id):
        if not self._currently_active.get(guild_id).get('voice_client').is_paused():
            # Can't resume if the bot isn't paused
            voice_client: VoiceClient = self._currently_active.get(guild_id).get('voice_client')
            voice_client.resume()

    def __check_valid_user_vc(self, ctx: Context):
        music_channel_in_db = db_gateway().get('music_channels', params={'guild_id': ctx.guild.id})
        if ctx.message.channel.id != music_channel_in_db[0].get('channel_id'):
            # Message is not in the songs channel
            return False

        if not ctx.author.voice:
            # User is not in a voice channel
            return False

        if self._currently_active.get(ctx.guild.id).get('channel_id') != ctx.author.voice.channel.id:
            # The user is not in the same voice channel as the bot
            return False

        return True

    def __determine_url(self, string: str) -> bool:
        # This is for matching all urls
        # re_string = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+] |[!*\(\), ]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        # As we only want to match actual youtube urls
        re_string = r'(http[s]?://)?youtube.com/watch\?v='
        found_urls = re.findall(re_string, string)

        if len(found_urls) > 0:
            # url is present in the string
            return True
        return False

    @tasks.loop(seconds=1)
    async def check_active_channels(self):
        # Create a copy to avoid concurrent changes to _currently_active
        active_copy = self._currently_active.copy()
        for guild_id in active_copy.keys():
            if not self._currently_active.get(guild_id).get('voice_client').is_playing():
                # Check any voice_clients that are no longer playing
                self.check_next_song(guild_id)

    @tasks.loop(seconds=60)
    async def check_marked_channels(self):
        # Create a copy to avoid concurrent changes to _marked_channels
        marked_copy = self._marked_channels.copy()
        for guild_id in marked_copy.keys():
            guild_time = self._marked_channels.get(guild_id)
            if time.time() - guild_time >= 60 * 5:
                # If the time since inactivity has been more than 5 minutes leave the channel
                asyncio.create_task(self.__remove_active_channel(guild_id))
                self._marked_channels.pop(guild_id)

    def check_next_song(self, guild_id):
        if len(self._currently_active.get(guild_id).get('queue')) == 1:
            # The queue will be empty so will be marked as inactive
            self._currently_active.get(guild_id).get('queue').pop(0)
            self._marked_channels[guild_id] = time.time()
        elif len(self._currently_active.get(guild_id).get('queue')) > 1:
            # The queue is not empty, play the next song
            self._currently_active.get(guild_id).get('queue').pop(0)
            self.__start_queue(guild_id)

    def make_queue_list(self, guild_id):
        pass


def setup(bot):
    bot.add_cog(MusicCog(bot))
