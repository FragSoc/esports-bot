import grequests
import asyncio
import os
import time

import youtube_dl
import re
from youtubesearchpython import VideosSearch

from discord import Message, VoiceClient, TextChannel, Embed, Colour, FFmpegOpusAudio
from discord.ext import commands, tasks
from discord.ext.commands import Context, UserInputError

from src.esportsbot.db_gateway import db_gateway

import googleapiclient.discovery
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup as bs

from random import shuffle
from collections import defaultdict

# TODO: Code commenting and cleanup


class EmbedColours:

    @staticmethod
    def green():
        return Colour(0x1f8b4c)

    @staticmethod
    def orange():
        return Colour(0xe67e22)

    @staticmethod
    def red():
        return Colour(0xe74c3c)

    @staticmethod
    def music():
        return Colour(0xd462fd)


class MusicCog(commands.Cog):

    def __init__(self, bot, max_search_results=100):
        print("Loaded music module")
        self._bot = bot
        self._max_results = max_search_results
        self._song_location = 'songs' + os.path.sep
        self._currently_active = {}
        self._marked_channels = {}

        self.__check_loops_alive()

        self._empty_queue_message = "**__Queue list:__**\n" \
                                    "Join a VoiceChannel and search a song by name or YouTube url.\n"

        self._no_current_song_message = Embed(title="No song currently playing",
                                              colour=EmbedColours.music(),
                                              footer="Use the prefix ! for commands"
                                              )
        self._no_current_song_message.set_image(
            url="http://fragsoc.co.uk/wpsite/wp-content/uploads/2020/08/logo1-450x450.png")
        self._no_current_song_message.set_footer(text="Definitely not made by fuxticks#1809 on discord")
        # Bitrate quality 0->2 inclusive, 0 is best, 2 is worst
        self._bitrate_quality = 0

        self._API_KEY = os.getenv('GOOGLE_API_PERSONAL')

        #self._time_allocation = defaultdict(lambda: {'last_time': time.time(), 'used_time': self._allowed_time})
        self._time_allocation = defaultdict(lambda: self._allowed_time)
        # Seconds of song (time / day) / server
        # Currently 2 hours of playtime for each server per day
        self._allowed_time = 7200

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setmusicchannel(self, ctx: Context, args=None, given_channel_id=None):

        if given_channel_id is None and args is not None:
            # No args was given, but a channel id was given
            given_channel_id = args
            args = None

        if given_channel_id is None:
            # No given channel id.. exit
            message = Embed(title="A channel id is a required argument", colour=EmbedColours.red())
            await self.__send_timed_message(ctx.channel, message, timer=30)
            raise UserInputError(message="A channel id is a required argument")

        is_valid_channel_id = (len(given_channel_id) == 18) and given_channel_id.isdigit()

        if not is_valid_channel_id:
            # The channel id given is not valid.. exit
            message = Embed(title="The id given was not a valid id", colour=EmbedColours.red())
            await self.__send_timed_message(ctx.channel, message, timer=30)
            raise UserInputError(message="The id given was not a valid id")

        guild_text_channel_ids = [str(x.id) for x in ctx.guild.text_channels]

        if str(given_channel_id) not in guild_text_channel_ids:
            # The channel id given not for a text channel.. exit
            message = Embed(title="The id given must be of a text channel", colour=EmbedColours.red())
            await self.__send_timed_message(ctx.channel, message, timer=30)
            raise UserInputError(message="The id given must be of a text channel")

        current_channel_for_guild = db_gateway().get('music_channels', params={
            'guild_id': ctx.author.guild.id})

        if len(current_channel_for_guild) > 0:
            # There is already a channel set.. update
            db_gateway().update('music_channels', set_params={
                'channel_id': given_channel_id}, where_params={'guild_id': ctx.author.guild.id})
        else:
            # No channel for guild.. insert
            db_gateway().insert('music_channels', params={
                'channel_id': int(given_channel_id), 'guild_id': int(ctx.author.guild.id)})

        await self.__setup_channel(ctx, int(given_channel_id), args)

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
    @commands.has_permissions(administrator=True)
    async def resetmusicchannel(self, ctx):
        current_channel_for_guild = db_gateway().get('music_channels', params={
            'guild_id': ctx.author.guild.id})

        if current_channel_for_guild[0].get('channel_id'):
            await self.__setup_channel(ctx, arg='-c', channel_id=current_channel_for_guild[0].get('channel_id'))
            message = "Successfully reset the music channel"
            await self.__send_timed_message(ctx.channel, message, timer=20, is_embed=False)
        else:
            await ctx.channel.send("Music channel has not been set")

    @commands.command()
    async def removesong(self, ctx: Context, song_index=None):
        if not self.__check_valid_user_vc(ctx):
            message = Embed(title="You are not in the voice channel with the bot", colour=EmbedColours.orange())
            await self.__send_timed_message(ctx.channel, message)
            return

        if len(self._currently_active.get(ctx.guild.id).get('queue')) < (int(song_index) - 1):
            message = Embed(title=f"There is no song at position {song_index} in the queue",
                            colour=EmbedColours.orange())
            await self.__send_timed_message(ctx.channel, message)
            return

        self._currently_active[ctx.guild.id]['queue'].pop(int(song_index) - 1)
        await self.__update_channel_messages(ctx.guild.id)
        await ctx.message.delete()
        message = Embed(title=f"Removed song at position {song_index} in the queue", colour=EmbedColours.green())
        await self.__send_timed_message(ctx.channel, message)

    @commands.command()
    async def pausesong(self, ctx: Context):
        if not self.__check_valid_user_vc(ctx):
            # Checks if the user is in a valid voice channel
            return

        self.__pause_song(ctx.guild.id)
        await ctx.message.delete()
        message = Embed(title="Song Paused", colour=EmbedColours.music())
        await self.__send_timed_message(ctx.channel, message, timer=20)

    @commands.command()
    async def resumesong(self, ctx: Context):
        if not self.__check_valid_user_vc(ctx):
            # Checks if the user is in a valid voice channel
            return

        self.__resume_song(ctx.guild.id)
        await ctx.message.delete()
        message = Embed(title="Song Resumed", colour=EmbedColours.music())
        await self.__send_timed_message(ctx.channel, message, timer=20)

    @commands.command()
    async def kickbot(self, ctx: Context):
        if not self.__check_valid_user_vc(ctx):
            # Checks if the user is in a valid voice channel
            return

        await self.__remove_active_channel(ctx.guild.id)
        await ctx.message.delete()
        message = Embed(title="I have left the Voice Channel", colour=EmbedColours.music())
        await self.__send_timed_message(ctx.channel, message, timer=20)

    @commands.command()
    async def skipsong(self, ctx: Context):
        if not self.__check_valid_user_vc(ctx):
            # Checks if the user is in a valid voice channel
            return

        if len(self._currently_active.get(ctx.guild.id).get('queue')) == 1:
            # Skipping when only one song in the queue will just kick the bot
            await self.__remove_active_channel(ctx.guild.id)
            await ctx.message.delete()
            return

        await self.__check_next_song(ctx.guild.id)
        await ctx.message.delete()
        message = Embed(title="Song Skipped!", colour=EmbedColours.music(), time=5)
        await self.__send_timed_message(ctx.channel, message)

    @commands.command()
    async def listqueue(self, ctx: Context):
        # if not self.__check_valid_user_vc(ctx):
            # Checks if the user is in a valid voice channel
        #    return

        # We don't want the song channel to be filled with the queue as it already shows it
        music_channel_in_db = db_gateway().get('music_channels', params={'guild_id': ctx.guild.id})
        if ctx.message.channel.id == music_channel_in_db[0].get('channel_id'):
            # Message is in the songs channel
            return

        queue_string = self.__make_queue_list(ctx.guild.id)

        await ctx.channel.send(queue_string)

    @commands.command()
    async def clearqueue(self, ctx: Context):
        if not self.__check_valid_user_vc(ctx):
            # Checks if the user is in a valid voice channel
            return

        if self._currently_active.get(ctx.guild.id).get('voice_client').is_playing():
            # If currently in a song, set the queue to what is currently playing
            self._currently_active.get(ctx.guild.id)['queue'] = [
                self._currently_active.get(ctx.guild.id).get('queue').pop(0)]
        else:
            # Else empty the queue and start the inactivity timer
            self._currently_active.get(ctx.guild.id)['queue'] = [None]
            await self.__check_next_song(ctx.guild.id)

        await self.__update_channel_messages(ctx.guild.id)
        await ctx.message.delete()
        message = Embed(title="Queue Cleared!", colour=EmbedColours.music())
        await self.__send_timed_message(ctx.channel, message)

    @commands.command()
    async def shufflequeue(self, ctx: Context):
        if not self.__check_valid_user_vc(ctx):
            # Checks if the user is in a valid voice channel
            return

        if not len(self._currently_active.get(ctx.guild.id).get('queue')) > 2:
            # Nothing to shuffle
            return

        current_top = self._currently_active.get(ctx.guild.id).get('queue').pop(0)
        shuffle(self._currently_active.get(ctx.guild.id)['queue'])
        self._currently_active.get(ctx.guild.id).get('queue').insert(0, current_top)

        message = Embed(title="Queue shuffled!", colour=EmbedColours.green())
        await self.__send_timed_message(ctx.channel, message, timer=10)
        await ctx.message.delete()

    async def on_message_handle(self, message: Message):
        if message.content.startswith(self._bot.command_prefix):
            # Ignore commands, any MusicCog commands will get handled in the usual way
            return

        if not message.author.voice:
            # User is not in a voice channel.. exit
            send = Embed(title="You must be in a voice channel to add a song", colour=EmbedColours.orange())
            await message.delete()
            await self.__send_timed_message(message.channel, send, timer=10)
            return

        if not self._currently_active.get(message.guild.id):
            # We aren't in a voice channel in the given guild
            voice_client = await message.author.voice.channel.connect()
            self.__add_new_active_channel(message.guild.id, voice_client=voice_client,
                                          channel_id=message.author.voice.channel.id)
        else:
            if self._currently_active.get(message.guild.id).get('channel_id') != message.author.voice.channel.id:
                send = Embed(title="I am already in another voice channel in this server", colour=EmbedColours.orange())
                await message.delete()
                await self.__send_timed_message(message.channel, send, timer=10)
                return

        self.__check_loops_alive()

        split_message = message.content.split("\n")
        total_success = True

        for line in split_message:
            total_success = total_success and await self.process_song_request(message, line)

        if total_success:
            if message.guild.id in self._marked_channels:
                # Remove the channel from marked channels as it is no longer inactive
                self._marked_channels.pop(message.guild.id)

        await message.delete()

    def __check_loops_alive(self):
        if not self.check_active_channels.is_running():
            self.check_active_channels.start()
        if not self.check_marked_channels.is_running():
            self.check_marked_channels.start()
        if not self.reset_music_allowance.is_running():
            self.reset_music_allowance.start()

    def __create_time_remaining_field(self, guild_id, embed):
        guild_time = self._time_allocation[guild_id]
        # remain_time = guild_time.get('used_time')
        seconds_remain = str(guild_time % 60)
        if len(seconds_remain) == 1:
            seconds_remain += '0'

        allowed_time = self._allowed_time
        seconds_allowed = str(self._allowed_time % 60)
        if len(seconds_allowed) == 1:
            seconds_allowed += '0'
        embed.add_field(name=f"Minutes Remaining Today: {guild_time // 60}:{seconds_remain} / "
                             f"{allowed_time // 60}:{seconds_allowed}",
                        value="Blame Ryan :upside_down:")

    async def __setup_channel(self, ctx: Context, channel_id, arg):
        channel_instance: TextChannel = [x for x in ctx.guild.text_channels if x.id == channel_id][0]
        channel_messages = await channel_instance.history().flatten()
        if len(channel_messages) > 0:
            if arg is None:
                await ctx.channel.send(
                    "The channel is not empty, if you want to clear the channel for use, use !setmusicchannel -c <id>")
            elif arg == '-c':
                for message in channel_messages:
                    await message.delete()

        temp_default = self._no_current_song_message
        self.__create_time_remaining_field(ctx.guild.id, temp_default)


        default_queue_message = await channel_instance.send(self._empty_queue_message)
        default_preview_message = await channel_instance.send(embed=temp_default)

        db_gateway().update('music_channels', set_params={'queue_message_id': int(default_queue_message.id)},
                            where_params={'guild_id': ctx.author.guild.id})

        db_gateway().update('music_channels', set_params={'preview_message_id': int(default_preview_message.id)},
                            where_params={'guild_id': ctx.author.guild.id})

    async def __remove_active_channel(self, guild_id) -> bool:
        if guild_id in self._currently_active:
            voice_client: VoiceClient = self._currently_active.get(guild_id).get('voice_client')
            await voice_client.disconnect()
            self._currently_active.get(guild_id)['queue'] = [None]
            await self.__check_next_song(guild_id)
            self._currently_active.pop(guild_id)
            return True
        return False

    async def __update_channel_messages(self, guild_id):

        current_guild_instance = [x for x in self._bot.guilds if x.id == guild_id][0]

        guild_db_data = db_gateway().get('music_channels', params={'guild_id': guild_id})[0]
        queue_message_id = guild_db_data.get('queue_message_id')
        preview_message_id = guild_db_data.get('preview_message_id')

        queue_message = self.__update_queue_message(guild_id)
        preview_message = self.__update_preview_message(guild_id)

        music_channel_id = guild_db_data.get('channel_id')
        music_channel_instance = [x for x in current_guild_instance.text_channels if x.id == music_channel_id][0]

        queue_message_instance: Message = [x for x in await music_channel_instance.history().flatten()
                                           if x.id == queue_message_id][0]
        preview_message_instance: Message = [x for x in await music_channel_instance.history().flatten()
                                             if x.id == preview_message_id][0]

        await queue_message_instance.edit(content=queue_message)
        await preview_message_instance.edit(embed=preview_message)

    async def __check_next_song(self, guild_id):
        if len(self._currently_active.get(guild_id).get('queue')) == 1:
            # The queue will be empty so will be marked as inactive
            self._currently_active.get(guild_id).get('queue').pop(0)
            self._marked_channels[guild_id] = time.time()
            await self.__update_channel_messages(guild_id)
        elif len(self._currently_active.get(guild_id).get('queue')) > 1:
            # The queue is not empty, play the next song
            self._currently_active.get(guild_id).get('queue').pop(0)
            self.__start_queue(guild_id)
            await self.__update_channel_messages(guild_id)

    async def __send_timed_message(self, channel, message, timer=15, is_embed=True):
        if is_embed:
            timed_message = await channel.send(embed=message)
        else:
            timed_message = await channel.send(message)
        await timed_message.delete(delay=timer)

    @tasks.loop(seconds=1)
    async def check_active_channels(self):
        # Create a copy to avoid concurrent changes to _currently_active
        active_copy = self._currently_active.copy()
        for guild_id in active_copy.keys():
            if not self._currently_active.get(guild_id).get('voice_client').is_playing() \
                    and not self._currently_active.get(guild_id).get('voice_client').is_paused():
                # Check any voice_clients that are no longer playing but that aren't just paused
                await self.__check_next_song(guild_id)
            elif self.__check_empty_vc(guild_id):
                asyncio.create_task(self.__remove_active_channel(guild_id))
                self._marked_channels.pop(guild_id)

        if len(active_copy.keys()) == 0:
            # Stop the task when no channels to check
            self.check_active_channels.stop()

    @tasks.loop(seconds=60)
    async def check_marked_channels(self):
        # Create a copy to avoid concurrent changes to _marked_channels
        marked_copy = self._marked_channels.copy()
        for guild_id in marked_copy.keys():
            guild_time = self._marked_channels.get(guild_id)
            if time.time() - guild_time >= 60 * 2:
                # If the time since inactivity has been more than 5 minutes leave the channel
                asyncio.create_task(self.__remove_active_channel(guild_id))
                self._marked_channels.pop(guild_id)
            elif self.__check_empty_vc(guild_id):
                asyncio.create_task(self.__remove_active_channel(guild_id))
                self._marked_channels.pop(guild_id)

        if len(marked_copy.keys()) == 0:
            self.check_marked_channels.stop()

    @tasks.loop(hours=24)
    async def reset_music_allowance(self):
        self._time_allocation = defaultdict(lambda: self._allowed_time)

    def __check_empty_vc(self, guild_id):
        voice_client = self._currently_active.get(guild_id).get('voice_client')
        voice_channel = voice_client.channel

        if len(voice_channel.members) == 1:
            return True
        else:
            return False

    def __add_new_active_channel(self, guild_id, channel_id=None, voice_client=None) -> bool:
        if guild_id not in self._currently_active:
            self._currently_active[guild_id] = {}
            self._currently_active[guild_id]['channel_id'] = channel_id
            self._currently_active[guild_id]['voice_client'] = voice_client
            self._currently_active[guild_id]['queue'] = []
            self._currently_active[guild_id]['current_song'] = None
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

        song = self._currently_active.get(guild_id).get('queue')[0]

        song_data = self.__download_video_info(song.get('link'), download=False)
        song_formatted = self.__format_download_data(song_data)

        # Check if the allowed time for the day is used up
        length = song_formatted.get('length')

        # Has to be done separately as to ensure defaultdict creates it if not present
        self._time_allocation[guild_id] = self._time_allocation[guild_id] - length
        #guild_time['used_time'] = self._time_allocation.get(guild_id)['used_time'] - length

        if self._time_allocation[guild_id] < 0:
            self.__remove_active_channel(guild_id)
            self._time_allocation[guild_id] = 0
            return False

        self._currently_active.get(guild_id)['current_song'] = song_formatted

        before = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
        voice_client.play(FFmpegOpusAudio(song_formatted.get('stream'), before_options=before,
                                          bitrate=int(song_formatted.get('bitrate')) + 10))
        voice_client.volume = 100

        return True

    def __pause_song(self, guild_id):
        if self._currently_active.get(guild_id).get('voice_client').is_playing():
            # Can't pause if the bot isn't playing
            voice_client: VoiceClient = self._currently_active.get(guild_id).get('voice_client')
            voice_client.pause()

    def __resume_song(self, guild_id):
        if self._currently_active.get(guild_id).get('voice_client').is_paused():
            # Onl able to resume if currently paused
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

    def __update_queue_message(self, guild_id):
        if len(self._currently_active.get(guild_id).get('queue')) == 0:
            updated_queue_message = self._empty_queue_message
        else:
            updated_queue_message = self.__make_queue_list(guild_id)

        return updated_queue_message

    def __update_preview_message(self, guild_id):
        if len(self._currently_active.get(guild_id).get('queue')) == 0:
            updated_preview_message = self._no_current_song_message
        else:
            current_song = self._currently_active.get(guild_id).get('current_song')
            updated_preview_message = Embed(title="Currently Playing: " + current_song.get('title'),
                                            colour=Colour(0xd462fd), url=current_song.get('link'),
                                            video=current_song.get('link'))
            updated_preview_message.set_image(url=current_song.get('thumbnail'))

        self.__create_time_remaining_field(guild_id, updated_preview_message)

        return updated_preview_message

    def __make_queue_list(self, guild_id):
        queue_string = self._empty_queue_message
        if len(self._currently_active.get(guild_id).get('queue')) > 30:
            # The queue is too long to display
            first_part = self._currently_active.get(guild_id).get('queue')[:10]
            last_part = self._currently_active.get(guild_id).get('queue')[-10:]

            first_string = self.__song_list_to_string(first_part)
            last_string = self.__song_list_to_string(last_part)

            queue_string += first_string + ".\n.\n.\n" + last_string
        else:
            queue_string += self.__song_list_to_string(self._currently_active.get(guild_id).get('queue'))

        return queue_string

    def __song_list_to_string(self, songs):
        string = ""
        for x in range(len(songs)):
            index = x + 1
            item = songs[x]
            # string += f"{index}. {item.get('title')} - {item.get('length')} \n"
            string += f"{index}. {item.get('title')}\n"

        return string

    async def process_song_request(self, message, request):
        # 0 is playlist, 1 is url, 2 is string
        message_type = self.__determine_message_type(request)

        if message_type == 0:
            playlist_links = self.__find_playlist_songs(request)
            playlist_info = self.__get_playlist_info_from_links(playlist_links)
            success = await self.__add_to_queue(message.guild.id, playlist_info)
        else:
            songs_found = self.__find_song(request, message_type)
            success = await self.__add_to_queue(message.guild.id, songs_found)

        if success:
            feedback = Embed(title="Added request to queue!", colour=EmbedColours.music())
            await self.__send_timed_message(message.channel, feedback, timer=5, is_embed=True)
        else:
            feedback = Embed(title="An error occurred while adding your request to the queue",
                             colour=EmbedColours.orange())
            await self.__send_timed_message(message.channel, feedback, timer=10, is_embed=True)

        return success

    def __find_song(self, message, message_type):
        if message_type == 1:
            links = [message]
            return self.__get_playlist_info_from_links(links)
        else:
            return self.__find_query(message)

    def __find_playlist_songs(self, playlist_link):
        query = parse_qs(urlparse(playlist_link).query, keep_blank_values=True)
        playlist_id = query["list"][0]
        youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=self._API_KEY)

        request = youtube.playlistItems().list(
            part="snippet",
            playlistId=playlist_id,
            maxResults=50
        )
        response = request.execute()

        playlist_items = []
        while request is not None:
            response = request.execute()
            playlist_items += response["items"]
            request = youtube.playlistItems().list_next(request, response)

        playlist_links = [f'https://www.youtube.com/watch?v={t["snippet"]["resourceId"]["videoId"]}'
                          for t in playlist_items]

        return playlist_links

    def __get_playlist_info_from_links(self, links):

        # Grequest exception handler
        def exception_handler(request, exception):
            print(str(request) + ' failed with exception: ' + str(exception))

        request = (grequests.get(url) for url in links)
        response = grequests.map(request, exception_handler=exception_handler)

        info = []

        for x in range(len(links)):
            soup = bs(response[x].text, 'lxml')
            all_alternate = soup.find_all('link', attrs={"rel": "alternate"})
            for item in all_alternate:
                if item.get('title'):
                    info.append({'link': links[x], 'title': item.get('title')})
                    break

        return info

    def __find_query(self, message):
        # Finds the required data for
        search_info = self.__search_youtube(message)

        top_hit = search_info[-1]
        best_audio_hit = search_info[0]

        # Usually has a better thumbnail than the lyrics
        best_audio_hit['thumbnail'] = top_hit['thumbnail']
        # Better title to display
        best_audio_hit['title'] = top_hit['title']

        return best_audio_hit

    def __determine_message_type(self, message) -> int:
        if self.__is_url(message):
            if re.search(r'(playlist)', message):
                return 0
            else:
                return 1
        else:
            return 2

    def __format_playlist_data(self, playlist_data):
        entries = playlist_data.get('entries')
        formatted_entries = []
        for entry in entries:
            formatted_entries.append(self.__format_download_data(entry))
        return formatted_entries

    def __format_download_data(self, download_data):
        # Returns the parts of the data that is actually needed
        stream, rate = self.__get_opus_stream(download_data.get('formats'))
        useful_data = {'title': download_data.get('title'), 'id': download_data.get('id'),
                       'link': download_data.get('webpage_url'), 'length': download_data.get('duration'),
                       'stream': stream,
                       'bitrate': rate,
                       'thumbnail': self.__get_thumbnail(download_data.get('thumbnails')),
                       'filename': download_data.get('filename')}
        return useful_data

    def __get_opus_stream(self, formats):
        # Limit the codecs to just opus, as that is required for streaming audio
        opus_formats = [x for x in formats if x.get('acodec') == 'opus']

        # Sort the formats from highest br to lowest
        sorted_opus = list(sorted(opus_formats, key=lambda k: float(k.get('abr')), reverse=True))

        chosen_stream = sorted_opus[self._bitrate_quality]

        return chosen_stream.get('url'), chosen_stream.get('abr')

    def __get_thumbnail(self, thumbnails):
        # Sort by thumbnail size
        sorted_thumbnails = list(sorted(thumbnails, key=lambda k: int(k.get('height')), reverse=True))

        return sorted_thumbnails[0].get('url')

    def __is_url(self, string):
        # Match desktop, mobile and playlist links
        re_desktop = r'(http[s]?://)?youtube.com/(watch\?v)|(playlist\?list)='
        re_mobile = r'(http[s]?://)?youtu.be/([a-zA-Z]|[0-9])+'

        re_string = "(" + re_desktop + ") | (" + re_mobile + ")"

        if re.search(re_desktop, string) or re.search(re_mobile, string):
            return True
        return False

    async def __add_to_queue(self, guild_id, song):
        try:
            if isinstance(song, list):
                for item in song:
                    self._currently_active.get(guild_id).get('queue').append(item)
            else:
                self._currently_active.get(guild_id).get('queue').append(song)
            # self._currently_active.get(guild_id).get('queue').extend(song)

            if not self._currently_active.get(guild_id).get('voice_client').is_playing():
                # If we are not currently playing, start playing
                self.__start_queue(guild_id)

            await self.__update_channel_messages(guild_id)
            return True
        except Exception as e:
            print("There was an error while adding to the queue: \n" + str(e))
            return False

    def __download_video_info(self, link, download=False):
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': self._song_location + '%(title)s-%(id)s.mp3',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=download)
            file = ydl.prepare_filename(info)
            info['filename'] = file

        return info

    def __clean_youtube_results(self, results) -> list:
        cleaned_data = []

        # Gets the data that is actually useful and discards the rest of the data
        for result in results:
            new_result = {'title': result.get('title'),
                          'thumbnail': result.get('thumbnails')[-1].get('url'),
                          'link': result.get('link'),
                          'id': result.get('id'),
                          'viewCount': result.get('viewCount'),
                          'length': result.get('duration')
                          }
            # formatted_title = new_result.get('title').replace('/', '_').replace('|', '_')
            # new_result['localfile'] = self._song_location + "" + formatted_title + '-' + new_result.get('id') \
            new_result['localfile'] = self._song_location + re.sub(r'\W+', '', new_result.get('title')) + \
                                      f"{new_result.get('id')}.mp3"

            cleaned_data.append(new_result)

        return cleaned_data

    def __search_youtube(self, message: str) -> list:
        start = time.time()
        results = VideosSearch(message, limit=self._max_results).result().get('result')

        # Sort the list by view count
        top_results = sorted(results,
                             key=lambda k: int(re.sub(r'view(s)?', '', k['viewCount']['text']).replace(',', '')),
                             reverse=True)

        music_results = []

        # Get results that have words "lyric" or "audio" as it filters out music videos
        for result in results:
            title_lower = result.get('title').lower()
            if 'lyric' in title_lower or 'audio' in title_lower:
                music_results.append(result)

        if len(music_results) == 0:
            # If the song doesn't have a lyric video just use a generic search
            music_results = results

        # Add the top result regardless if it uses the words lyrics or audio
        music_results.append(top_results[0])

        # Remove useless data
        cleaned_results = self.__clean_youtube_results(music_results)

        end = time.time()

        print("Time taken to query youtube: " + str(end - start))

        return cleaned_results


def setup(bot):
    bot.add_cog(MusicCog(bot))
