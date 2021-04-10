import asyncio
import sys
import os
import time
from typing import Union, List, Tuple

import youtube_dl
import re

from enum import IntEnum
from youtubesearchpython import VideosSearch

from discord import Message, VoiceClient, TextChannel, Embed, Colour, FFmpegOpusAudio
from discord.ext import commands, tasks
from discord.ext.commands import Context

from ..base_functions import get_cleaned_id
from ..db_gateway import db_gateway
from ..lib.client import EsportsBot

import googleapiclient.discovery
from urllib.parse import parse_qs, urlparse

from random import shuffle
from collections import defaultdict

from ..lib.discordUtil import send_timed_message
from ..lib.stringTyping import strIsInt


class EmbedColours:
    green = Colour(0x1f8b4c)
    orange = Colour(0xe67e22)
    red = Colour(0xe74c3c)
    music = Colour(0xd462fd)


class MessageTypeEnum(IntEnum):
    url = 0
    playlist = 1
    string = 2


EMPTY_QUEUE_MESSAGE = "**__Queue list:__**\n" \
                      "Join a VoiceChannel and search a song by name or YouTube url.\n"

ESPORTS_LOGO_URL = "http://fragsoc.co.uk/wpsite/wp-content/uploads/2020/08/logo1-450x450.png"

EMPTY_PREVIEW_MESSAGE = Embed(title="No song currently playing",
                              colour=EmbedColours.music,
                              footer="Use the prefix ! for commands"
                              )
EMPTY_PREVIEW_MESSAGE.set_image(url=ESPORTS_LOGO_URL)
EMPTY_PREVIEW_MESSAGE.set_footer(text="Definitely not made by fuxticks#1809 on discord")

# Bitrate quality can be 0,1,2: 0 is best, 2 is worst
BITRATE_QUALITY = 0

FFMPEG_BEFORE_OPT = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"

GOOGLE_API_KEY = os.getenv('GOOGLE_API')
YOUTUBE_API = googleapiclient.discovery.build("youtube", "v3", developerKey=GOOGLE_API_KEY)

BOT_INACTIVE_MINUTES = 2


class MusicCog(commands.Cog):

    def __init__(self, bot: EsportsBot, max_search_results=100):
        print("Loaded music module")
        self._bot = bot
        self._max_results = max_search_results
        self._song_location = 'songs' + os.path.sep
        self._currently_active = {}
        self._marked_channels = {}

        self.__check_loops_alive()

        self._time_allocation = defaultdict(lambda: self._allowed_time)
        # Seconds of song (time / day) / server
        # Currently 2 hours of playtime for each server per day
        self._allowed_time = 7200

        self.__db_accessor = db_gateway()

    async def __send_message_and_delete(self, to_send: Embed, to_delete: Message, timer=10):
        await send_timed_message(to_delete.channel, embed=to_send, timer=timer)
        await to_delete.delete()

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setmusicchannel(self, ctx: Context, args: str = None, given_channel_id: str = None) -> bool:
        """
        Sets the music channel for a given guild to a text channel in the given guild by passing the id of the channel
        or by tagging the channel with #<name>.
        :param ctx: The Context of the message sent.
        :param args: Used to specify extra actions for the set command to perform.
        :param given_channel_id: The channel to set as the music channel.
        :return: A boolean determining setting the channel was successful.
        """

        if given_channel_id is None and args is not None:
            # No args was given, but a channel id was given
            given_channel_id = args
            args = ""

        if given_channel_id is None:
            # No given channel id.. exit
            message = Embed(title="A channel id is a required argument", colour=EmbedColours.red)
            await send_timed_message(ctx.channel, embed=message, timer=30)
            return False

        cleaned_channel_id = get_cleaned_id(given_channel_id)

        is_valid_channel_id = (len(str(cleaned_channel_id)) == 18) and strIsInt(cleaned_channel_id)

        if not is_valid_channel_id:
            # The channel id given is not valid.. exit
            message = Embed(title="The id given was not a valid id", colour=EmbedColours.red)
            await send_timed_message(ctx.channel, embed=message, timer=30)
            return False

        music_channel_instance = ctx.guild.get_channel(cleaned_channel_id)

        if not isinstance(music_channel_instance, TextChannel):
            # The channel id given not for a text channel.. exit
            message = Embed(title="The id given must be of a text channel", colour=EmbedColours.red)
            await send_timed_message(ctx.channel, embed=message, timer=30)
            return False

        current_channel_for_guild = self.__db_accessor.get('music_channels', params={
            'guild_id': ctx.guild.id})

        if len(current_channel_for_guild) > 0:
            # There is already a channel set.. update
            self.__db_accessor.update('music_channels', set_params={
                'channel_id': cleaned_channel_id}, where_params={'guild_id': ctx.guild.id})
        else:
            # No channel for guild.. insert
            self.__db_accessor.insert('music_channels', params={
                'channel_id': int(cleaned_channel_id), 'guild_id': int(ctx.guild.id)})

        await self.__setup_channel(ctx, int(cleaned_channel_id), args)
        return True

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def getmusicchannel(self, ctx: Context):
        """
        Sends a tagged channel if the music channel has been set, otherwise will send an error message.
        :param ctx: The context of the message.
        """

        current_channel_for_guild = self.__db_accessor.get('music_channels', params={
            'guild_id': ctx.guild.id})

        if current_channel_for_guild and current_channel_for_guild[0].get('channel_id'):
            # If the music channel has been set in the guild
            id_as_channel = ctx.guild.get_channel(current_channel_for_guild[0].get('channel_id'))
            await ctx.channel.send(f"Music channel is set to {id_as_channel.mention}")
        else:
            await ctx.channel.send("Music channel has not been set")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def resetmusicchannel(self, ctx: Context):
        """
        If the music channel is set, clear it and re-setup the channel with the correct messages. Otherwise send an
        error message.
        :param ctx: The context of the message.
        """

        current_channel_for_guild = self.__db_accessor.get('music_channels', params={
            'guild_id': ctx.guild.id})

        if current_channel_for_guild and current_channel_for_guild[0].get('channel_id'):
            # If the music channel has been set for the guild
            await self.__setup_channel(ctx, arg='-c', channel_id=current_channel_for_guild[0].get('channel_id'))
            message = "Successfully reset the music channel"
            await send_timed_message(ctx.channel, message, timer=20)
        else:
            await ctx.channel.send("Music channel has not been set")

    @commands.command()
    async def removesong(self, ctx, song_index=None) -> bool:
        """
        Remove a song at an index from the current queue.
        :param ctx: The context of the message.
        :param song_index: The index of the song to remove. Index starting from 1.
        :return: A boolean of if the removal of the song at the given index was successful.
        """
        if not self._currently_active.get(ctx.guild.id):
            # Not currently active
            await self.__send_message_and_delete(Embed(title="I am not playing anything currently",
                                                       colour=EmbedColours.music),
                                                 ctx.message)
            return False

        if not await self.__check_valid_user_vc(ctx):
            # Check if the user is in a valid voice channel
            return False

        if not strIsInt(song_index):
            await self.__send_message_and_delete(Embed(title="To remove a song you must provide a number "
                                                           "of a song in the queue", colour=EmbedColours.orange),
                                                 ctx.message)
            return False

        if int(song_index) < 1:
            await self.__send_message_and_delete(Embed(title="The number of the song to remove must be greater than 1",
                                                       colour=EmbedColours.orange),
                                                 ctx.message)
            return False

        if len(self._currently_active.get(ctx.guild.id).get('queue')) < (int(song_index) - 1):
            # The index given is out of the bounds of the current queue
            message = Embed(title=f"There is no song at position {song_index} in the queue",
                            description=f"A valid number is between 1 "
                                        f"and {len(self._currently_active.get(ctx.guild.id).get('queue'))}.",
                            colour=EmbedColours.orange)
            await self.__send_message_and_delete(message, ctx.message)
            return False

        song_popped = self._currently_active[ctx.guild.id]['queue'].pop(int(song_index) - 1)
        await self.__update_channel_messages(ctx.guild.id)
        message = Embed(title=f"Removed {song_popped.get('title')} from position {song_index} in the queue",
                        colour=EmbedColours.green)
        await self.__send_message_and_delete(message, ctx.message)
        return True

    @commands.command()
    async def pausesong(self, ctx: Context) -> bool:
        """
        If the bot is currently playing in the context's guild, pauses the playback, else does nothing.
        :param ctx: The context of the song.
        :return: A boolean if the pausing of the current playback was successful.
        """

        if not self._currently_active.get(ctx.guild.id):
            # Not currently active
            await self.__send_message_and_delete(Embed(title="I am not playing anything currently",
                                                       colour=EmbedColours.music),
                                                 ctx.message)
            return False

        if not await self.__check_valid_user_vc(ctx):
            # Checks if the user is in a valid voice channel
            return False

        if self.__pause_song(ctx.guild.id):
            await self.__send_message_and_delete(Embed(title="Song Paused", colour=EmbedColours.music), ctx.message)
            return True

        await ctx.message.delete()
        return False

    @commands.command()
    async def resumesong(self, ctx: Context) -> bool:
        """
        If the bot is currently paused, the playback is resumed, else does nothing.
        :param ctx: The context of the message.
        :return: A boolean if the playback was resumed successfully.
        """

        if not self._currently_active.get(ctx.guild.id):
            # Not currently active
            await self.__send_message_and_delete(Embed(title="There is nothing to resume at the moment...",
                                                       colour=EmbedColours.music),
                                                 ctx.message)
            return False

        if not await self.__check_valid_user_vc(ctx):
            # Checks if the user is in a valid voice channel
            return False

        if self.__resume_song(ctx.guild.id):
            await self.__send_message_and_delete(Embed(title="Song Resumed", colour=EmbedColours.music), ctx.message)
            return True

        await ctx.message.delete()
        return False

    @commands.command()
    async def kickbot(self, ctx: Context) -> bool:
        """
        Remove the bot from the voice channel. Will also reset the queue.
        :param ctx: The context of the message.
        :return: A boolean if the bot was removed from the voice channel successfully.
        """

        if not self._currently_active.get(ctx.guild.id):
            # Not currently active
            await self.__send_message_and_delete(Embed(title="I am not in a channel at the moment",
                                                       colour=EmbedColours.music),
                                                 ctx.message)
            return False

        if not await self.__check_valid_user_vc(ctx):
            # Checks if the user is in a valid voice channel
            await ctx.message.delete()
            return False

        if await self.__remove_active_channel(ctx.guild.id):
            await self.__send_message_and_delete(Embed(title="I have left the Voice Channel",
                                                       colour=EmbedColours.music),
                                                 ctx.message)
            return True
        await ctx.message.delete()
        return False

    @commands.command()
    async def skipsong(self, ctx: Context) -> bool:
        """
        Skips the current song. If there are no more songs in the queue, the bot will leave.
        :param ctx: The context of the message.
        :return: None
        """

        if not self._currently_active.get(ctx.guild.id):
            # Not currently active
            await self.__send_message_and_delete(Embed(title="I am not currently active", colour=EmbedColours.music),
                                                 ctx.message)
            return False

        if not await self.__check_valid_user_vc(ctx):
            # Checks if the user is in a valid voice channel
            return False

        # TODO: Decide if the bot should leave the vc if the queue is empty after skipping.
        if len(self._currently_active.get(ctx.guild.id).get('queue')) == 1:
            # Skipping when only one song in the queue will just kick the bot
            await self.__remove_active_channel(ctx.guild.id)
            await ctx.message.delete()
            return True

        await self.__check_next_song(ctx.guild.id)
        await self.__send_message_and_delete(Embed(title="Song Skipped!", colour=EmbedColours.music, time=5),
                                             ctx.message)
        return True

    @commands.command()
    async def listqueue(self, ctx: Context) -> bool:
        """
        Sends a message of the current queue to the channel the message was sent from.
        :param ctx:The context of the message.
        :return: A boolean if sending the message was successful.
        """

        if not self._currently_active.get(ctx.guild.id):
            # Not currently active
            await self.__send_message_and_delete(Embed(title="I am not currently active", colour=EmbedColours.music),
                                                 ctx.message)
            return False

        # We don't want the song channel to be filled with the queue as it already shows it
        music_channel_in_db = self.__db_accessor.get('music_channels', params={'guild_id': ctx.guild.id})
        if ctx.message.channel.id == music_channel_in_db[0].get('channel_id'):
            # Message is in the songs channel
            await self.__send_message_and_delete(Embed(title="The queue is already visible in the music channel",
                                                       colour=EmbedColours.music),
                                                 ctx.message)
            return False

        queue_string = self.__make_queue_list(ctx.guild.id)

        if await ctx.channel.send(queue_string) is not None:
            return True
        return False

    @commands.command()
    async def clearqueue(self, ctx: Context) -> bool:
        """
        Clear the current queue of all songs. The bot won't leave the vc with this command.
        :param ctx: The context of the message.
        :return: A boolean if the current queue was successfully cleared.
        """

        if not self._currently_active.get(ctx.guild.id):
            # Not currently active
            await self.__update_channel_messages(ctx.guild.id)
            await ctx.message.delete()
            return False

        if not await self.__check_valid_user_vc(ctx):
            # Checks if the user is in a valid voice channel
            return False

        if self._currently_active.get(ctx.guild.id).get('voice_client').is_playing():
            # If currently in a song, set the queue to what is currently playing
            self._currently_active.get(ctx.guild.id)['queue'] = [
                self._currently_active.get(ctx.guild.id).get('queue').pop(0)]
        else:
            # Else empty the queue and start the inactivity timer
            self._currently_active.get(ctx.guild.id)['queue'] = [None]
            await self.__check_next_song(ctx.guild.id)

        await self.__update_channel_messages(ctx.guild.id)
        await self.__send_message_and_delete(Embed(title="Queue Cleared!", colour=EmbedColours.music), ctx.message)
        return True

    @commands.command()
    async def shufflequeue(self, ctx: Context) -> bool:
        """
        Shuffle the current queue of songs. Does not include the current song playing, which is index 0. Won't bother
        with a shuffle unless there are 3 or more songs.
        :param ctx: The context of the message.
        :return: A boolean if the queue was shuffled.
        """

        if not self._currently_active.get(ctx.guild.id):
            # Not currently active
            await self.__send_message_and_delete(Embed(title="I am not currently active", colour=EmbedColours.music),
                                                 ctx.message)
            return False

        if not await self.__check_valid_user_vc(ctx):
            # Checks if the user is in a valid voice channel
            return False

        if not len(self._currently_active.get(ctx.guild.id).get('queue')) > 2:
            # Nothing to shuffle
            await ctx.message.delete()
            return False

        current_top = self._currently_active.get(ctx.guild.id).get('queue').pop(0)
        shuffle(self._currently_active.get(ctx.guild.id)['queue'])
        self._currently_active.get(ctx.guild.id).get('queue').insert(0, current_top)

        await self.__update_channel_messages(ctx.guild.id)
        await self.__send_message_and_delete(Embed(title="Queue shuffled!", colour=EmbedColours.green), ctx.message)

    @tasks.loop(seconds=1)
    async def check_active_channels(self):
        """
        Check the inactive channels if they are still playing. If its been more than the allotted time remove the
        channel from any active/inactive status.
        """
        # Get a list of the keys to iterate through
        active_copy = list(self._currently_active.keys())
        for guild_id in active_copy:
            if not self._currently_active.get(guild_id).get('voice_client').is_playing() \
                    and not self._currently_active.get(guild_id).get('voice_client').is_paused():
                # Check any voice_clients that are no longer playing but that aren't just paused
                await self.__check_next_song(guild_id)
            elif self.__check_empty_vc(guild_id):
                # Check if the bot is in a channel by itself
                guild = self._currently_active.pop(guild_id)
                await guild['voice_client'].disconnect()
                await self.__update_channel_messages(guild_id)

        if len(self._currently_active) == 0:
            # Stop the task when no channels to check
            self.check_active_channels.stop()

    @tasks.loop(seconds=60)
    async def check_marked_channels(self):
        """
        Check the current channels if they are still playing. If no longer playing, check for the next song. Also checks
        if the bot is in a channel by itself.
        """
        # Create a copy to avoid concurrent changes to _marked_channels
        marked_copy = list(self._marked_channels.keys())
        for guild_id in marked_copy:
            guild_time = self._marked_channels.get(guild_id)
            if time.time() - guild_time >= 60 * BOT_INACTIVE_MINUTES:
                # If the time since inactivity has been more than the minutes specified by BOT_TIMEOUT_MINUTES,
                # leave the channel
                asyncio.create_task(self.__remove_active_channel(guild_id))
                self._marked_channels.pop(guild_id)
            elif self.__check_empty_vc(guild_id):
                # The voice channel has no members in it
                asyncio.create_task(self.__remove_active_channel(guild_id))
                self._marked_channels.pop(guild_id)

        if len(self._marked_channels) == 0:
            # Stop the task when no channels to check
            self.check_marked_channels.stop()

    @tasks.loop(hours=24)
    async def reset_music_allowance(self):
        """
        Reset the number of minutes a guild can use per day. Runs every 24hrs
        """
        self._time_allocation = defaultdict(lambda: self._allowed_time)

    async def __setup_channel(self, ctx: Context, channel_id: int, arg: str):
        """
        Sends the preview and queue messages to the music channel and adds the ids of the messages to the database.
        If the music channel is not empty and the correct arg is set, also clears the channel.
        :param ctx: The context of the messages, used to send the messages to the channels.
        :param channel_id: The id of the music channel.
        :param arg: Optional arg to perform extra utilities while setting the channel up.
        """

        # Get a discord object of the channel.
        channel_instance = self._bot.get_channel(channel_id)
        if channel_instance is None:
            channel_instance = await self._bot.fetch_channel(channel_id)

        # Only need to get a few messages to check if the channel is non-empty.
        channel_messages = await channel_instance.history(limit=2).flatten()
        if len(channel_messages) > 1:
            # If there are messages in the channel.
            if arg is None:
                await ctx.channel.send("The channel is not empty, if you want to clear the channel for use, "
                                       "use !setmusicchannel -c <channel>")
            elif arg == '-c':
                await channel_instance.purge(limit=int(sys.maxsize))

        temp_default_preview = EMPTY_PREVIEW_MESSAGE.copy()
        self.__add_time_remaining_field(ctx.guild.id, temp_default_preview)

        # Send the messages and record their ids.
        default_queue_message = await channel_instance.send(EMPTY_QUEUE_MESSAGE)
        default_preview_message = await channel_instance.send(embed=temp_default_preview)

        self.__db_accessor.update('music_channels', set_params={'queue_message_id': int(default_queue_message.id)},
                                  where_params={'guild_id': ctx.author.guild.id})

        self.__db_accessor.update('music_channels', set_params={'preview_message_id': int(default_preview_message.id)},
                                  where_params={'guild_id': ctx.author.guild.id})

    async def __remove_active_channel(self, guild_id: int) -> bool:
        """
        Disconnect the bot from the voice channel and remove it from the currently active channels.
        :param guild_id: The id of the guild to remove the bot from.
        :return: True if the removal was successful, False otherwise.
        """
        if guild_id in self._currently_active:
            # If the guild is currently active.
            voice_client: VoiceClient = self._currently_active.get(guild_id).get('voice_client')
            await voice_client.disconnect()
            self._currently_active.get(guild_id)['queue'] = [None]
            self._currently_active.pop(guild_id)
            await self.__update_channel_messages(guild_id)
            return True
        return False

    async def __check_next_song(self, guild_id: int):
        # TODO: Check spam updates
        """
        Check if there is another song to play after the current one. If no more songs, mark the channel as in active,
        otherwise play the next song.
        :param guild_id: The id of the guild to check the next song in.
        """
        if len(self._currently_active.get(guild_id).get('queue')) == 1:
            # The queue will be empty so will be marked as inactive
            self._currently_active.get(guild_id).get('queue').pop(0)
            self._marked_channels[guild_id] = time.time()
            await self.__update_channel_messages(guild_id)
        elif len(self._currently_active.get(guild_id).get('queue')) > 1:
            # The queue is not empty, play the next song
            self._currently_active.get(guild_id).get('queue').pop(0)
            self.__play_queue(guild_id)
            await self.__update_channel_messages(guild_id)

    async def __add_song_to_queue(self, guild_id: int, song) -> bool:
        """
        Add a list of songs or a single song to the queue.
        :param guild_id: The id of the guild to add the song to the queue.
        :param song: The song or list of songs. A song is a dict of information that is needed to play the song.
        :return: True if the addition was successful. False otherwise.
        """

        try:
            if isinstance(song, list):
                for item in song:
                    self._currently_active.get(guild_id).get('queue').append(item)
            elif isinstance(song, dict):
                self._currently_active.get(guild_id).get('queue').append(song)
            else:
                raise ValueError("The values supplied to add to the queue were not a list or dict: \n" + str(song))

            if not self._currently_active.get(guild_id).get('voice_client').is_playing():
                # If we are not currently playing, start playing
                self.__play_queue(guild_id)

            await self.__update_channel_messages(guild_id)
            return True
        except Exception as e:
            print("There was an error while adding to the queue: \n" + str(e))
            return False

    async def on_message_handle(self, message: Message) -> bool:
        """
        The handle the is called whenever a message is sent in the music channel of a guild.
        :param message: The message sent to the channel.
        :return: A boolean if the message was properly handled by the music cog.
        """

        if message.content.startswith(self._bot.command_prefix):
            # Ignore commands, any MusicCog commands will get handled in the usual way
            return True

        if not message.author.voice:
            # User is not in a voice channel.. exit
            await self.__send_message_and_delete(Embed(title="You must be in a voice channel to add a song",
                                                       colour=EmbedColours.orange),
                                                 message)
            return True

        if not message.author.voice.channel.permissions_for(message.guild.me).connect:
            # The bot does not have permission to join the channel.. exit
            await self.__send_message_and_delete(Embed(title="I need the permission `connect` "
                                                             "to be able to join that channel",
                                                       colour=EmbedColours.orange),
                                                 message)
            return True

        if not self._currently_active.get(message.guild.id):
            # We aren't in a voice channel in the given guild
            voice_client = await message.author.voice.channel.connect()
            self.__add_new_active_channel(message.guild.id, voice_client=voice_client,
                                          channel_id=message.author.voice.channel.id)
        else:
            if self._currently_active.get(message.guild.id).get('channel_id') != message.author.voice.channel.id:
                # The bot is already being used in the current guild.
                await self.__send_message_and_delete(Embed(title="I am already in another voice channel in this server",
                                                           colour=EmbedColours.orange),
                                                     message)
                return True

        # Check if the loops for marked and active channels are running.
        self.__check_loops_alive()

        # Splits multiline messages into a list. Single line messages return a list of [message]
        split_message = message.content.split("\n")
        split_message = [k for k in split_message if k not in ('', ' ')]
        partial_success = False
        total_success = True

        # Add each line of the message to the queue
        st = time.time()
        for line in split_message:
            result = await self.process_song_request(message, line)
            partial_success = result or partial_success
            total_success = result and total_success

        print(f"Queue time: {time.strftime('%H:%M:%S', time.gmtime(time.time() - st))}")
        # If any of the songs were successful, ensure that the channel is no long marked as inactive.
        if partial_success:
            if message.guild.id in self._marked_channels:
                # Remove the channel from marked channels as it is no longer inactive
                self._marked_channels.pop(message.guild.id)

        if not total_success:
            send = Embed(title="There were errors while adding some songs to the queue", colour=EmbedColours.red)
            await send_timed_message(message.channel, embed=send, timer=10)

        await message.delete()

    async def process_song_request(self, message: Message, request: str) -> bool:
        """
        Process the incoming message as a song request
        :param message: The instance of the discord message that sent the request.
        :param request: The contents of the request made.
        :return The success value of if the song was added to the queue or not.
        """

        message_type = self.__determine_message_type(request)
        if message_type == MessageTypeEnum.url or message_type == MessageTypeEnum.playlist:
            processed_request = self.__get_youtube_api_info(request, message_type)
            formatted_request = self.__format_api_data(processed_request)
            return await self.__add_song_to_queue(message.guild.id, formatted_request)
        elif message_type == MessageTypeEnum.string:
            queried_song = self.__find_query(request)
            return await self.__add_song_to_queue(message.guild.id, queried_song)

    def __get_youtube_api_info(self, request: str, message_type: int) -> Union[List[dict], None]:
        """
        Downloads the video information associated with a url as a list for each video in the request.
        :param request: The request to make to the YouTube API.
        :param message_type: The kind of request: Video url or Playlist url.
        :return: A list of dicts for each video in the request.
        """

        # Determines if we access the videos or playlist part of the YouTube API.
        func = YOUTUBE_API.videos() if message_type == MessageTypeEnum.url else YOUTUBE_API.playlistItems()
        # Used to get the id of the url.
        key = "v" if message_type == MessageTypeEnum.url else "list"

        query = parse_qs(urlparse(request).query, keep_blank_values=True)
        youtube_id = query[key][0]

        # The args used to get the data from the API.
        args = {"part": "snippet", "maxResults": 1 if message_type == MessageTypeEnum.url else 50}

        if message_type == MessageTypeEnum.url:
            args["id"] = youtube_id
        else:
            args["playlistId"] = youtube_id

        youtube_request = func.list(**args)

        # The list of video data.
        api_items = []
        while youtube_request is not None:
            response = youtube_request.execute()
            api_items += response["items"]
            youtube_request = func.list_next(youtube_request, response)

        if len(api_items) == 0:
            return None
        return api_items

    def __format_api_data(self, data: list) -> List[dict]:
        """
        Formats a list of data that was obtained from the YouTube API call, where each item in the list is a dict.
        :param data: The list of dicts that was gained from the API call.
        :return: A formatted list of dicts. Each dict contains the YouTube url, the thumbnail url and the title of the
                 video.
        """
        formatted_data = []
        for item in data:
            snippet = item.get("snippet")
            info = {"title": snippet.get("title", "Unable to get title, this is a bug"),
                    "thumbnail": snippet.get("thumbnails", {}).get("maxres", {}).get("url", "Unable to get thumbnail "
                                                                                            "this is a bug")}
            if "id" in info:
                info["link"] = info.get("id", "Unable to get link, this is a bug")
            else:
                info["link"] = snippet.get("resourceId", {}).get("videoId", "Unable to get link, this is a bug")

            # Turn the id gained from the dict into an actual url.
            if "Unable to get link, this is a bug" not in info.get("link"):
                info["link"] = "https://www.youtube.com/watch?v=" + info.get("link")

            # Generate the url from the video id if the video id was gotten successfully.
            if not self.__is_url(info.get("thumbnail")):
                thumbnail = snippet.get("thumbnails", {}).get("maxres", {}).get("url", "Unable to get thumbnail this "
                                                                                       "is a bug")
                info["thumbnail"] = thumbnail

            formatted_data.append(info)

        return formatted_data

    async def __update_channel_messages(self, guild_id: int):
        """
        Update the queue and preview messages in the music channel.
        :param guild_id: The guild id of the guild to be updated.
        """

        guild_db_data = self.__db_accessor.get('music_channels', params={'guild_id': guild_id})[0]

        # Get the ids of the queue and preview messages
        queue_message_id = guild_db_data.get('queue_message_id')
        preview_message_id = guild_db_data.get('preview_message_id')

        # Create the updated messages
        queue_message = self.__make_updated_queue_message(guild_id)
        preview_message = self.__make_update_preview_message(guild_id)

        music_channel_id = guild_db_data.get('channel_id')
        # Get the music channel id as a discord.TextChannel object
        music_channel_instance = self._bot.get_channel(music_channel_id)
        if music_channel_instance is None:
            music_channel_instance = await self._bot.fetch_channel(music_channel_id)

        # Get the message ids as discord.Message objects
        queue_message_instance: Message = await music_channel_instance.fetch_message(queue_message_id)
        preview_message_instance: Message = await music_channel_instance.fetch_message(preview_message_id)

        # Update the messages
        await queue_message_instance.edit(content=queue_message)
        await preview_message_instance.edit(embed=preview_message)

    def __make_updated_queue_message(self, guild_id: int) -> str:
        """
        Update the queue message in a given guild.
        :param guild_id: The guild id of the guild to update the queue message in.
        :return: A string of the queue that is to be the new queue message.
        """

        if not self._currently_active.get(guild_id) or len(self._currently_active.get(guild_id).get('queue')) == 0:
            # If the queue is empty or the bot isn't active
            updated_queue_message = EMPTY_QUEUE_MESSAGE
        else:
            updated_queue_message = self.__make_queue_list(guild_id)

        return updated_queue_message

    def __make_update_preview_message(self, guild_id: int) -> Embed:
        """
        Update the preview message in a given guild.
        :param guild_id: The guild id of the guild to update the preview message in.
        :return: An embed message for the updated preview message in a given guild id.
        """

        if not self._currently_active.get(guild_id) or len(self._currently_active.get(guild_id).get('queue')) == 0:
            # If the queue is empty, provide the empty queue embed or the bot isn't active
            updated_preview_message = EMPTY_PREVIEW_MESSAGE.copy()
        else:
            current_song = self._currently_active.get(guild_id).get('current_song')
            updated_preview_message = Embed(title="Currently Playing: " + current_song.get('title'),
                                            colour=EmbedColours.music, url=current_song.get('link'),
                                            video=current_song.get('link'))
            thumbnail = current_song.get('thumbnail')
            # If the current thumbnail isn't a url, just use the default image.
            if not self.__is_url(current_song.get('thumbnail')):
                thumbnail = ESPORTS_LOGO_URL
            updated_preview_message.set_image(url=thumbnail)

        self.__add_time_remaining_field(guild_id, updated_preview_message)

        return updated_preview_message

    def __generate_link_data_from_queue(self, guild_id: int) -> Tuple[dict, dict]:
        """
        Get the opus stream, length and bitrate of the stream for a given YouTube url.
        :param guild_id: The guild id to get the queue from.
        :return: A tuple of two dicts. First dict is the stream data, Second dict is the current song information
                 already gained.
        """
        current_song = self._currently_active.get(guild_id).get('queue')[0]
        download_data = self.__download_video_info(current_song.get('link'))
        return self.__format_download_data(download_data), current_song

    def __check_loops_alive(self):
        """
        Check if the async task loops are alive and start any that are not.
        """
        if not self.check_active_channels.is_running():
            self.check_active_channels.start()
        if not self.check_marked_channels.is_running():
            self.check_marked_channels.start()
        if not self.reset_music_allowance.is_running():
            self.reset_music_allowance.start()

    def __add_new_active_channel(self, guild_id: int, channel_id: str = None, voice_client: VoiceClient = None) -> bool:
        """
        Add a new voice channel to the currently active channels.
        :param guild_id: The id of the guild the voice channel is in.
        :param channel_id: The id of the voice channel the bot is joining.
        :param voice_client: The voice client instance of the bot.
        :return: True if successfully added to the list of active channels. False otherwise.
        """

        if guild_id not in self._currently_active:
            # If the guild is not currently active we can add it
            self._currently_active[guild_id] = {}
            self._currently_active[guild_id]['channel_id'] = channel_id
            self._currently_active[guild_id]['voice_client'] = voice_client
            self._currently_active[guild_id]['queue'] = []
            self._currently_active[guild_id]['current_song'] = None
            return True
        return False

    def __pause_song(self, guild_id: int) -> bool:
        """
        Pauses the playback of a specific guild if the guild is playing. Otherwise nothing.
        :param guild_id: The id of the guild to pause the playback in.
        :return: A boolean if the pause was successful.
        """

        if self._currently_active.get(guild_id).get('voice_client').is_playing():
            # Can't pause if the bot isn't playing
            voice_client: VoiceClient = self._currently_active.get(guild_id).get('voice_client')
            voice_client.pause()
            return True
        return False

    def __resume_song(self, guild_id: int) -> bool:
        """
        Resumes the playback of a specific guild if the guild is paused. Otherwise nothing.
        :param guild_id: The id of the guild to resume the playback in.
        :return: A boolean if the playback resume was successful.
        """

        if self._currently_active.get(guild_id).get('voice_client').is_paused():
            # Only able to resume if currently paused
            voice_client: VoiceClient = self._currently_active.get(guild_id).get('voice_client')
            voice_client.resume()
            return True
        return False

    async def __check_valid_user_vc(self, ctx: Context) -> bool:
        """
        Checks if the user: A) Is in a voice channel, B) The voice channel is the same as the voice channel the bot is
        connected to, C) The message sent was in the music text channel.
        :param ctx: The context of the message sent.
        :return: If all the above conditions are met, True, otherwise False.
        """

        music_channel_in_db = self.__db_accessor.get('music_channels', params={'guild_id': ctx.guild.id})
        if ctx.message.channel.id != music_channel_in_db[0].get('channel_id'):
            # Message is not in the songs channel
            await self.__send_message_and_delete(Embed(title="You are not in a valid voice channel",
                                                       colour=EmbedColours.music),
                                                 ctx.message)
            return False

        if not ctx.author.voice:
            # User is not in a voice channel
            await self.__send_message_and_delete(Embed(title="You are not in a valid voice channel",
                                                       colour=EmbedColours.music),
                                                 ctx.message)
            return False

        if self._currently_active.get(ctx.guild.id).get('channel_id') != ctx.author.voice.channel.id:
            # The user is not in the same voice channel as the bot
            await self.__send_message_and_delete(Embed(title="You are not in a valid voice channel",
                                                       colour=EmbedColours.music),
                                                 ctx.message)
            return False

        return True

    def __determine_message_type(self, message: str) -> int:
        """
        Determine if the message received is a video url, playlist url or a string that needs to be queried.
        :param message: The message to determine the type of.
        :return: An integer representing the message type.
        """

        if self.__is_url(message):
            # The message is a url
            if re.search(r'(playlist)', message):
                # The message is a playlist
                return MessageTypeEnum.playlist
            else:
                return MessageTypeEnum.url
        else:
            # The message is a string
            return MessageTypeEnum.string

    def __get_opus_stream(self, formats: list) -> Tuple[str, float]:
        """
        Get the opus formatted streaming link from the formats dictionary.
        :param formats: The formats dictionary that contains the different streaming links.
        :return: A streaming url that links to an opus stream and the bit rate of the stream.
        """

        # Limit the codecs to just opus, as that is required for streaming audio
        opus_formats = [x for x in formats if x.get('acodec') == 'opus']

        # Sort the formats from highest br to lowest
        sorted_opus = list(sorted(opus_formats, key=lambda k: float(k.get('abr')), reverse=True))

        chosen_stream = sorted_opus[BITRATE_QUALITY]

        return chosen_stream.get('url'), float(chosen_stream.get('abr'))

    def __format_download_data(self, download_data: dict) -> dict:
        """
        Format a songs data to remove the useless data.
        :param download_data: The song data to format.
        :return: A dictionary of data which is a subset of the param download_data
        """

        stream, rate = self.__get_opus_stream(download_data.get('formats'))
        useful_data = {'length': download_data.get('duration'),
                       'stream': stream,
                       'bitrate': rate,
                       'filename': download_data.get('filename')}
        return useful_data

    def __is_url(self, string: str) -> bool:
        """
        Returns if the string given is a url.
        :param string: The string to check.
        :return: True if the string is a url. False otherwise.
        """

        # Match desktop, mobile and playlist links
        re_desktop = r'(http[s]?://)?youtube.com/(watch\?v)|(playlist\?list)='
        re_mobile = r'(http[s]?://)?youtu.be/([a-zA-Z]|[0-9])+'
        re_thumbnail = r'(http[s]?://)?i.ytimg.com/vi/([a-zA-Z]|[0-9])+'

        return bool(re.search(re_desktop, string) or re.search(re_mobile, string) or re.search(re_thumbnail, string))

    def __download_video_info(self, link: str, download: bool = False) -> dict:
        """
        Download all the information about a given link from YouTube.
        :param link: The link to find the information about.
        :param download: If the song should also be downloaded to a file.
        :return: The information about a YouTube url.
        """

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

    def __add_time_remaining_field(self, guild_id: int, embed: Embed):
        """
        Create the field for an embed that displays how much time a server has left to play songs in that day.
        :param guild_id: The guild id of the guild.
        :param embed: The embed message to add the field to.
        """

        # Get the time remaining
        guild_time = self._time_allocation[guild_id]
        guild_time_string = time.strftime('%H:%M:%S', time.gmtime(guild_time))

        # Get the total time allowed.
        allowed_time = self._allowed_time
        allowed_time_string = time.strftime('%H:%M:%S', time.gmtime(allowed_time))

        # Add the field to the embed.
        embed.add_field(name=f"Time Remaining Today: {guild_time_string} / {allowed_time_string}",
                        value="Blame Ryan :upside_down:")

    def __check_empty_vc(self, guild_id: int) -> bool:
        """
        Checks if the voice channel the bot is in has no members in it.
        :param guild_id: The id of the guild that is being checked.
        :return: True if the channel is empty or if the bot isn't in a channel. False otherwise.
        """

        voice_client = self._currently_active.get(guild_id).get('voice_client')
        if not voice_client:
            # The bot is not in a channel, just return True
            return True
        voice_channel = voice_client.channel
        # TODO: Test commented version of self removal from list
        members_not_bots = [x for x in voice_channel.members if not x.bot]
        # members_not_bots = voice_channel.members.remove(voice_channel.guild.me)

        return not len(members_not_bots) > 0

    def __play_queue(self, guild_id: int) -> bool:
        """
        Starts the playback of the song at the top of the queue.
        :param guild_id: The id of the guild the bot is playing in.
        :return: True if the playback was successful, False otherwise.
        """

        if len(self._currently_active.get(guild_id).get('queue')) < 1:
            # Queue is empty.. exit
            return False

        voice_client: VoiceClient = self._currently_active.get(guild_id).get('voice_client')

        if voice_client.is_playing():
            # Stop the bot if it is playing
            voice_client.stop()

        # Get the next song
        extra_data, current_song = self.__generate_link_data_from_queue(guild_id)
        next_song = {**current_song, **extra_data}
        length = next_song.get("length")

        self._time_allocation[guild_id] = self._time_allocation[guild_id] - length

        if self._time_allocation[guild_id] < 0:
            # If the allocated time is used up set it to 0 and exit out
            self.__remove_active_channel(guild_id)
            self._time_allocation[guild_id] = 0
            return False

        self._currently_active.get(guild_id)['current_song'] = next_song

        voice_client.play(FFmpegOpusAudio(next_song.get("stream"), before_options=FFMPEG_BEFORE_OPT,
                                          bitrate=int(next_song.get("bitrate")) + 10))
        voice_client.volume = 100

        return True

    def __make_queue_list(self, guild_id: int) -> str:
        """
        Create a formatted string representing the queue from a server.
        :param guild_id: The guild of the queue to turn into a string.
        :return: A string representing the queue list.
        """

        queue_string = EMPTY_QUEUE_MESSAGE
        if len(self._currently_active.get(guild_id).get('queue')) > 30:
            # The queue is too long to display
            first_part = self._currently_active.get(guild_id).get('queue')[:10]
            last_part = self._currently_active.get(guild_id).get('queue')[-10:]

            extra = len(self._currently_active.get(guild_id).get('queue')) - 20

            first_string = self.__song_list_to_string(first_part)
            last_string = self.__song_list_to_string(last_part)

            queue_string += f"{first_string}... and `{extra}` more \n{last_string}"
        else:
            queue_string += self.__song_list_to_string(self._currently_active.get(guild_id).get('queue'))

        return queue_string

    def __song_list_to_string(self, songs: list) -> str:
        """
        Turn a list into a string.
        :param songs: The list of songs to turn into a string.
        :return: A string representing a queue list.
        """
        return "\n".join(str(songNum + 1) + ". " + song.get('title') for songNum, song in enumerate(songs))

    def __find_query(self, message: str) -> dict:
        """
        Query YouTube to find a search result and get return a link to the top hit of that query.
        :param message: The message to query YouTube with.
        :return: A link and some other basic information regarding the query.
        """

        # Finds the required data for
        search_info = self.__query_youtube(message)

        top_hit = search_info[-1]
        best_audio_hit = search_info[0]

        # Usually has a better thumbnail than the lyrics
        best_audio_hit['thumbnail'] = top_hit['thumbnail']
        # Better title to display
        best_audio_hit['title'] = top_hit['title']

        # Ensures that all the dicts returned from api or this are formatted the same.
        best_audio_hit.pop('viewCount', None)

        return best_audio_hit

    def __clean_query_results(self, results: list) -> list:
        """
        Remove unnecessary data from a list of dicts gained from querying YouTube.
        :param results: The list of YouTube information gathered from the query.
        :return: A list of dicts containing the title, thumbnail url, video url and view count of a video.
        """

        cleaned_data = []

        # Gets the data that is actually useful and discards the rest of the data
        for result in results:
            new_result = {'title': result.get('title'),
                          'thumbnail': result.get('thumbnails')[-1].get('url'),
                          'link': result.get('link'),
                          'viewCount': result.get('viewCount')
                          }
            filename = re.sub(r'\W+', '', new_result.get('title')) + f"{new_result.get('id')}.mp3"
            new_result['localfile'] = self._song_location + filename

            cleaned_data.append(new_result)

        return cleaned_data

    def __query_youtube(self, message: str) -> list:
        """
        Search YouTube with a given string.
        :param message: The message to query YouTube with.
        :return: A dictionary having the information about the query.
        """

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
        cleaned_results = self.__clean_query_results(music_results)

        end = time.time()

        print("Time taken to query youtube: " + str(end - start))

        return cleaned_results


def setup(bot):
    bot.add_cog(MusicCog(bot))
