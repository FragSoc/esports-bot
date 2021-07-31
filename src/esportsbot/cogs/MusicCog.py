import asyncio
import datetime
import functools
import logging
import os
import re
import sys
import time
from enum import IntEnum
from random import shuffle
from urllib.parse import parse_qs, urlparse

import googleapiclient.discovery
import youtube_dl
from discord import ClientException, Colour, Embed, FFmpegPCMAudio, PCMVolumeTransformer, TextChannel
from discord.ext import commands, tasks
from youtubesearchpython import VideosSearch

from esportsbot.db_gateway import DBGatewayActions
from esportsbot.lib.discordUtil import send_timed_message
from esportsbot.models import Music_channels


# A discord command check that the command is in the music channel:
def check_music_channel(context):
    guild_id = context.guild.id
    if guild_data := DBGatewayActions().get(Music_channels, guild_id=guild_id):
        if channel_id := guild_data.channel_id:
            return context.channel.id == channel_id
    return False


# A delete after done command wrapper:
def delete_after():
    def wrapper(func):
        @functools.wraps(func)
        async def wrapped(*args, **kwargs):
            context = args[1]
            if not isinstance(context, commands.Context):
                raise ValueError("The second arg for a command should be a commands.Context object")
            res = await func(*args, **kwargs)
            await context.message.delete()
            return res

        return wrapped

    return wrapper


class EmbedColours:
    green = Colour(0x1f8b4c)
    orange = Colour(0xe67e22)
    red = Colour(0xe74c3c)
    music = Colour(0xd462fd)


class MessageTypeEnum(IntEnum):
    youtube_url = 0
    youtube_playlist = 1
    youtube_thumbnail = 2
    string = 3
    invalid = 4


EMPTY_QUEUE_MESSAGE = "Join a Voice Channel and search a song by name or paste a YouTube url.\n" \
                      "**__Current Queue:__**\n"

ESPORTS_LOGO_URL = "http://fragsoc.co.uk/wpsite/wp-content/uploads/2020/08/logo1-450x450.png"

EMPTY_PREVIEW_MESSAGE = Embed(
    title="No song currently playing",
    colour=EmbedColours.music,
    footer="Use the prefix ! for commands"
)
EMPTY_PREVIEW_MESSAGE.set_image(url=ESPORTS_LOGO_URL)
EMPTY_PREVIEW_MESSAGE.set_footer(text="Definitely not made by fuxticks#1809 on discord")

GOOGLE_API_KEY = os.getenv("GOOGLE_API")
YOUTUBE_API = googleapiclient.discovery.build("youtube", "v3", developerKey=GOOGLE_API_KEY)

FFMPEG_BEFORE_OPT = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"

TIMEOUT_DELAY = 60


class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.db = DBGatewayActions()
        self.user_strings = bot.STRINGS["music"]
        self.unhandled_error_string = bot.STRINGS["command_error_generic"]
        self.music_channels = self.load_channels()
        self.active_guilds = {}
        self.playing_guilds = []
        self.inactive_guilds = {}
        self.logger.info(f"Finished loading {__name__}... cog is ready!")

    def load_channels(self):
        """
        Loads the currently set music channels from the DB.
        :return: A dictionary of the guild and its music channel id.
        """
        channels = self.db.list(Music_channels)
        channels_dict = {}
        for channel in channels:
            channels_dict[channel.guild_id] = channel.channel_id
        return channels_dict

    @commands.Cog.listener()
    async def on_message(self, message):
        """
        Handles messages that are not sent by a bot or that are Direct Messages.
        :param message: The message received by the bot.
        """
        if not message.author.bot and message.guild:
            guild_id = message.guild.id
            music_channel = self.music_channels.get(guild_id)
            if music_channel:
                if await self.on_message_handle(message):
                    await message.delete()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """
        If the bot is forcefully removed from the channel by an admin, we want to ensure that the bot doesn't think it is
        still in a voice channel.
        :param member: The member triggering the change.
        :param before: The voice state before.
        :param after: The voice state after.
        """
        if member.id != self.bot.user.id:
            if not after.channel:
                # If the user has left a voice channel
                if member.guild.id in self.active_guilds:
                    guild_vc = self.active_guilds.get(member.guild.id).get("voice_channel")
                    if before.channel.id == guild_vc.id:
                        # And that voice channel is the one we are in
                        # And the only users in the channel are bots
                        non_bots = [x for x in guild_vc.members if not x.bot]
                        if not non_bots:
                            # Leave the channel
                            await self.remove_active_guild(member.guild)
            return

        if not before.channel and not after.channel:
            # This should never happen but is here to ensure it won't cause an issue.
            return

        if not before.channel and after.channel:
            # Bot has joined a voice channel.
            self.new_active_guild(after.channel.guild)
            return

        if before.channel and not after.channel:
            # Bot has left a voice channel.
            await self.remove_active_guild(before.channel.guild)
            return

        if before.channel and after.channel:
            # Bot has been moved to another voice channel.
            self.update_voice_client(after.channel.guild)
            return

    def run_tasks(self):
        if not self.check_inactive_guilds.is_running() or self.check_inactive_guilds.is_being_cancelled():
            self.check_inactive_guilds.start()

        if not self.check_playing_guilds.is_running() or self.check_playing_guilds.is_being_cancelled():
            self.check_playing_guilds.start()

    @tasks.loop(seconds=5)
    async def check_playing_guilds(self):
        """
        Check the guilds who's voice client status is playing.
        """
        if not self.playing_guilds:
            # Stop running if no guilds playing.
            self.check_playing_guilds.cancel()
            self.check_playing_guilds.stop()
            return

        to_remove = []

        now = datetime.datetime.now()

        for guild_id in self.playing_guilds:
            if guild_id not in self.active_guilds:
                # If the guild has been stopped from playing elsewhere it will no longer be in active guilds.
                to_remove.append(guild_id)
                continue
            voice_client = self.active_guilds.get(guild_id).get("voice_client")
            if not voice_client.is_playing() and not voice_client.is_paused():
                if not await self.play_queue(guild_id):
                    # play queue will return False if there is nothing to play or if it was unable to play something.
                    self.inactive_guilds[guild_id] = now
                    to_remove.append(guild_id)
                    self.run_tasks()

        for guild_id in to_remove:
            self.playing_guilds.remove(guild_id)

    @tasks.loop(seconds=60)
    async def check_inactive_guilds(self):
        """
        Check the guilds that are in a voice channel but not playing anything.
        """
        if not self.inactive_guilds:
            # Stop running if no guilds active.
            self.check_inactive_guilds.cancel()
            self.check_inactive_guilds.stop()
            return

        to_remove = []

        now = datetime.datetime.now()

        for guild_id in self.inactive_guilds:
            if (now - self.inactive_guilds.get(guild_id)).seconds > TIMEOUT_DELAY:
                # If the bot has been inactive for the given timeout delay.
                to_remove.append(guild_id)

        for guild_id in to_remove:
            # These guilds have reached the timeout and should be disconnected.
            self.inactive_guilds.pop(guild_id)
            guild = self.active_guilds.get(guild_id).get("voice_channel").guild
            await self.remove_active_guild(guild)

    def new_active_guild(self, guild):
        """
        Add a new guild to the ones that are currently active.
        :param guild: The that now has an active instance of the bot in a voice channel.
        :return: A dictionary of the data stored about the current playback status in the guild.
        """
        self.logger.info(f"Adding an active channel in {guild.name}")
        guild_id = guild.id
        guild_data = {
            "voice_channel": guild.me.voice.channel,
            "voice_client": self.get_guild_client(guild),
            "queue": [],
            "current_song": None,
            "volume": 1
        }
        self.active_guilds[guild_id] = guild_data
        return guild_data

    def update_voice_client(self, guild):
        """
        Update the voice channel and voice client of the bot if it has become disconnected or been moved to a different
        voice channel.
        :param guild: The guild that needs updating.
        :return: A dictionary of the data stored about the current playback status in the guild.
        """
        self.logger.info(f"Updating the voice client for {guild.name}")
        if guild.id not in self.active_guilds:
            # If it has been removed from the active guilds dict, create a new one.
            return self.new_active_guild(guild)
        else:
            # Otherwise keep the rest of the data and just update the voice channel and voice client.
            guild_id = guild.id
            guild_data = {
                "voice_channel": guild.me.voice.channel,
                "voice_client": self.get_guild_client(guild),
                "queue": self.active_guilds.get(guild_id).get("queue"),
                "current_song": self.active_guilds.get(guild_id).get("current_song"),
                "volume": self.active_guilds.get(guild_id).get("volume")
            }
            self.active_guilds[guild_id] = guild_data
            return guild_data

    def get_guild_client(self, guild):
        """
        Get a voice client of the bot in a given guild.
        :param guild: The guild to find the voice client of.
        :return: A voice client if there is one, else None.
        """
        voice_clients = self.bot.voice_clients
        for client in voice_clients:
            if client.guild.id == guild.id:
                return client
        return None

    async def remove_active_guild(self, guild):
        """
        Remove a guild from being active. Will also attempt to disconnect the bot from a voice channel.
        :param guild: The guild to remove activity from.
        :return: A boolean if the removal was successful.
        """
        self.logger.info(f"Removing active channel for {guild.name}")
        try:
            guild_data = self.active_guilds.pop(guild.id)
            await guild_data.get("voice_client").disconnect()
            return True
        except ClientException:
            return False
        except AttributeError:
            return False
        except KeyError:
            return False

    async def find_music_channel_instance(self, guild):
        """
        Find the instance of the music channel in a given guild.
        :param guild: The guild to find the music channel in.
        :return: A text channel if the text channel exists, else None.
        """
        current_music_channel = self.db.get(Music_channels, guild_id=guild.id)
        if not current_music_channel:
            return None

        channel_instance = guild.get_channel(current_music_channel.channel_id)
        if not channel_instance:
            channel_instance = await guild.fetch_channel(current_music_channel.channel_id)

        if not channel_instance:
            # Remove the currently set music channel as it doesn't exist anymore.
            current_music_channel.channel_id = None
            self.db.update(current_music_channel)
            return None

        return channel_instance

    async def on_message_handle(self, message):
        """
        Handles when a message is sent to a music channel.
        :param message: The message sent to the music channel.
        :return: True if the message was handled by this function. False if the message was a command.
        """
        try:
            if message.content.startswith(self.bot.command_prefix):
                # Allow commands to be handled by the bot command handler.
                return False

            if not await self.join_member(message.author):
                # If we were unable to join the member, tell them why:
                if not message.author.voice:
                    await send_timed_message(channel=message.channel, content=self.user_strings["unable_to_join"])
                    return True
                if not message.author.voice.channel.permissions_for(message.guild.me).connect:
                    await send_timed_message(channel=message.channel, content=self.user_strings["no_connect_perms"])
                    return True

            # Split the message into it's lines and treat each non-blank line as a request.
            message_content = re.sub(r"(`)+", "", message.content)
            request_options = message_content.split("\n")
            cleaned_requests = [k for k in request_options if k not in ('', ' ')]

            debug_start_time = time.time()
            request_tasks = []
            for request in cleaned_requests:
                request_tasks.append(self.process_request(message.guild.id, request))

            results = await asyncio.gather(*request_tasks)
            debug_end_time = time.time()

            self.logger.info(
                f"Processed {len(cleaned_requests)} song(s) in {debug_end_time - debug_start_time} seconds for "
                f"{message.guild.name} and got {results.count(True)} successful result(s)"
            )

            failed_songs = ""

            for i in range(len(results)):
                if not results[i]:
                    failed_songs += f"{i + 1}. {cleaned_requests[i]}\n"

            # If any of the songs had errors, send a message:
            if results.count(False) >= 1:
                await send_timed_message(
                    channel=message.channel,
                    content=self.user_strings["song_process_failed"].format(songs=failed_songs),
                    timer=10
                )

            # If any songs succeeded, ensure that the bot is not marked as inactive.
            if results.count(True) >= 1:
                if message.guild.id in self.inactive_guilds:
                    self.inactive_guilds.pop(message.guild.id)

            self.run_tasks()

            return True
        except Exception as e:
            await send_timed_message(message.channel, content=self.unhandled_error_string, timer=120)
            self.logger.error(f"There was an error handling the following message: {message.content} \n {e!s}")
            return True

    async def process_request(self, guild_id, request):
        """
        Processes a song request and adds it to the queue.
        :param guild_id: The ID of the guild the song request is in.
        :param request: The song requested.
        :return: True if the song was added to the queue successfully, else False.
        """
        request_type = self.find_request_type(request)
        if request_type == MessageTypeEnum.youtube_url or request_type == MessageTypeEnum.youtube_playlist:
            # The request was a YouTube video or playlist
            youtube_api_response = self.get_youtube_request(request, request_type)
            formatted_response = self.format_youtube_response(youtube_api_response)
        elif request_type == MessageTypeEnum.string:
            # The request was a string
            query_response = self.query_request(request)
            formatted_response = self.format_query_response(query_response)
        else:
            # The request was in an invalid format
            return False
        res = await self.add_songs_to_queue(formatted_response, guild_id)
        await self.update_messages(guild_id)
        return res

    def find_request_type(self, request):
        """
        Find what kind of string the request is. If the string is a URL, determine what kind of URL it is.
        :param request: The request to identify.
        :return: A MessageTypeEnum depicting the type of string.
        """
        if request.startswith("https://") or request.startswith("http://"):
            return self.find_url_type(request)
        else:
            return MessageTypeEnum.string

    @staticmethod
    def find_url_type(url):
        """
        Finds what kind of url the given url is:
        :param url: The url to identify.
        :return: A MessageTypeEnum depicting what type of url the given url is.
        """
        youtube_desktop_signature = r"(http[s]?://)?youtube.com/watch\?v="
        if re.search(youtube_desktop_signature, url):
            return MessageTypeEnum.youtube_url

        youtube_playlist_signature = r"(http[s]?://)?youtube.com/playlist\?list="
        if re.search(youtube_playlist_signature, url):
            return MessageTypeEnum.youtube_playlist

        youtube_mobile_signature = r"(http[s]?://)?youtu.be/([a-zA-Z]|[0-9])+"
        if re.search(youtube_mobile_signature, url):
            return MessageTypeEnum.youtube_url

        youtube_thumbnail_signature = r"(http[s]?://)?i.ytimg.com/vi/([a-zA-Z]|[0-9])+"
        if re.search(youtube_thumbnail_signature, url):
            return MessageTypeEnum.youtube_thumbnail

        return MessageTypeEnum.invalid

    @staticmethod
    def get_youtube_request(request, request_type):
        """
        Get the data for a given request, when that request is a YouTube URL of some kind.
        :param request: The request to find the data of.
        :param request_type: The type of YouTube request the request is.
        :return: A list of dictionaries for each video found that fits the request.
        """
        api_func = YOUTUBE_API.videos() if request_type == MessageTypeEnum.youtube_url else YOUTUBE_API.playlistItems()
        key = "v" if request_type == MessageTypeEnum.youtube_url else "list"

        query = parse_qs(urlparse(request).query, keep_blank_values=True)
        youtube_id = query[key][0]

        api_args = {"part": "snippet", "maxResults": 1 if request_type == MessageTypeEnum.youtube_url else 50}

        if request_type == MessageTypeEnum.youtube_url:
            api_args["id"] = youtube_id
        else:
            api_args["playlistId"] = youtube_id

        api_request = api_func.list(**api_args)

        video_responses = []
        while api_request:
            response = api_request.execute()
            video_responses += response["items"]
            api_request = api_func.list_next(api_request, response)

        return video_responses

    def format_youtube_response(self, response):
        """
        Formats a list of dicts that were gained from a YouTube request to be in a format that is the same across
        request types.
        :param response: The response from the YouTube request.
        :return: A list of dictionaries formatted from the incoming list of dictionaries.
        """
        formatted_response = []
        for item in response:
            snippet = item.get("snippet")
            video_info = {
                "title": snippet.get("title"),
                "thumbnail": self.thumbnail_from_snippet(snippet),
                "link": self.url_from_response(item)
            }
            formatted_response.append(video_info)
        return formatted_response

    @staticmethod
    def thumbnail_from_snippet(snippet):
        """
        Get the thumbnail url from a YouTube `snippet` data-type.
        :param snippet: The snippet from the YouTube response
        :return: A string representing the URL of the thumbnail.
        """
        all_thumbnails = snippet.get("thumbnails")
        if "maxres" in all_thumbnails:
            return all_thumbnails.get("maxres").get("url")
        else:
            any_thumbnail_res = list(all_thumbnails)[0]
            return all_thumbnails.get(any_thumbnail_res).get("url")

    @staticmethod
    def url_from_response(response):
        """
        Create a YouTube URL from the response using the response ID.
        :param response: The response from a YouTube request.
        :return: A string representing the YouTube URL of the video.
        """
        if response.get("kind") == "youtube#video":
            video_id = response.get("id")
        else:
            video_id = response.get("resourceId").get("videoId")
        return "https://youtube.com/watch?=v{}".format(video_id)

    @staticmethod
    def query_request(request):
        """
        Finds the information for a request that is a string.
        :param request: The request to find.
        :return: A 2-tuple of dictionaries.
        """
        results = VideosSearch(request, limit=50).result().get("result")

        if not results:
            # If unable to find any results
            return {}, {}

        # The music result is what will be playing, while official will be used for the title and thumbnail.
        music_result = None
        official_result = None
        for result in results:
            title_lower = result.get("title").lower()
            if not music_result and "lyric" in title_lower or "audio" in title_lower:
                music_result = result
            if not official_result and "official" in title_lower:
                official_result = result
            if official_result and music_result:
                # Break once a video has been found for both.
                break

        ret_val = official_result, music_result

        # If one of them is not found just use the top result.
        if not music_result:
            ret_val = ret_val[0], results[0]
        if not official_result:
            ret_val = results[0], ret_val[1]
        return ret_val

    @staticmethod
    def format_query_response(response):
        """
        Formats the 2-tuple that was gained from a queried request to be in a format that is the same across request types.
        :param response: The response from the query.
        :return: A list of dictionaries of song data.
        """
        official_result, music_result = response

        if not official_result or not music_result:
            # If either of the dictionaries are emtpy, return an empty list with an empty dictionary.
            return [{}]

        official_views = re.sub(r"view(s)?", "", official_result.get("viewCount").get("text").replace(",", ""))
        music_views = re.sub(r"view(s)?", "", music_result.get("viewCount").get("text").replace(",", ""))

        official_views = 0 if official_views is None or "No" in official_views else int(official_views)
        music_views = 0 if music_views is None or "No" in music_views else int(music_views)

        formatted_query = {
            "title":
            official_result.get("title") if official_views > music_views else music_result.get("title"),
            "thumbnail":
            official_result.get("thumbnails")[-1].get("url")
            if official_views > music_views else music_result.get("thumbnails")[-1].get("url"),
            "link":
            music_result.get("link")
        }
        return [formatted_query]

    async def add_songs_to_queue(self, songs, guild_id):
        """
        Add a list of dictionaries representing songs to the queue of a guild.
        :param songs: The list of song dictionaries to add to the the guild.
        :param guild_id: The ID of the guild to add the songs to.
        :return: True if the song was added successfully, False otherwise.
        """
        try:
            if guild_id not in self.active_guilds:
                return False

            ret_val = True
            for song in songs:
                if len(song) != 0:
                    self.active_guilds.get(guild_id)["queue"].append(song)
                else:
                    ret_val = False

            # If we are not currently playing, start playing.
            if not self.active_guilds.get(guild_id).get("voice_client").is_playing():
                return await self.play_queue(guild_id)
            return ret_val
        except Exception as e:
            self.logger.error(f"There was an error adding a song to the queue for guild {guild_id}: {e!s}")
            return False

    async def __play_queue(self, guild_id):
        """
        The internal function for playing the current queue. Should not ever call this function explicitly.
        :param guild_id: The ID of the guild to play the queue of.
        :return: True if playback was started successfully, False otherwise.
        """
        if guild_id not in self.active_guilds:
            return False

        if not len(self.active_guilds.get(guild_id).get("queue")) > 0:
            self.active_guilds.get(guild_id)["current_song"] = None
            return False

        voice_client = self.active_guilds.get(guild_id).get("voice_client")

        # Voice client cannot be playing when calling play(), so must be stopped first.
        if voice_client.is_playing():
            voice_client.stop()

        try:
            next_song = self.set_next_song(guild_id)
            source = PCMVolumeTransformer(
                FFmpegPCMAudio(next_song.get("url"),
                               before_options=FFMPEG_BEFORE_OPT,
                               options="-vn"),
                volume=self.active_guilds.get(guild_id).get("volume")
            )
            voice_client.play(source)
            self.playing_guilds.append(guild_id)
            return True
        except AttributeError:
            return False
        except KeyError:
            return False
        except TypeError:
            return False
        except ClientException:
            return False

    async def play_queue(self, guild_id):
        """
        The function that calls the internal __play_queue, and should be used to initiate the queue playback.
        :param guild_id: The ID of the guild to start the playback in .
        :return: True if playback was started successfully, else False.
        """
        res = await self.__play_queue(guild_id)
        await self.update_messages(guild_id)
        return res

    def set_next_song(self, guild_id):
        """
        Sets the current song to the next song in the queue.
        :param guild_id: The ID of the guild to set the next song of.
        :return: The next song in the queue.
        """
        next_song = self.active_guilds.get(guild_id).get("queue").pop(0)
        current_song = {**self.get_youtube_info(next_song.get("link")), **next_song}
        self.active_guilds.get(guild_id)["current_song"] = current_song
        return current_song

    @staticmethod
    def get_youtube_info(url):
        """
        Download the information required to stream the audio to the voice client.
        :param url: The URL to find the information of.
        :return: A dictionary of data which contains the stream data.
        """
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": "%(title)s-%(id)s.mp3",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        }
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return info

    async def update_messages(self, guild_id):
        """
        Update the queue and preview messages with the current queue and currently playing song in a given guild.
        :param guild_id: The ID of the guild to update the messages of.
        """
        queue_message_content = self.get_updated_queue_message(guild_id)
        preview_message_content = self.get_updated_preview_message(guild_id)

        music_channel_instance = self.bot.get_channel(self.music_channels.get(guild_id))
        if not music_channel_instance:
            music_channel_instance = await self.bot.fetch_channel(self.music_channels.get(guild_id))

        db_item = self.db.get(Music_channels, guild_id=guild_id)

        if not db_item:
            return

        queue_message_instance = await music_channel_instance.fetch_message(db_item.queue_message_id)
        preview_message_instance = await music_channel_instance.fetch_message(db_item.preview_message_id)

        await queue_message_instance.edit(content=queue_message_content)
        await preview_message_instance.edit(embed=preview_message_content)

    def get_updated_queue_message(self, guild_id):
        """
        Gets the most up-to-date message for the current queue information of a given guild.
        :param guild_id: The ID of the guild to get the queue information of.
        :return: A string representing the queue in the guild.
        """
        if guild_id not in self.active_guilds:
            return EMPTY_QUEUE_MESSAGE
        else:
            return self.make_queue_text(guild_id)

    def make_queue_text(self, guild_id):
        """
        Creates the text of the current queue in a given guild.
        :param guild_id: The ID of the guild to get the queue of.
        :return: A string representing the queue in a given guild.
        """
        queue_string = EMPTY_QUEUE_MESSAGE
        queue = self.active_guilds.get(guild_id).get("queue")
        if len(queue) > 25:
            # If the queue is long, truncate it using the start and end with an indicator of how many extra songs are hidden.
            first_ten = queue[:10]
            last_ten = queue[-10:]
            remainder = len(queue) - 20

            first_string = self.reversed_numbered_list(first_ten)
            last_string = self.reversed_numbered_list(last_ten, offset=remainder + 10)

            queue_string += f"{last_string}\n\n... and **`{remainder}`** more ... \n\n{first_string}"
        elif queue:
            queue_string += self.reversed_numbered_list(queue)
        return queue_string

    @staticmethod
    def reversed_numbered_list(list_data, offset=0):
        """
        Get a list as a numbered string, where the first index is at the bottom of the string.
        :param list_data: The song data to turn into a string.
        :param offset: The song index offset to start at.
        :return: A string representing a list.
        """
        reversed_list = list(reversed(list_data))
        biggest = len(list_data) + offset
        return "\n".join(f"{biggest - song_num}. {song.get('title')}" for song_num, song in enumerate(reversed_list))

    @staticmethod
    def numbered_list(list_data, offset=0):
        """
        Get a list as a numbered string, where the first index is at the top of the string.
        :param list_data: The song data to turn into a string.
        :param offset: The song index offset to start at.
        :return: A string representing a list.
        """
        return "\n".join(f"{song_num + 1 + offset}. {song.get('title')}" for song_num, song in enumerate(list_data))

    def get_updated_preview_message(self, guild_id):
        """
        Gets the most up-to-date preview message for a given guild and its currently playing song.
        :param guild_id: The ID of the guild to get the current song of.
        :return: An Embed object of the currently playing song.
        """
        if guild_id not in self.active_guilds:
            return EMPTY_PREVIEW_MESSAGE
        elif not self.active_guilds.get(guild_id).get("current_song"):
            return EMPTY_PREVIEW_MESSAGE
        else:
            current_song = self.active_guilds.get(guild_id).get("current_song")
            updated_message = Embed(
                title=f"Currently Playing: {current_song.get('title')}",
                description=f"Current Volume: {int(self.active_guilds.get(guild_id).get('volume') * 100)}%",
                colour=EmbedColours.music,
                url=current_song.get("link"),
                video=current_song.get("link")
            )
            thumbnail = current_song.get("thumbnail")
            if self.find_url_type(thumbnail) != MessageTypeEnum.youtube_thumbnail:
                thumbnail = ESPORTS_LOGO_URL
            updated_message.set_image(url=thumbnail)
            updated_message.set_footer(text="Definitely not made by fuxticks#1809 on discord")
            return updated_message

    @staticmethod
    async def join_member(member):
        """
        Join a member's voice channel.
        :param member: The member to join.
        :return: A boolean if the bot was able to join the channel.
        """
        try:
            await member.voice.channel.connect()
            return True
        except ClientException:
            return False
        except AttributeError:
            return False

    @commands.command(
        name="setmusicchannel",
        usage="<channel mention> [optional args]",
        help="Sets the music channel to the channel mentioned. To see possible optional args, "
        "go to https://github.com/FragSoc/esports-bot#setmusicchannel-channel-mention-optional-args"
    )
    @commands.has_permissions(administrator=True)
    async def set_music_channel_command(self, context: commands.Context, text_channel: TextChannel):
        """
        Sets the music channel for a given guild to the channel channel mentioned in the command. Extra args can be given to
        indicate some extra process to perform while setting up the channel.
        :param context: The context of the command.
        :param text_channel: The text channel to set the music channel to.
        """
        # Using the text channel as the last official arg in the command, find any extras that occur after with a `-`
        text_channel_str = str(text_channel.mention)
        end_index = context.message.content.index(text_channel_str) + len(text_channel_str)
        args = context.message.content[end_index:].strip().split("-")
        args.pop(0)
        args = [arg.lower() for arg in args]
        if "c" in args:
            # Use -c to clear the channel.
            await self.clear_music_channel(text_channel)

        await self.setup_music_channel(text_channel)
        await context.send(self.user_strings["music_channel_set"].format(channel=text_channel.mention))

    @commands.command(name="getmusicchannel", help="Gets the current channel that is set as the music channel.")
    @commands.has_permissions(administrator=True)
    async def get_music_channel_command(self, context: commands.Context):
        """
        Gets the current channel that is set as the music channel.
        If there is no channel set it will return a message saying so.
        :param context: The context of the command.
        """
        channel = await self.find_music_channel_instance(context.guild)
        if channel:
            await context.send(self.user_strings["music_channel_get"].format(channel=channel.mention))
        else:
            await context.send(self.user_strings["music_channel_missing"])

    @commands.command(name="resetmusicchannel", help="Clears the music channel and sends the preview and queue messages.")
    @commands.has_permissions(administrator=True)
    async def reset_music_channel_command(self, context: commands.Context):
        """
        Resets the music channel to clear all the text and re-send the preview and queue messages.
        :param context: The context of the command.
        """
        await self.reset_music_channel(context)

    @commands.command(
        name="fixmusic",
        help="Kicks the bot from the current Voice Channel, clears the current queue and resets the music channel."
    )
    @commands.has_permissions(administrator=True)
    async def guild_bot_reset_command(self, context: commands.Context):
        """
        Resets the music channel as well as attempts to disconnect the bot. This is to be used in-case there was an error
        and the bot was not able to reset itself.
        :param context: The context of the command.
        """
        await self.remove_active_guild(context.guild)
        await self.reset_music_channel(context)

    @commands.command(
        name="removemusicchannel",
        help="Unlinks the currently set music channel from being the music channel. Does not delete the actual channel"
    )
    @commands.has_permissions(administrator=True)
    async def unlink_music_channel_command(self, context: commands.Context):
        if not self.music_channels.get(context.guild.id):
            await context.send(self.user_strings["music_channel_missing"])
            return

        music_channel_instance = await self.find_music_channel_instance(context.guild)
        self.music_channels.pop(context.guild.id)
        db_item = self.db.get(Music_channels, guild_id=context.guild.id)
        self.db.delete(db_item)
        await context.send(self.user_strings["music_channel_removed"].format(channel=music_channel_instance.mention))

    @commands.command(
        name="musicqueue",
        aliases=["songqueue",
                 "songs",
                 "songlist",
                 "songslist"],
        help="Gets the current list of songs in the queue"
    )
    @delete_after()
    async def get_current_queue(self, context: commands.Context):
        """
        Get the current queue as a string.
        :param context: The context of the command.
        """
        if context.guild.id not in self.active_guilds:
            await send_timed_message(channel=context.channel, content=self.user_strings["bot_inactive"], timer=20)
            return

        if not self.active_guilds.get(context.guild.id).get("queue"):
            await send_timed_message(channel=context.channel, content=self.user_strings["bot_inactive"], timer=20)
            return

        queue_string = self.get_updated_queue_message(context.guild.id)
        await send_timed_message(channel=context.channel, content=queue_string, timer=60)

    @commands.group(
        name="music",
        help="These are commands used to control the music bot. For more detailed command explanations, "
        "go to https://github.com/FragSoc/esports-bot#music-bot"
    )
    @commands.check(check_music_channel)
    @delete_after()
    async def command_group(self, context: commands.Context):
        """
        This is the command group for all commands that are meant to be performed in the music channel.
        :param context: The context of the command.
        """
        pass

    @command_group.error
    async def check_failed_error(self, context: commands.Context, error: commands.CheckFailure):
        """
        Handles when the @commands.check fails so that the log is not clogged with pseudo errors.
        :param context: The context of the command that failed.
        :param error: The error that occurred.
        """
        if isinstance(error, commands.CheckFailure):
            await send_timed_message(
                channel=context.channel,
                content=self.user_strings["music_channel_wrong_channel"].format(command=context.command.name),
                timer=10
            )
            await context.message.delete()
            self.logger.debug(f"The check for command '{context.command.name}' failed")
            return

        # If the error was some other error, raise it so we know about it.
        await context.send(self.unhandled_error_string)
        raise error

    @command_group.command(
        name="join",
        aliases=["connect"],
        usage="[-f]",
        help="Make the bot join the channel. If you are an admin you can force it join your voice channel "
        "if it is currently in another channel with '-f' or 'force'."
    )
    async def join_channel_command(self, context: commands.Context, force: str = ""):
        """
        Makes the bot join the channel of the author of the command. If the bot is in another channel and the author is an
        administrator, they can force it to join the channel with -f or force.
        :param context: The context of the command.
        :param force: Whether or the author is forcing the bot to join the channel.
        """
        disable_checks = force.lower() == "-f" or force.lower() == "force"
        if disable_checks:
            if not context.author.guild_permissions.administrator:
                await send_timed_message(context.channel, content=self.user_strings["not_admin"], timer=10)
                return
            await self.remove_active_guild(context.guild)
            if not await self.join_member(context.author):
                await send_timed_message(content=self.user_strings["unable_to_join"], channel=context.channel, timer=10)
                return
        else:
            if not await self.join_member(context.author):
                await send_timed_message(content=self.user_strings["unable_to_join"], channel=context.channel, timer=10)
                return

    @command_group.command(
        name="kick",
        aliases=["leave"],
        usage="[-f]",
        help="Kicks the bot from the channel. If you are an admin you can force it leave a voice channel "
        "if it is currently in another channel with '-f' or 'force'."
    )
    async def leave_channel_command(self, context: commands.Context, force: str = ""):
        """
        Make the bot leave the voice channel of the author. If the author is not in the same voice channel as the bot and they
        are an administrator, they can force the bot to leave with -f or force.
        :param context: The context of the command.
        :param force: Whether or the author is forcing the bot to leave the channel.
        """
        disable_checks = force.lower() == "-f" or force.lower() == "force"
        if disable_checks:
            if not context.author.guild_permissions.administrator:
                await send_timed_message(context.channel, content=self.user_strings["not_admin"], timer=10)
                return
            await self.remove_active_guild(context.guild)
        else:
            if context.author in self.active_guilds.get(context.guild.id).get("voice_channel").members:
                await self.remove_active_guild(context.guild)
        await self.update_messages(context.guild.id)

    @command_group.command(
        name="skip",
        usage="[skip to position]",
        help="Skips the current song. If a number is given it will also skip to the song at the position given."
        "For example, if 'songs to skip' is 4, the next song to play would be song 4 in the queue."
    )
    async def skip_song(self, context: commands.Context, skip_count=1):
        """
        The command used to skip the currently playing song. If the user also specifies a skip count,
        it will skip n-1 songs in the queue as well.
        :param context: The context of the command.
        :param skip_count: The amount of songs to skip + 1 in the queue.
        """
        try:
            skip_count = int(skip_count) - 1
        except ValueError:
            skip_count = 0

        if context.guild.id not in self.active_guilds:
            return

        if context.author in self.active_guilds.get(context.guild.id).get("voice_channel").members:
            await self.__skip_song(context.guild.id, skip_count)

    async def __skip_song(self, guild_id, skip_count):
        """
        The function that actually performs the song skipping.
        :param guild_id: The ID of the guild to skip the songs in.
        :param skip_count: The amount of extra songs to skip.
        """
        if guild_id not in self.active_guilds:
            return

        self.active_guilds.get(guild_id).get("voice_client").stop()
        self.active_guilds.get(guild_id)["current_song"] = None
        if skip_count > len(self.active_guilds.get(guild_id).get("queue")) or skip_count < 0:
            await self.play_queue(guild_id)
        else:
            self.active_guilds.get(guild_id)["queue"] = self.active_guilds.get(guild_id)["queue"][skip_count:]
            await self.play_queue(guild_id)

    @command_group.command(
        name="volume",
        usage="<volume percentage>",
        help="Sets the volume of the bot to the percentage given."
    )
    async def set_volume(self, context: commands.Context, volume_level):
        """
        Set the volume level of the current playback of the bot. This volume level will persist until the bot disconnects from
        a voice channel.
        :param context: The context of the command.
        :param volume_level: The level to set the volume to. A value between 0 and 100 inclusive.
        """
        if context.guild.id not in self.active_guilds:
            return

        volume_level = str(volume_level)
        if not volume_level.isdigit():
            await send_timed_message(channel=context.channel, content=self.user_strings["volume_set_invalid_value"], timer=10)
            return

        if context.author in self.active_guilds.get(context.guild.id).get("voice_channel").members:
            await self.__set_volume(context.guild.id, int(volume_level))

    async def __set_volume(self, guild_id, volume_level):
        """
        The function that actually performs the volume change for a given guild.
        :param guild_id: The ID of the guild to change the volume of.
        :param volume_level: The level to set the volume to. A value between 0 and 100 inclusive.
        """
        if guild_id not in self.active_guilds:
            return

        if volume_level < 0:
            volume_level = 0

        if volume_level > 100:
            volume_level = 100

        self.active_guilds.get(guild_id).get("voice_client").source.volume = float(volume_level) / float(100)
        self.active_guilds.get(guild_id)["volume"] = float(volume_level) / float(100)
        await self.update_messages(guild_id)

    @command_group.command(name="shuffle", help="Shuffles the current queue.")
    async def shuffle_queue(self, context: commands.Context):
        """
        Shuffles the current queue in a given guild.
        :param context: The context of the command.
        """
        if context.guild.id not in self.active_guilds:
            return
        if context.author in self.active_guilds.get(context.guild.id).get("voice_channel").members:
            await self.__shuffle_queue(context.guild.id)
            await send_timed_message(channel=context.channel, content=self.user_strings["shuffle_queue_success"], timer=10)

    async def __shuffle_queue(self, guild_id):
        """
        The function that actually performs the shuffle in a given guild.
        :param guild_id: The ID of the guild to shuffle the queue of.
        """
        if guild_id not in self.active_guilds:
            return

        shuffle(self.active_guilds.get(guild_id).get("queue"))
        await self.update_messages(guild_id)

    @command_group.command(
        name="clear",
        aliases=["purge",
                 "empty"],
        help="Clears the current queue of all songs. Does not stop the currently playing song."
    )
    async def clear_queue(self, context: commands.context):
        """
        Clear the current queue in a guild.
        :param context: The context of the command.
        """
        if context.guild.id in self.active_guilds:
            if context.author not in self.active_guilds.get(context.guild.id).get("voice_channel").members:
                if not context.author.guild_permissions.administrator:
                    return

        await self.__clear_queue(context.guild.id)

    async def __clear_queue(self, guild_id):
        """
        The actual function that performs the clearing of the current queue in a given guild.
        :param guild_id: The ID of the guild to clear the queue of.
        """
        if guild_id in self.active_guilds:
            self.active_guilds.get(guild_id)["queue"] = []
        await self.update_messages(guild_id)

    @command_group.command(
        name="resume",
        usage="[song to play]",
        aliases=["play"],
        help="Resumes playback of the current song. If a song is given and there is no current song, it is played,"
        "otherwise it is added to the queue."
    )
    async def play_song(self, context: commands.Context, song_to_play=""):
        """
        Either resumes the current playback, adds a song to the queue or starts playback depending on the stats of the bot in
        the given guild context.
        :param context: The context of the guild.
        :param song_to_play: The song to play. If none specified, the playback will be resumed and no song will be added.
        """
        if context.guild.id in self.active_guilds:
            if context.author not in self.active_guilds.get(context.guild.id).get("voice_channel").members:
                return

        await self.__play_song(context.author, song_to_play)
        await send_timed_message(channel=context.channel, content=self.user_strings["song_resume_success"], timer=10)

    async def __play_song(self, member, song_to_play=""):
        """
        The function that actually performs the play_song command and handles the logic of if to play, resume or
        queue the song.
        :param member: The member requesting to play the song.
        :param song_to_play: The song to play, if any.
        """
        if member.guild.id not in self.active_guilds and song_to_play == "":
            return

        if song_to_play != "":
            if member.guild.id not in self.active_guilds:
                await self.join_member(member)
            await self.process_request(member.guild.id, song_to_play)
        else:
            if self.active_guilds.get(member.guild.id).get("voice_client").is_paused():
                self.active_guilds.get(member.guild.id).get("voice_client").resume()
            else:
                await self.play_queue(member.guild.id)

        if member.guild.id in self.inactive_guilds:
            self.inactive_guilds.pop(member.guild.id)

        if member.guild.id not in self.playing_guilds:
            self.playing_guilds.append(member.guild.id)

    @command_group.command(name="pause", help="Pauses the current song.")
    async def pause_song(self, context: commands.Context):
        """
        Pauses the current playback of the bot in a given guild.
        :param context: The context of the command.
        """
        if context.guild.id in self.active_guilds:
            if context.author not in self.active_guilds.get(context.guild.id).get("voice_channel").members:
                return

        self.__pause_song(context.guild.id)
        await send_timed_message(channel=context.channel, content=self.user_strings["song_pause_success"], timer=10)

    def __pause_song(self, guild_id):
        """
        The actual function that performs the pause in a given guild.
        :param guild_id: The ID of the guild to pause the playback of the current song in.
        """
        if guild_id not in self.active_guilds:
            return

        if self.active_guilds.get(guild_id)["voice_client"].is_playing():
            self.active_guilds.get(guild_id)["voice_client"].pause()

    @command_group.command(
        name="remove",
        aliases=["removeat"],
        usage="<song number>",
        help="Removes a song from the given number in the queue."
    )
    async def remove_song(self, context: commands.Context, song_index: str = 1):
        """
        Removes a song from the queue using it's index. The index given as a param is 1-indexed, instead of 0-indexed.
        :param context: The context of the command.
        :param song_index: The 1-indexed index of the song to remove.
        """
        if context.guild.id not in self.active_guilds:
            return

        song_index = await self.song_index_str_to_int(context, song_index)
        if song_index is None:
            return

        removed_song = await self.__remove_song(context.guild.id, song_index)
        if removed_song:
            await send_timed_message(
                channel=context.channel,
                content=self.user_strings["song_remove_success"].format(
                    song_title=removed_song.get("title"),
                    song_position=song_index
                )
            )

    async def __remove_song(self, guild_id, song_index):
        """
        The actual function that performs the removal of the song_index from the queue. The song index is 0-indexed.
        :param guild_id: The ID of the guild to remove the song in.
        :param song_index: The 0-indexed index of the song to remove.
        :return: The song removed if one was removed, else None.
        """
        if guild_id not in self.active_guilds:
            return None

        try:
            song = self.active_guilds.get(guild_id)["queue"].pop(song_index)
            await self.update_messages(guild_id)
            return song
        except IndexError:
            return None

    @command_group.command(
        name="move",
        usage="<from position> <to position>",
        help="Moves a song from one position to another."
    )
    async def move_song(self, context: commands.context, from_pos: str, to_pos: str):
        """
        Moves a song from one position in the queue to another position. The positions given as params are 1-indexed.
        :param context: The context of the command.
        :param from_pos: The 1-indexed position of the song to move.
        :param to_pos: The 1-indexed position of the index to move to.
        """
        if context.guild.id not in self.active_guilds:
            return
        else:
            if context.author not in self.active_guilds.get(context.guild.id).get("voice_channel").members:
                return

        from_pos = await self.song_index_str_to_int(context, from_pos)
        # Explicitly check for None, as index 0 is counted as False
        if from_pos is None:
            return
        to_pos = await self.song_index_str_to_int(context, to_pos)
        if to_pos is None:
            return

        song_at_pos = self.active_guilds.get(context.guild.id).get("queue")[from_pos]

        if await self.__move_song(context.guild.id, from_pos, to_pos):
            await send_timed_message(
                channel=context.channel,
                content=self.user_strings["song_moved_success"].format(
                    from_pos=from_pos + 1,
                    to_pos=to_pos + 1,
                    title=song_at_pos.get("title")
                )
            )

    async def __move_song(self, guild_id, from_pos, to_pos):
        """
        The actual function that performs song move.
        :param guild_id: The ID of the guild to move the song in.
        :param from_pos: The 0-indexed position of the song to move.
        :param to_pos: The 0-indexed position of where to move the song to.
        :return: True if the song was moved, False otherwise.
        """
        if guild_id not in self.active_guilds:
            return False

        if from_pos == to_pos:
            return True

        queue = self.active_guilds.get(guild_id).get("queue")

        if from_pos > to_pos:
            queue_top = queue[:to_pos]
            inserted_song = [queue[from_pos]]
            queue_middle = queue[to_pos:from_pos]
            queue_end = queue[from_pos + 1:]
            new_queue = queue_top + inserted_song + queue_middle + queue_end
        else:
            queue_top = queue[:from_pos]
            inserted_song = [queue[from_pos]]
            queue_middle = queue[from_pos + 1:to_pos + 1]
            queue_end = queue[to_pos + 1:]
            new_queue = queue_top + queue_middle + inserted_song + queue_end

        self.active_guilds.get(guild_id)["queue"] = new_queue
        await self.update_messages(guild_id)
        return True

    async def song_index_str_to_int(self, context, song_index):
        """
        Convert a 1-indexed song index as a string to a 0-indexed index as an int.
        :param context: The context of the command.
        :param song_index: The 1-indexed song index.
        :return: A 0-indexed song index if it is valid, else None.
        """
        song_index = str(song_index)
        try:
            song_index = int(song_index) - 1
            queue_length = len(self.active_guilds.get(context.guild.id).get("queue"))
            if song_index > queue_length or song_index < 0:
                raise ValueError
            return song_index
        except ValueError:
            if len(self.active_guilds.get(context.guild.id).get("queue")) == 0:
                return None
            help_string = self.user_strings["song_remove_valid_options"].format(
                end_index=len(self.active_guilds.get(context.guild.id).get("queue"))
            )
            helpful_error = f"{self.user_strings['song_remove_invalid_value']}:\n{help_string}"
            await send_timed_message(channel=context.channel, content=helpful_error, timer=10)
            return None

    @staticmethod
    async def clear_music_channel(channel):
        """
        A function used to purge a channel.
        :param channel: The channel to purge.
        """
        await channel.purge(limit=int(sys.maxsize))

    async def setup_music_channel(self, channel):
        """
        Setup a new channel as the music channel for a guild.
        :param channel: The channel to set as the music channel.
        """
        self.logger.info(f"Setting up {channel.name} as the music channel in {channel.guild.name}")
        default_preview = EMPTY_PREVIEW_MESSAGE.copy()

        queue_message = await channel.send(EMPTY_QUEUE_MESSAGE)
        preview_message = await channel.send(embed=default_preview)

        db_item = self.db.get(Music_channels, guild_id=channel.guild.id)
        if not db_item:
            db_item = Music_channels(
                guild_id=channel.guild.id,
                channel_id=channel.id,
                queue_message_id=queue_message.id,
                preview_message_id=preview_message.id
            )
            self.db.create(db_item)
        else:
            db_item.queue_message_id = queue_message.id
            db_item.preview_message_id = preview_message.id
            db_item.channel_id = channel.id
            self.db.update(db_item)
        self.music_channels[channel.guild.id] = channel.id

    async def reset_music_channel(self, context):
        """
        Resets the contents of the music channel.
        :param context: The context of the command.
        """
        channel = await self.find_music_channel_instance(context.guild)
        if channel:
            self.logger.info(f"Resetting music channel in {context.guild.name}")
            await self.clear_music_channel(channel)
            await self.setup_music_channel(channel)
            await context.send(self.user_strings["music_channel_reset"].format(channel=channel.mention))
        else:
            await context.send(self.user_strings["music_channel_missing"])


def setup(bot):
    bot.add_cog(MusicCog(bot))
