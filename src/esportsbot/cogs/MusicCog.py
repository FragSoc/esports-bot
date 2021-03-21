import asyncio
import os
import time

import youtube_dl
import re
from youtubesearchpython import VideosSearch

from discord import Message, VoiceClient, FFmpegPCMAudio, TextChannel, Embed, Colour
from discord.ext import commands, tasks
from discord.ext.commands import Context, UserInputError

from src.esportsbot.db_gateway import db_gateway


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
        self._song_location = 'songs' + os.pathsep
        self._currently_active = {}
        self._marked_channels = {}

        self.check_active_channels.start()
        self.check_marked_channels.start()

        self._empty_queue_message = "**__Queue list:__**\n" \
                                    "Join a VoiceChannel and search a song by name or YouTube url.\n"

        self._no_current_song_message = Embed(title="No song currently playing",
                                              colour=EmbedColours.music(),
                                              footer="Use the prefix ! for commands"
                                              )

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
            message = Embed(title=f"There is no song at position {song_index} in the queue", colour=EmbedColours.orange())
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
            return

        await self.__check_next_song(ctx.guild.id)
        await ctx.message.delete()
        message = Embed(title="Song Skipped!", colour=EmbedColours.music())
        await self.__send_timed_message(ctx.channel, message)

    @commands.command()
    async def listqueue(self, ctx: Context):
        if not self.__check_valid_user_vc(ctx):
            # Checks if the user is in a valid voice channel
            return

        queue_string = self.__make_queue_list(ctx.guild.id)

        await ctx.channel.send(queue_string)

    async def on_message_handle(self, message: Message):
        if message.content.startswith(self._bot.command_prefix):
            # Ignore commands, any MusicCog commands will get handled in the usual way
            return

        if not message.author.voice:
            # User is not in a voice channel.. exit
            send = Embed(title="You must be in a voice channel to add a song", colour=EmbedColours.orange())
            await self.__send_timed_message(message.channel, send, timer=20)
            return

        if not self._currently_active.get(message.guild.id):
            # We aren't in a voice channel in the given guild
            voice_client = await message.author.voice.channel.connect()
            self.__add_new_active_channel(message.guild.id, voice_client=voice_client,
                                          channel_id=message.author.voice.channel.id)
        else:
            if self._currently_active.get(message.guild.id).get('channel_id') != message.author.voice.channel.id:
                send = Embed(title="I am already in another voice channel in this server", colour=EmbedColours.orange())
                await self.__send_timed_message(message.channel, send, timer=20)
                return

        if message.guild.id in self._marked_channels:
            # Remove the channel from marked channels as it is no longer inactive
            self._marked_channels.pop(message.guild.id)

        song_data = await self.find_song(message.content)

        self._currently_active[message.guild.id]['queue'].append(song_data)

        if not self._currently_active.get(message.guild.id).get('voice_client').is_playing():
            # If we are not currently playing, start playing
            self.__start_queue(message.guild.id)

        await self.__update_channel_messages(message.guild.id)

        await message.delete()

    async def find_song(self, search_term) -> dict:
        if self.__determine_url(search_term):
            # Currently only supports youtube links
            # Searching youtube with the video id gets the original video
            # Means we can have the same data is if it were searched for by name
            search_term = search_term.split('v=')[-1]

        youtube_results = self.__search_youtube(search_term)

        if len(youtube_results) > 0:
            await self.__download_video(youtube_results[0])

            return youtube_results[0]
        else:
            return {}

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

        default_queue_message = await channel_instance.send(self._empty_queue_message)
        default_preview_message = await channel_instance.send(embed=self._no_current_song_message)

        print()

        db_gateway().update('music_channels', set_params={'queue_message_id': int(default_queue_message.id)},
                            where_params={'guild_id': ctx.author.guild.id})

        db_gateway().update('music_channels', set_params={'preview_message_id': int(default_preview_message.id)},
                            where_params={'guild_id': ctx.author.guild.id})

    async def __remove_active_channel(self, guild_id) -> bool:
        if guild_id in self._currently_active:
            voice_client: VoiceClient = self._currently_active.get(guild_id).get('voice_client')
            await voice_client.disconnect()
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
        elif len(self._currently_active.get(guild_id).get('queue')) > 1:
            # The queue is not empty, play the next song
            self._currently_active.get(guild_id).get('queue').pop(0)
            self.__start_queue(guild_id)
        await self.__update_channel_messages(guild_id)

    async def __download_video(self, video_info):
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

    def __search_youtube(self, message: str) -> list:
        results = VideosSearch(message, limit=self._max_results).result().get('result')

        music_results = []

        # Get results that have words "lyric" or "audio" as it filters out music videos
        for result in results:
            title_lower = result.get('title').lower()
            if 'lyric' in title_lower or 'audio' in title_lower:
                music_results.append(result)

        if len(music_results) == 0:
            # If the song doesn't have a lyric video just use a generic search
            music_results = results

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
            formatted_title = new_result.get('title').replace('/', '_')
            new_result['localfile'] = self._song_location + "" + formatted_title + '-' + new_result.get('id') \
                                      + '.mp3'

            cleaned_data.append(new_result)

        return cleaned_data

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
            current_song = self._currently_active.get(guild_id).get('queue')[0]
            updated_preview_message = Embed(title="Currently Playing: " + current_song.get('title'),
                                            colour=Colour(0xd462fd), url=current_song.get('link'),
                                            video=current_song.get('link'))
            updated_preview_message.set_image(url=current_song.get('thumbnail').get('url'))

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
            string += f"{index}. {item.get('title')} - {item.get('duration')} \n"

        return string

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


def setup(bot):
    bot.add_cog(MusicCog(bot))
