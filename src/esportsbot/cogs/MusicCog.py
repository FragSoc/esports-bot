import grequests
import asyncio
import os
import time

import youtube_dl
import re
from youtubesearchpython import VideosSearch

from discord import Message, VoiceClient, TextChannel, Embed, Colour, FFmpegOpusAudio
from discord.ext import commands, tasks
from discord.ext.commands import Context

from ..db_gateway import db_gateway
from ..lib.client import EsportsBot

import googleapiclient.discovery
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup as bs

from random import shuffle
from collections import defaultdict


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

    def __init__(self, bot: EsportsBot, max_search_results=100):
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

        self._time_allocation = defaultdict(lambda: self._allowed_time)
        # Seconds of song (time / day) / server
        # Currently 2 hours of playtime for each server per day
        self._allowed_time = 7200

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setmusicchannel(self, ctx: Context, args=None, given_channel_id=None):
        """
        Sets the music channel for a given guild to a text channel in the given guild by passing the id of the channel.
        Args:
            ctx: The Context of the message sent.
            args: Used to specify extra actions for the set command to perform.
            given_channel_id: The id of the channel to set as the music channel.
        """
        if given_channel_id is None and args is not None:
            # No args was given, but a channel id was given
            given_channel_id = args
            args = None

        if given_channel_id is None:
            # No given channel id.. exit
            message = Embed(title="A channel id is a required argument", colour=EmbedColours.red())
            await self.__send_timed_message(ctx.channel, message, timer=30)
            #raise UserInputError(message="A channel id is a required argument")
            return

        is_valid_channel_id = (len(given_channel_id) == 18) and given_channel_id.isdigit()

        if not is_valid_channel_id:
            # The channel id given is not valid.. exit
            message = Embed(title="The id given was not a valid id", colour=EmbedColours.red())
            await self.__send_timed_message(ctx.channel, message, timer=30)
            #raise UserInputError(message="The id given was not a valid id")
            return

        guild_text_channel_ids = [str(x.id) for x in ctx.guild.text_channels]

        if str(given_channel_id) not in guild_text_channel_ids:
            # The channel id given not for a text channel.. exit
            message = Embed(title="The id given must be of a text channel", colour=EmbedColours.red())
            await self.__send_timed_message(ctx.channel, message, timer=30)
            #raise UserInputError(message="The id given must be of a text channel")
            return

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
        """
        Sends a tagged channel if the music channel has been set, otherwise will send an error message.
        Args:
            ctx: The context of the message.
        """
        current_channel_for_guild = db_gateway().get('music_channels', params={
            'guild_id': ctx.author.guild.id})

        if current_channel_for_guild[0].get('channel_id'):
            # If the music channel has been set in the guild
            id_as_channel = [x for x in ctx.guild.channels if x.id == current_channel_for_guild[0].get('channel_id')][0]
            await ctx.channel.send(f"Music channel is set to {id_as_channel.mention}")
        else:
            await ctx.channel.send("Music channel has not been set")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def resetmusicchannel(self, ctx):
        """
        If the music channel is set, clear it and re-setup the channel with the correct messages. Otherwise do nothing.
        Args:
            ctx: The context of the message.
        """
        current_channel_for_guild = db_gateway().get('music_channels', params={
            'guild_id': ctx.author.guild.id})

        if current_channel_for_guild[0].get('channel_id'):
            # If the music channel has been set for the guild
            await self.__setup_channel(ctx, arg='-c', channel_id=current_channel_for_guild[0].get('channel_id'))
            message = "Successfully reset the music channel"
            await self.__send_timed_message(ctx.channel, message, timer=20, is_embed=False)
        else:
            await ctx.channel.send("Music channel has not been set")

    @commands.command()
    async def removesong(self, ctx: Context, song_index=None):
        """
        Remove a song at an index from the current queue.
        Args:
            ctx: The context of the message.
            song_index: The index of the song to remove. Index starting from 1.
        """
        if not self.__check_valid_user_vc(ctx):
            # Check if the user is in a valid voice channel
            message = Embed(title="You are not in the voice channel with the bot", colour=EmbedColours.orange())
            await self.__send_timed_message(ctx.channel, message)
            return

        if len(self._currently_active.get(ctx.guild.id).get('queue')) < (int(song_index) - 1):
            # The index given is out of the bounds of the current queue
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
        """
        Pause the current playback.
        Args:
            ctx: The context of the song.
        """
        if not self.__check_valid_user_vc(ctx):
            # Checks if the user is in a valid voice channel
            return

        self.__pause_song(ctx.guild.id)
        await ctx.message.delete()
        message = Embed(title="Song Paused", colour=EmbedColours.music())
        await self.__send_timed_message(ctx.channel, message, timer=20)

    @commands.command()
    async def resumesong(self, ctx: Context):
        """
        Resume the current playback of the song.
        Args:
            ctx: The context of the message.
        """
        if not self.__check_valid_user_vc(ctx):
            # Checks if the user is in a valid voice channel
            return

        self.__resume_song(ctx.guild.id)
        await ctx.message.delete()
        message = Embed(title="Song Resumed", colour=EmbedColours.music())
        await self.__send_timed_message(ctx.channel, message, timer=20)

    @commands.command()
    async def kickbot(self, ctx: Context):
        """
        Remove the bot from the voice channel. Will also reset the queue.
        Args:
            ctx: The context of the message.
        """
        if not self.__check_valid_user_vc(ctx):
            # Checks if the user is in a valid voice channel
            return

        await self.__remove_active_channel(ctx.guild.id)
        await ctx.message.delete()
        message = Embed(title="I have left the Voice Channel", colour=EmbedColours.music())
        await self.__send_timed_message(ctx.channel, message, timer=20)

    @commands.command()
    async def skipsong(self, ctx: Context):
        """
        Skips the current song. If there are no more songs in the queue, the bot will leave.
        Args:
            ctx: The context of the message.
        """
        if not self.__check_valid_user_vc(ctx):
            # Checks if the user is in a valid voice channel
            return

        # TODO: Decide if the bot should leave the vc if the queue is empty after skipping.
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
        """
        Sends a message of the current queue to the channel the messasge was sent from.
        Args:
            ctx: The context of the message.
        """

        # We don't want the song channel to be filled with the queue as it already shows it
        music_channel_in_db = db_gateway().get('music_channels', params={'guild_id': ctx.guild.id})
        if ctx.message.channel.id == music_channel_in_db[0].get('channel_id'):
            # Message is in the songs channel
            return

        queue_string = self.__make_queue_list(ctx.guild.id)

        await ctx.channel.send(queue_string)

    @commands.command()
    async def clearqueue(self, ctx: Context):
        """
        Clear the current queue of all songs. The bot won't leave the vc with this command.
        Args:
            ctx: The context of the message.
        """

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
        """
        Shuffle the current queue of songs. Does not include the current song playing, which is index 0. Won't bother
        with a shuffle unless there are 3 or more songs.
        Args:
            ctx: The context of the message.
        """

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
        """
        The handle the is called whenever a message is sent in the music channel of a guild.
        Args:
            message: The message sent to the music channel.
        """

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
                # The bot is already being used in the current guild.
                send = Embed(title="I am already in another voice channel in this server", colour=EmbedColours.orange())
                await message.delete()
                await self.__send_timed_message(message.channel, send, timer=10)
                return

        # Check if the loops for marked and active channels are running.
        self.__check_loops_alive()

        # Splits multiline messages into a list. Single line messages return a list of [message]
        split_message = message.content.split("\n")
        partial_success = True

        # Add each line of the message to the queue
        for line in split_message:
            partial_success = partial_success or await self.process_song_request(message, line)

        # If any of the songs were successful, ensure that the channel is no long marked as inactive.
        if partial_success:
            if message.guild.id in self._marked_channels:
                # Remove the channel from marked channels as it is no longer inactive
                self._marked_channels.pop(message.guild.id)

        await message.delete()

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

    def __create_time_remaining_field(self, guild_id, embed):
        """
        Create the field for an embed that displays how much time a server has left to play songs in that day.
        Args:
            guild_id: The guild id of the guild
            embed: The embed message to add the field to.
        """
        # Get the time remaining
        guild_time = self._time_allocation[guild_id]
        seconds_remain = str(guild_time % 60)
        # Format the seconds part of the time.
        if len(seconds_remain) == 1:
            seconds_remain += '0'

        # Get the total time allowed.
        allowed_time = self._allowed_time
        seconds_allowed = str(self._allowed_time % 60)
        # Format the seconds part of the time.
        if len(seconds_allowed) == 1:
            seconds_allowed += '0'

        # Add the field to the embed.
        embed.add_field(name=f"Minutes Remaining Today: {guild_time // 60}:{seconds_remain} / "
                             f"{allowed_time // 60}:{seconds_allowed}",
                        value="Blame Ryan :upside_down:")

    async def __setup_channel(self, ctx: Context, channel_id, arg):
        """
        Sends the preview and queue messages to the music channel and adds the ids of the messages to the database.
        If the music channel is not empty and the correct arg is set, also clears the channel.
        Args:
            ctx: The context of the messages, used to send the messages to the channels.
            channel_id: The id of the music channel
            arg:
        """
        channel_instance: TextChannel = [x for x in ctx.guild.text_channels if x.id == channel_id][0]
        channel_messages = await channel_instance.history().flatten()
        if len(channel_messages) > 0:
            # If there are messages in the channel
            if arg is None:
                await ctx.channel.send(
                    "The channel is not empty, if you want to clear the channel for use, use !setmusicchannel -c <id>")
            elif arg == '-c':
                for message in channel_messages:
                    await message.delete()

        temp_default = self._no_current_song_message
        self.__create_time_remaining_field(ctx.guild.id, temp_default)

        # Send the messages and record their ids
        default_queue_message = await channel_instance.send(self._empty_queue_message)
        default_preview_message = await channel_instance.send(embed=temp_default)

        db_gateway().update('music_channels', set_params={'queue_message_id': int(default_queue_message.id)},
                            where_params={'guild_id': ctx.author.guild.id})

        db_gateway().update('music_channels', set_params={'preview_message_id': int(default_preview_message.id)},
                            where_params={'guild_id': ctx.author.guild.id})

    async def __remove_active_channel(self, guild_id) -> bool:
        """
        Disconnect the bot from the voice channel and remove it from the currently active channels.
        Args:
            guild_id: The id of the guild to remove the bot from.

        Returns: True if the removal was successful, False otherwise.

        """
        if guild_id in self._currently_active:
            # If the guild is currently active.
            voice_client: VoiceClient = self._currently_active.get(guild_id).get('voice_client')
            await voice_client.disconnect()
            self._currently_active.get(guild_id)['queue'] = [None]
            await self.__check_next_song(guild_id)
            self._currently_active.pop(guild_id)
            return True
        return False

    async def __update_channel_messages(self, guild_id):
        """
        Update the queue and preview messages in the music channel.
        Args:
            guild_id: The guild id of the guild to be updated.
        """

        # Get the guild_id as a discord.Guild object
        current_guild_instance = [x for x in self._bot.guilds if x.id == guild_id][0]

        guild_db_data = db_gateway().get('music_channels', params={'guild_id': guild_id})[0]

        # Get the ids of the queue and preview messages
        queue_message_id = guild_db_data.get('queue_message_id')
        preview_message_id = guild_db_data.get('preview_message_id')

        # Create the updated messages
        queue_message = self.__update_queue_message(guild_id)
        preview_message = self.__update_preview_message(guild_id)

        music_channel_id = guild_db_data.get('channel_id')
        # Get the music channel id as a discord.TextChannel object
        music_channel_instance = [x for x in current_guild_instance.text_channels if x.id == music_channel_id][0]

        # Get the message ids as discord.Message objects
        queue_message_instance: Message = [x for x in await music_channel_instance.history().flatten()
                                           if x.id == queue_message_id][0]
        preview_message_instance: Message = [x for x in await music_channel_instance.history().flatten()
                                             if x.id == preview_message_id][0]

        # Update the messages
        await queue_message_instance.edit(content=queue_message)
        await preview_message_instance.edit(embed=preview_message)

    async def __check_next_song(self, guild_id):
        """
        Check if there is another song to play after the current one. If no more songs, mark the channel as in active,
        otherwise play the next song.
        Args:
            guild_id: The id of the guild to check the next song in.
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

    async def __send_timed_message(self, channel, message, timer=15, is_embed=True):
        """
        Sends a message to a specific channel that gets deleted  after a given amount of seconds.
        Args:
            channel: The channel to send the message to.
            message: The message to send.
            timer: The number of seconds before the message is deleted.
            is_embed: If the message param is an embed message or just a string.
        """
        if is_embed:
            # The message param is an embed message
            timed_message = await channel.send(embed=message)
        else:
            timed_message = await channel.send(message)
        await timed_message.delete(delay=timer)

    @tasks.loop(seconds=1)
    async def check_active_channels(self):
        """
        Check the current channels if they are still playing. If no longer playing, check for the next song. Also checks
        if the bot is in a channel by itself.
        """
        # Create a copy to avoid concurrent changes to _currently_active
        active_copy = self._currently_active.copy()
        for guild_id in active_copy.keys():
            if not self._currently_active.get(guild_id).get('voice_client').is_playing() \
                    and not self._currently_active.get(guild_id).get('voice_client').is_paused():
                # Check any voice_clients that are no longer playing but that aren't just paused
                await self.__check_next_song(guild_id)
            elif self.__check_empty_vc(guild_id):
                # Check if the bot is in a channel by itself
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
                # The voice channel has no members in it
                asyncio.create_task(self.__remove_active_channel(guild_id))
                self._marked_channels.pop(guild_id)

        if len(marked_copy.keys()) == 0:
            # Stop the task when no channels to check
            self.check_marked_channels.stop()

    @tasks.loop(hours=24)
    async def reset_music_allowance(self):
        """
        Reset the number of minutes a guild can use per day. Runs every 24hrs
        """
        self._time_allocation = defaultdict(lambda: self._allowed_time)

    def __check_empty_vc(self, guild_id):
        """
        Checks if the voice channel the bot is in has no members in it.
        Args:
            guild_id: The id of the guild that is being checked.

        Returns: True if the channel is empty or if the bot isn't in a channel. False otherwise.

        """
        voice_client = self._currently_active.get(guild_id).get('voice_client')
        if not voice_client:
            # The bot is not in a channel, just return True
            return True
        voice_channel = voice_client.channel
        members_not_bots = [x for x in voice_channel.members if not x.bot]

        if len(members_not_bots) > 0:
            # There are members in the channel
            return False
        else:
            return True

    def __add_new_active_channel(self, guild_id, channel_id=None, voice_client=None) -> bool:
        """
        Add a new voice channel to the currently active channels.
        Args:
            guild_id: The id of the guild the voice channel is in.
            channel_id: The id of the voice channel the bot is joining.
            voice_client: The voice client instance of the bot.

        Returns: True if successfully added to the list of active channels. False otherwise.

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

    def __play_queue(self, guild_id):
        """
        Starts the playback of the song at the top of the queue.
        Args:
            guild_id: The id of the guild the bot is playing in.

        Returns: True if the playback was successful, False otherwise.
        """

        if len(self._currently_active.get(guild_id).get('queue')) < 1:
            # Queue is empty.. exit
            return False

        voice_client: VoiceClient = self._currently_active.get(guild_id).get('voice_client')

        if voice_client.is_playing():
            # Stop the bot if it is playing
            voice_client.stop()

        # Get the top song
        song = self._currently_active.get(guild_id).get('queue')[0]

        # Get the information about the song
        song_data = self.__download_video_info(song.get('link'), download=False)
        song_formatted = self.__format_download_data(song_data)

        # Check if the allowed time for the day is used up
        length = song_formatted.get('length')

        self._time_allocation[guild_id] = self._time_allocation[guild_id] - length

        if self._time_allocation[guild_id] < 0:
            # If the allocated time is used up set it to 0 and exit out
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
        """
        Pauses the playback of a specific guild if the guild is playing. Otherwise nothing.
        Args:
            guild_id: The id of the guild to pause the playback in.
        """
        if self._currently_active.get(guild_id).get('voice_client').is_playing():
            # Can't pause if the bot isn't playing
            voice_client: VoiceClient = self._currently_active.get(guild_id).get('voice_client')
            voice_client.pause()

    def __resume_song(self, guild_id):
        """
        Resumes the playback of a specific guild if the guild is paused. Otherwise nothing.
        Args:
            guild_id: The id of the guild to resume the playback in.
        """
        if self._currently_active.get(guild_id).get('voice_client').is_paused():
            # Only able to resume if currently paused
            voice_client: VoiceClient = self._currently_active.get(guild_id).get('voice_client')
            voice_client.resume()

    def __check_valid_user_vc(self, ctx: Context):
        """
        Checks if the user: A) Is in a voice channel, B) The voice channel is the same as the voice channel the bot is
        connected to, C) The message sent was in the music text channel.
        Args:
            ctx: The context of the message sent.

        Returns: If all the above conditions are met, True, otherwise False.
        """
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
        """
        Update the queue message in a given guild.
        Args:
            guild_id: The guild id of the guild to update the queue message in.

        Returns: A string of the queue that is to be the new queue message.

        """
        if len(self._currently_active.get(guild_id).get('queue')) == 0:
            # If the queue is empty.
            updated_queue_message = self._empty_queue_message
        else:
            updated_queue_message = self.__make_queue_list(guild_id)

        return updated_queue_message

    def __update_preview_message(self, guild_id):
        """
        Update the preview message in a given guild.
        Args:
            guild_id: The guild id of the guild to update the preview message in.

        Returns: An embed message for the updated preview message in a given guild id.

        """
        if len(self._currently_active.get(guild_id).get('queue')) == 0:
            # If the queue is empty, provide the empty queue embed.
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
        """
        Create a formatted string representing the queue from a server.
        Args:
            guild_id: The guild of the queue to turn into a string.

        Returns: A string representing the queue list.
        """
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
        """
        Turn a list into a string.
        Args:
            songs: The list of songs to turn into a string

        Returns: A string representing a queue list.
        """
        string = ""
        for x in range(len(songs)):
            index = x + 1
            item = songs[x]
            # string += f"{index}. {item.get('title')} - {item.get('length')} \n"
            string += f"{index}. {item.get('title')}\n"

        return string

    async def process_song_request(self, message, request):
        """
        Process a song request.
        Args:
            message: The instance of the discord message that sent the request.
            request: The actual message request.

        Returns: The success value of if the song was added to the queue or not.

        """
        # 0 is playlist, 1 is url, 2 is string
        message_type = self.__determine_message_type(request)

        if message_type == 0:
            # If the request given is a playlist
            playlist_links = self.__find_playlist_songs(request)
            playlist_info = self.__get_playlist_info_from_links(playlist_links)
            success = await self.__add_to_queue(message.guild.id, playlist_info)
        else:
            # If the request is either a link or a string that needs to be queried
            songs_found = self.__find_song(request, message_type)
            success = await self.__add_to_queue(message.guild.id, songs_found)

        if success:
            # If adding the song to the queue was successful
            feedback = Embed(title="Added request to queue!", colour=EmbedColours.music())
            await self.__send_timed_message(message.channel, feedback, timer=5, is_embed=True)
        else:
            feedback = Embed(title="An error occurred while adding your request to the queue",
                             colour=EmbedColours.orange())
            await self.__send_timed_message(message.channel, feedback, timer=10, is_embed=True)

        return success

    def __find_song(self, message, message_type):
        """
        Finds the information about a song. Either a link or a string request.
        Args:
            message: The request to find information about. Either a string or a video url.
            message_type: The type of message.

        Returns: A list of dicts containing basic information about the request.

        """
        if message_type == 1:
            links = [message]
            return self.__get_playlist_info_from_links(links)
        else:
            return self.__find_query(message)

    def __find_playlist_songs(self, playlist_link):
        """
        Gets the individual song links from a playlist link.
        Args:
            playlist_link: The link to the playlist to find the urls from.

        Returns: A list of YouTube urls.
        """

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
        """
        Get the basic information about a list of links.
        Args:
            links: The list of links to find the information about.

        Returns: A list of dicts that hold basic information about a link.

        """
        # Grequest exception handler
        def exception_handler(request, exception):
            print(str(request) + ' failed with exception: ' + str(exception))

        # Create the requests for all the links.
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
        """
        Query youtube to find a search result and get return a link to the top hit of that query
        Args:
            message: The message to query youtube with.

        Returns: A link and some other basic information regarding the query.
        """
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
        """
        Determine if the message received is a video url, playlist url or a string that needs to be queried.
        Args:
            message: The message to determine the type of.

        Returns: An integer representing the message type.
        """
        if self.__is_url(message):
            # The message is a url
            if re.search(r'(playlist)', message):
                # The message is a playlist
                return 0
            else:
                return 1
        else:
            # The message is a string
            return 2

    def __format_playlist_data(self, playlist_data):
        """
        Format the data for a list of song data.
        Args:
            playlist_data: The list of song data to format.

        Returns: The playlist data but only with useful information.
        """

        entries = playlist_data.get('entries')
        formatted_entries = []
        for entry in entries:
            formatted_entries.append(self.__format_download_data(entry))
        return formatted_entries

    def __format_download_data(self, download_data):
        """
        Format a songs data to remove the useless data.
        Args:
            download_data: The song data to format.

        Returns: A dictionary of data which is a subset of the param download_data
        """

        stream, rate = self.__get_opus_stream(download_data.get('formats'))
        useful_data = {'title': download_data.get('title'), 'id': download_data.get('id'),
                       'link': download_data.get('webpage_url'), 'length': download_data.get('duration'),
                       'stream': stream,
                       'bitrate': rate,
                       'thumbnail': self.__get_thumbnail(download_data.get('thumbnails')),
                       'filename': download_data.get('filename')}
        return useful_data

    def __get_opus_stream(self, formats):
        """
        Get the opus formatted streaming link from the formats dictionary.
        Args:
            formats: The formats dictionary that contains the different streaming links.

        Returns: A streaming url that links to an opus stream and the bit rate of the stream.

        """
        # Limit the codecs to just opus, as that is required for streaming audio
        opus_formats = [x for x in formats if x.get('acodec') == 'opus']

        # Sort the formats from highest br to lowest
        sorted_opus = list(sorted(opus_formats, key=lambda k: float(k.get('abr')), reverse=True))

        chosen_stream = sorted_opus[self._bitrate_quality]

        return chosen_stream.get('url'), chosen_stream.get('abr')

    def __get_thumbnail(self, thumbnails):
        """
        Get the thumbnail from url from the thumbnails dictionary.
        Args:
            thumbnails: The dictionary of thumbnail urls.

        Returns: A url linking to the video thumbnail.
        """
        # Sort by thumbnail size
        sorted_thumbnails = list(sorted(thumbnails, key=lambda k: int(k.get('height')), reverse=True))

        return sorted_thumbnails[0].get('url')

    def __is_url(self, string):
        """
        Returns if the string given is a url.
        Args:
            string: The string to check.

        Returns: True if the string is a url. False otherwise.

        """
        # Match desktop, mobile and playlist links
        re_desktop = r'(http[s]?://)?youtube.com/(watch\?v)|(playlist\?list)='
        re_mobile = r'(http[s]?://)?youtu.be/([a-zA-Z]|[0-9])+'

        re_string = "(" + re_desktop + ") | (" + re_mobile + ")"

        if re.search(re_desktop, string) or re.search(re_mobile, string):
            return True
        return False

    async def __add_to_queue(self, guild_id, song):
        """
        Add the given song to the queue in a guild.
        Args:
            guild_id: The id of the guild to add the song to the queue.
            song: The song to add to the queue.

        Returns: True if the addition was successful. False otherwise.
        """

        try:
            if isinstance(song, list):
                # If the song given is a list
                for item in song:
                    self._currently_active.get(guild_id).get('queue').append(item)
            else:
                self._currently_active.get(guild_id).get('queue').append(song)
            # self._currently_active.get(guild_id).get('queue').extend(song)

            if not self._currently_active.get(guild_id).get('voice_client').is_playing():
                # If we are not currently playing, start playing
                self.__play_queue(guild_id)

            await self.__update_channel_messages(guild_id)
            return True
        except Exception as e:
            print("There was an error while adding to the queue: \n" + str(e))
            return False

    def __download_video_info(self, link, download=False):
        """
        Download all the information about a given link from youtube.
        Args:
            link: The link to find the information about.
            download: If the song should also be downloaded to a file.

        Returns: The information about a youtube url.
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

    def __clean_youtube_results(self, results) -> list:
        """
        Remove unnecessary data from a list of the youtube information gathered.
        Args:
            results: The list of youtube information gathered from links.

        Returns: A list of data that has the unnecessary removed from each of the values.
        """
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
            new_result['localfile'] = self._song_location + re.sub(r'\W+', '', new_result.get('title')) + \
                                      f"{new_result.get('id')}.mp3"

            cleaned_data.append(new_result)

        return cleaned_data

    def __search_youtube(self, message: str) -> list:
        """
        Search youtube with a given string.
        Args:
            message: The message to query youtube with.

        Returns: A dictionary having the information about the query.

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
        cleaned_results = self.__clean_youtube_results(music_results)

        end = time.time()

        print("Time taken to query youtube: " + str(end - start))

        return cleaned_results


def setup(bot):
    bot.add_cog(MusicCog(bot))
