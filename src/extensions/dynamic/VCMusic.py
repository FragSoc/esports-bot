import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Union
from urllib.parse import parse_qs, urlparse

import googleapiclient.discovery
from discord import (
    ButtonStyle,
    Color,
    Embed,
    FFmpegPCMAudio,
    Guild,
    Interaction,
    Member,
    PCMVolumeTransformer,
    PermissionOverwrite,
    TextChannel,
    TextStyle,
    VoiceClient,
    VoiceState
)
from discord.app_commands import (
    Range,
    Transform,
    autocomplete,
    checks,
    command,
    default_permissions,
    describe,
    guild_only,
    rename
)
from discord.ext import tasks
from discord.ext.commands import Bot, GroupCog
from discord.ui import Button, Modal, TextInput, View
from youtubesearchpython import VideosSearch
from yt_dlp import YoutubeDL

from common.discord import ColourTransformer, respond_or_followup
from common.io import load_cog_toml
from database.gateway import DBSession
from database.models import MusicChannels

COG_STRINGS = load_cog_toml(__name__)
MUSIC_INTERACTION_PREFIX = f"{__name__}.interaction"
INTERACTION_SPLIT_CHARACTER = "."
EMBED_IMAGE_URL = "https://static.wixstatic.com/media/d8a4c5_b42c82e4532c4f8e9f9b2f2d9bb5a53e~mv2.png/v1/fill/w_287,h_287,al_c,q_85,usm_0.66_1.00_0.01/esportslogo.webp"
QUERY_RESULT_LIMIT = 15
INACTIVE_TIMEOUT = 60
AUTHOR_ID = 244050529271939073  # main account
# AUTHOR_ID = 202978567741505536  # alt account
FFMPEG_PLAYER_OPTIONS = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"

GOOGLE_API_KEY = os.getenv("GOOGLE_API")
YOUTUBE_API = googleapiclient.discovery.build("youtube", "v3", developerKey=GOOGLE_API_KEY)


class UserActionType(IntEnum):
    PLAY = 0
    PAUSE = 1
    STOP = 2
    ADD_SONG = 3
    VIEW_QUEUE = 4
    EDIT_QUEUE = 5
    ADD_SONG_MODAL_SUBMIT = 6
    EDIT_QUEUE_MODAL_SUBMIT = 7
    ADD_SONG_MODAL_SINGLE = 8
    ADD_SONG_MODAL_MULTIPLE = 9
    SKIP = 10
    VOLUME = 11
    VOLUME_MODAL_SUBMIT = 12
    VOLUME_MODAL_VALUE = 13

    @property
    def id(self) -> str:
        base = f"{MUSIC_INTERACTION_PREFIX}{INTERACTION_SPLIT_CHARACTER}"
        match self:
            case UserActionType.PLAY:
                return f"{base}actionplay"
            case UserActionType.PAUSE:
                return f"{base}actionpause"
            case UserActionType.STOP:
                return f"{base}actionstop"
            case UserActionType.ADD_SONG:
                return f"{base}actionadd"
            case UserActionType.VIEW_QUEUE:
                return f"{base}actionview"
            case UserActionType.EDIT_QUEUE:
                return f"{base}actionedit"
            case UserActionType.ADD_SONG_MODAL_SUBMIT:
                return f"{base}submitadd"
            case UserActionType.EDIT_QUEUE_MODAL_SUBMIT:
                return f"{base}submitedit"
            case UserActionType.ADD_SONG_MODAL_SINGLE:
                return f"{base}addmodalsingle"
            case UserActionType.ADD_SONG_MODAL_MULTIPLE:
                return f"{base}addmodalmultiple"
            case UserActionType.SKIP:
                return f"{base}skipsong"
            case UserActionType.VOLUME:
                return f"{base}volume"
            case UserActionType.VOLUME_MODAL_SUBMIT:
                return f"{base}submitvolume"
            case UserActionType.VOLUME_MODAL_VALUE:
                return f"{base}volumemodalvalue"
            case _:
                raise ValueError("Invalid enum type given!")

    @classmethod
    def from_string(self, string: str) -> "UserActionType":
        if not string.startswith(MUSIC_INTERACTION_PREFIX):
            raise ValueError(f"Invalid string given for {__class__.__name__}")

        enum_id = string.split(INTERACTION_SPLIT_CHARACTER)[-1]

        match enum_id:
            case "actionplay":
                return UserActionType.PLAY
            case "actionpause":
                return UserActionType.PAUSE
            case "actionstop":
                return UserActionType.STOP
            case "actionadd":
                return UserActionType.ADD_SONG
            case "actionview":
                return UserActionType.VIEW_QUEUE
            case "actionedit":
                return UserActionType.EDIT_QUEUE
            case "submitadd":
                return UserActionType.ADD_SONG_MODAL_SUBMIT
            case "submitedit":
                return UserActionType.EDIT_QUEUE_MODAL_SUBMIT
            case "addmodalsingle":
                return UserActionType.ADD_SONG_MODAL_SINGLE
            case "addmodalmultiple":
                return UserActionType.ADD_SONG_MODAL_MULTIPLE
            case "skipsong":
                return UserActionType.SKIP
            case "volume":
                return UserActionType.VOLUME
            case "submitvolume":
                return UserActionType.VOLUME_MODAL_SUBMIT
            case "volumemodalvalue":
                return UserActionType.VOLUME_MODAL_VALUE
            case _:
                raise ValueError(f"Invalid string given for {__class__.__name__}")

    def __str__(self):
        return self.id


class SongRequestType(IntEnum):
    INVALID = 0
    STRING = 1
    YOUTUBE_VIDEO = 2
    YOUTUBE_PLAYLIST = 3
    YOUTUBE_THUMBNAIL = 4


@dataclass(slots=True)
class SongRequest:
    raw_request: str
    request_type: SongRequestType
    url: str = None
    title: str = None
    thumbnail: str = None
    stream_data: dict = None

    async def get_song(self) -> Union[list["SongRequest"], "SongRequest", None]:
        match self.request_type:
            case SongRequestType.STRING:
                result = string_request_query(self)
                parsed_result = parse_string_query_result(result)
                self.url = parsed_result.get("url")
                self.title = parsed_result.get("title")
                self.thumbnail = parsed_result.get("thumbnail")
                return self
            case SongRequestType.YOUTUBE_VIDEO:
                result = self.get_stream_data()
                return self
            case SongRequestType.YOUTUBE_PLAYLIST:
                if not GOOGLE_API_KEY:
                    return None
                playlist_items = get_playlist_items(self.raw_request)
                song_requests = parse_playlist_response(self.raw_request, playlist_items)
                return song_requests
            case _:
                raise ValueError("Invalid SongRequestType given!")

    def get_stream_data(self):
        if self.stream_data is not None:
            return self.stream_data

        ydl_opts = {
            "quiet": "true",
            "nowarning": "true",
            "format": "bestaudio/best",
            "outtmpl": "%(title)s-%(id)s.mp3",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        }

        with YoutubeDL(ydl_opts) as ydl:
            if self.url is None and self.request_type != SongRequestType.STRING:
                self.url = self.raw_request
            if not self.url.startswith("https://"):
                self.url = f"https://{self.url}"
            if "music." in self.url:
                self.url = self.url.replace("music.", "www.")
            if self.request_type != SongRequestType.YOUTUBE_PLAYLIST and "&list" in self.url:
                self.url = self.url.split("&list")[0]
            info = ydl.extract_info(self.url, download=False)
            self.stream_data = info

        if self.title is None:
            self.title = escape_discord_characters(self.stream_data.get("title"))

        if self.thumbnail is None:
            self.thumbnail = self.stream_data.get("thumbnail")

        return info


@dataclass(slots=True)
class GuildMusicPlayer:
    guild: Union[Guild, int]
    current_song: Union[None, SongRequest] = None
    queue: list = field(default_factory=list)
    voice_client: Union[None, VoiceClient] = None
    volume: int = 100

    def __eq__(self, other: "GuildMusicPlayer") -> bool:
        if not isinstance(other, GuildMusicPlayer):
            return False
        value1 = self.guild if isinstance(self.guild, int) else self.guild.id
        value2 = other.guild if isinstance(self.guild, int) else other.guild.id
        return value1 == value2


def parse_request_type(request: str) -> SongRequestType:
    yt_desktop_regex = r"youtube\.com\/watch\?v="
    yt_playlist_regex = r"youtube\.com\/playlist\?list="
    yt_mobile_regex = r"youtu\.be\/"
    yt_thumbnail_regex = r"i\.ytimg\.com\/vi\/"

    if re.search(yt_desktop_regex, request):
        return SongRequestType.YOUTUBE_VIDEO

    if re.search(yt_playlist_regex, request):
        return SongRequestType.YOUTUBE_PLAYLIST

    if re.search(yt_mobile_regex, request):
        return SongRequestType.YOUTUBE_VIDEO

    if re.search(yt_thumbnail_regex, request):
        return SongRequestType.YOUTUBE_THUMBNAIL

    return SongRequestType.STRING


def convert_viewcount_to_float(short_views: str) -> float:
    raw = short_views.lower().split(" views")[0]
    scale = raw[-1]
    power = 1
    match scale:
        case 'k':
            power = 3
        case 'm':
            power = 6
        case 'b':
            power = 9
        case _:
            if scale.isdigit():
                return float(raw)
            else:
                return 0

    return float(raw[:-1]) * (10**power)


def string_request_query(request: SongRequest) -> dict:
    if request.request_type == SongRequestType.STRING:
        query = f"\"{request.raw_request}\" #music"
    else:
        query = request.raw_request

    video_results = VideosSearch(query, limit=QUERY_RESULT_LIMIT).resultComponents
    if request.request_type != SongRequestType.STRING and video_results:
        return video_results[0]

    preferred_keywords = ["official", "music"]
    alternate_keywords = ["lyric", "audio"]

    for result in video_results:
        video_title = result.get("title").lower()
        for keyword in preferred_keywords:
            if keyword in video_title:
                return result

        for keyword in alternate_keywords:
            if keyword in video_title:
                return result

    return video_results[0]


def parse_string_query_result(result: dict) -> dict:

    # def get_video_title():
    #     views_long = result.get("viewCount").get("text")
    #     duration_long = result.get("accessibility").get("duration")
    #     title_long = result.get("accessibility").get("title")
    #     title = title_long.replace(views_long, "").replace(duration_long, "")
    #     return title

    video_title = escape_discord_characters(result.get("title"))
    video_url = None
    video_thumbnail = None

    video_url = result.get("link")
    if parse_request_type(video_url) != SongRequestType.YOUTUBE_VIDEO:
        raise ValueError(f"Unable to find correct video URL type for {video_title}")

    thumbnails = sorted(result.get("thumbnails"), key=lambda x: x.get("width"), reverse=True)
    video_thumbnail = thumbnails[0].get("url")

    if parse_request_type(video_thumbnail) != SongRequestType.YOUTUBE_THUMBNAIL:
        video_thumbnail = EMBED_IMAGE_URL

    return {"title": video_title, "url": video_url, "thumbnail": video_thumbnail}


def escape_discord_characters(title: str):
    characters_to_escape = ['`', '|', "_", "~"]
    escaped_title = title
    for character in characters_to_escape:
        escaped_title = escaped_title.replace(character, f"\\{character}")
    return escaped_title


def get_playlist_items(playlist_url: str) -> list[dict]:
    api = YOUTUBE_API.playlistItems()
    query = parse_qs(urlparse(playlist_url).query, keep_blank_values=True)
    if not query:
        youtube_id = playlist_url.split("/")[-1]
    else:
        youtube_id = query["list"][0]

    api_args = {"part": "snippet", "maxResults": 50, "playlistId": youtube_id}

    api_request = api.list(**api_args)

    video_responses = []
    while api_request:
        response = api_request.execute()
        video_responses += response["items"]
        api_request = api.list_next(api_request, response)

    return video_responses


def parse_playlist_response(original_request: str, playlist_items: list[dict]) -> list[SongRequest]:
    formatted_requests = []
    for item in playlist_items:
        title, url, thumbnail = parse_playlist_item(item)
        song = SongRequest(
            raw_request=original_request,
            request_type=SongRequestType.YOUTUBE_VIDEO,
            title=title,
            url=url,
            thumbnail=thumbnail
        )
        formatted_requests.append(song)
    return formatted_requests


def parse_playlist_item(item: dict):
    snippet = item.get("snippet")

    chosen_thumbnail = None
    all_thumbnails = snippet.get("thumbnails")
    if "maxres" in all_thumbnails:
        chosen_thumbnail = all_thumbnails.get("maxres").get("url")
    else:
        any_thumbnail_res = list(all_thumbnails)[0]
        chosen_thumbnail = all_thumbnails.get(any_thumbnail_res).get("url")

    url = None
    if item.get("kind") == "youtube#video":
        video_id = item.get("id")
    else:
        video_id = item.get("snippet").get("resourceId").get("videoId")
    url = "https://youtube.com/watch?v={}".format(video_id)

    title = escape_discord_characters(snippet.get("title"))

    return (title, url, chosen_thumbnail)


def create_music_embed(
    color: Color,
    author: str,
    title: str = COG_STRINGS["music_embed_title_idle"],
    description: str = None,
    image: str = EMBED_IMAGE_URL,
    url: str = None
) -> Embed:
    embed = Embed(title=title, description=description, color=color, url=url)
    embed.set_image(url=image)
    embed.set_footer(text=COG_STRINGS["music_embed_footer"].format(author=author))
    return embed


def create_music_actionbar(is_paused: bool = True) -> View:
    view = View(timeout=None)

    play_button = Button(style=ButtonStyle.secondary, emoji="▶️", custom_id=UserActionType.PLAY.id)
    pause_button = Button(style=ButtonStyle.secondary, emoji="⏸️", custom_id=UserActionType.PAUSE.id)
    playback_button = play_button if is_paused else pause_button

    skip_button = Button(
        style=ButtonStyle.secondary,
        label=COG_STRINGS["music_button_skip_song"],
        emoji="⏩",
        custom_id=UserActionType.SKIP.id
    )
    volume_button = Button(
        style=ButtonStyle.primary,
        label=COG_STRINGS["music_button_set_volume"],
        emoji="🔊",
        custom_id=UserActionType.VOLUME.id
    )
    add_button = Button(
        style=ButtonStyle.primary,
        label=COG_STRINGS["music_button_add_song"],
        emoji="➕",
        custom_id=UserActionType.ADD_SONG.id
    )
    view_button = Button(
        style=ButtonStyle.primary,
        label=COG_STRINGS["music_button_view_queue"],
        emoji="📋",
        custom_id=UserActionType.VIEW_QUEUE.id
    )
    edit_button = Button(
        style=ButtonStyle.primary,
        label=COG_STRINGS["music_button_edit_queue"],
        emoji="✏️",
        custom_id=UserActionType.EDIT_QUEUE.id
    )
    stop_button = Button(
        style=ButtonStyle.danger,
        label=COG_STRINGS["music_button_stop_queue"],
        emoji="⏹️",
        custom_id=UserActionType.STOP.id
    )

    view.add_item(playback_button)
    view.add_item(skip_button)
    view.add_item(volume_button)
    view.add_item(add_button)
    view.add_item(view_button)
    # TOOD: Implement queue editing
    # view.add_item(edit_button)
    view.add_item(stop_button)

    return view


class VCMusic(GroupCog, name=COG_STRINGS["music_group_name"]):

    def __init__(self, bot: Bot):
        self.bot = bot
        self.author = "fuxticks"
        self.active_players: dict[int, GuildMusicPlayer] = {}
        self.playing: list[int] = []
        self.inactive: dict[int, datetime] = {}
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"{__name__} has been added as a Cog")

    @GroupCog.listener()
    async def on_ready(self):
        self.update_author.start()

    @GroupCog.listener()
    async def on_voice_state_update(self, member: Member, before: VoiceState, after: VoiceState):
        guild_id = before.channel.guild.id if before.channel else after.channel.guild.id
        if member.id != self.bot.user.id:
            if guild_id not in self.active_players:
                return

            if before.channel:
                if before.channel.guild.me not in before.channel.members:
                    return
                members_left = [x for x in before.channel.members if not x.bot]
                if not members_left:
                    await self.active_players.get(guild_id).voice_client.disconnect()
                    return

        if before.channel and not after.channel:
            # Bot has disconnected from a channel, ensure that cleanup has occured
            await self.cleanup_after_disconnect(guild_id)
            return

        if before.channel and after.channel:
            if guild_id in self.active_players:
                self.active_players.get(guild_id).voice_client = after.channel.guild.voice_client
            if guild_id in self.inactive:
                self.inactive.pop(guild_id)
            return

    @GroupCog.listener()
    async def on_interaction(self, interaction: Interaction):
        if not interaction.data or not interaction.data.get("custom_id"):
            return False

        if not interaction.data.get("custom_id").startswith(MUSIC_INTERACTION_PREFIX):
            return False

        try:
            user_action = UserActionType.from_string(interaction.data.get("custom_id"))
        except ValueError:
            return False

        match user_action:
            case UserActionType.PLAY:
                return await self.resume_or_start_playback(interaction)
            case UserActionType.PAUSE:
                return await self.pause_playback(interaction)
            case UserActionType.SKIP:
                return await self.skip_song_handler(interaction)
            case UserActionType.VOLUME:
                return await self.set_volume_handler(interaction)
            case UserActionType.ADD_SONG:
                return await self.add_interaction_hanlder(interaction)
            case UserActionType.VIEW_QUEUE:
                return await self.get_current_queue(interaction)
            case UserActionType.EDIT_QUEUE:
                pass
            case UserActionType.STOP:
                return await self.stop_playback(interaction)
            case UserActionType.VOLUME_MODAL_SUBMIT:
                return await self.set_volume_submit_handler(interaction)
            case UserActionType.ADD_SONG_MODAL_SUBMIT:
                return await self.add_modal_interaction_handler(interaction)
            case UserActionType.EDIT_QUEUE_MODAL_SUBMIT:
                pass
            case _:
                return False

    def run_tasks(self):
        if self.playing and not self.check_playing.is_running():
            self.check_playing.start()

        if self.inactive and not self.check_inactive.is_running():
            self.check_inactive.start()

    async def cleanup_after_disconnect(self, guild_id):
        needs_update = False
        if guild_id in self.active_players:
            self.active_players.pop(guild_id)
            needs_update = True
        if guild_id in self.playing:
            self.playing.remove(guild_id)
            needs_update = True
        if guild_id in self.inactive:
            self.inactive.pop(guild_id)
            needs_update = True
        if needs_update:
            await self.update_embed(guild_id)

    @tasks.loop(seconds=5)
    async def check_playing(self):
        if not self.playing:
            self.check_playing.cancel()
            self.check_playing.stop()
            return

        no_longer_active = []

        for guild_id in self.playing:
            voice_client = self.active_players.get(guild_id).voice_client
            if not voice_client.is_playing() and not voice_client.is_paused():
                if not self.play_next_song(guild_id):
                    no_longer_active.append(guild_id)
                    self.end_playback(guild_id)
                await self.update_embed(guild_id)

        for guild in no_longer_active:
            self.playing.remove(guild)

    @tasks.loop(seconds=10)
    async def check_inactive(self):
        if not self.inactive:
            self.check_inactive.cancel()
            self.check_inactive.stop()
            return

        now = datetime.now()
        guilds_to_disconnect = []

        for guild_id in self.inactive:
            if (now - self.inactive.get(guild_id)).seconds > INACTIVE_TIMEOUT:
                guilds_to_disconnect.append(guild_id)

        for guild in guilds_to_disconnect:
            await self.active_players.get(guild).voice_client.disconnect()

    @tasks.loop(hours=12)
    async def update_author(self):
        new_author = await self.bot.fetch_user(AUTHOR_ID)
        if new_author:
            self.author = new_author
            self.logger.info(f"Found current discord tag of VCAuthor: {self.author}")
            return True
        self.logger.info(f"Unable to find VCMusic author with id {AUTHOR_ID}, defaulting to {self.author}")
        return False

    def check_valid_user(self, guild: Guild, user: Member) -> bool:
        if not user.voice:
            return False

        if not user.voice.channel:
            return False

        if guild.id not in self.active_players:
            return True

        return self.bot.user in user.voice.channel.members

    async def set_volume_handler(self, interaction: Interaction) -> bool:
        if not self.check_valid_user(interaction.guild, interaction.user):
            await respond_or_followup(COG_STRINGS["music_invalid_voice"], interaction, ephemeral=True)
            return False

        if interaction.guild.id not in self.active_players:
            await respond_or_followup(COG_STRINGS["music_warn_not_playing"], interaction, ephemeral=True)
            return False

        modal = Modal(
            title=COG_STRINGS["music_volume_modal_title"],
            timeout=None,
            custom_id=UserActionType.VOLUME_MODAL_SUBMIT.id
        )

        volume = TextInput(
            label=COG_STRINGS["music_volume_modal_volume"],
            custom_id=UserActionType.VOLUME_MODAL_VALUE.id,
            required=True,
        )

        modal.add_item(volume)
        await interaction.response.send_modal(modal)
        return True

    async def set_volume_submit_handler(self, interaction: Interaction) -> bool:
        if not self.check_valid_user(interaction.guild, interaction.user):
            await respond_or_followup(COG_STRINGS["music_invalid_voice"], interaction, ephemeral=True)
            return False

        if interaction.guild.id not in self.active_players:
            await respond_or_followup(COG_STRINGS["music_warn_not_playing"], interaction, ephemeral=True)
            return False

        raw_modal_data = interaction.data.get("components")

        raw_volume_value = ""

        for item in raw_modal_data:
            if item.get("components")[0].get("custom_id") == UserActionType.VOLUME_MODAL_VALUE.id:
                raw_volume_value = item.get("components")[0].get("value")
                break

        if not raw_volume_value.isdigit():
            await respond_or_followup(
                COG_STRINGS["music_volume_modal_invalid"].format(supplied=raw_volume_value),
                interaction,
                ephemeral=True
            )
            return False

        volume_value = int(raw_volume_value)
        if volume_value < 0:
            volume_value = 0
        elif volume_value > 100:
            volume_value = 100

        self.active_players.get(interaction.guild.id).voice_client.source.volume = float(volume_value) / float(100)
        self.active_players.get(interaction.guild.id).volume = volume_value
        await self.update_embed(interaction.guild.id)
        await respond_or_followup(COG_STRINGS["music_volume_set_success"].format(value=volume_value), interaction)
        return True

    async def add_interaction_hanlder(self, interaction: Interaction) -> bool:
        if not self.check_valid_user(interaction.guild, interaction.user):
            await respond_or_followup(COG_STRINGS["music_invalid_voice"], interaction, ephemeral=True)
            return False

        modal = Modal(
            title=COG_STRINGS["music_add_song_modal_title"],
            timeout=None,
            custom_id=UserActionType.ADD_SONG_MODAL_SUBMIT.id
        )

        single_request = TextInput(
            label=COG_STRINGS["music_add_song_modal_single"],
            custom_id=UserActionType.ADD_SONG_MODAL_SINGLE.id,
            required=False,
        )

        multiple_request = TextInput(
            label=COG_STRINGS["music_add_song_modal_multiple"],
            custom_id=UserActionType.ADD_SONG_MODAL_MULTIPLE.id,
            required=False,
            style=TextStyle.paragraph
        )

        modal.add_item(single_request)
        modal.add_item(multiple_request)
        await interaction.response.send_modal(modal)
        return True

    async def add_modal_interaction_handler(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)
        if not self.check_valid_user(interaction.guild, interaction.user):
            await respond_or_followup(COG_STRINGS["music_invalid_voice"], interaction, ephemeral=True)
            return False

        await respond_or_followup(COG_STRINGS["music_thinking"], interaction, ephemeral=True, delete_after=20)

        raw_modal_data = interaction.data.get("components")

        single_request = ""
        multiple_request = ""

        for item in raw_modal_data:
            if item.get("components")[0].get("custom_id") == UserActionType.ADD_SONG_MODAL_SINGLE.id:
                single_request = item.get("components")[0].get("value")
            elif item.get("components")[0].get("custom_id") == UserActionType.ADD_SONG_MODAL_MULTIPLE.id:
                multiple_request = item.get("components")[0].get("value")

        request_list = [
            SongRequest(x.strip(),
                        parse_request_type(x.strip())) for x in multiple_request.split("\n") if x.strip() not in ('',
                                                                                                                  ' ')
        ]
        if single_request.strip() not in ('', ' '):
            request_list = [SongRequest(single_request.strip(), parse_request_type(single_request.strip()))] + request_list

        first_success = 0
        if request_list:
            first_request = request_list.pop(0)
            song = await first_request.get_song()
            if song is None or song is []:
                first_request = 0
            elif await self.try_play_queue(interaction, add_to_queue=song if isinstance(song, list) else [song]):
                first_success = len(song) if isinstance(song, list) else 1

        failed_requests = []
        requests_to_queue = []
        for request in request_list:
            result = await request.get_song()
            if result is None:
                failed_requests.append(request)
            elif isinstance(result, list):
                requests_to_queue += result
            else:
                requests_to_queue.append(result)

        await respond_or_followup(
            COG_STRINGS["music_added_song_count"].format(count=len(request_list) - len(failed_requests) + first_success),
            interaction,
            ephemeral=True
        )

        await self.try_play_queue(interaction, add_to_queue=requests_to_queue)

        return True

    async def try_play_queue(self, interaction: Interaction, add_to_queue: list = []):
        if not self.check_valid_user(interaction.guild, interaction.user):
            await respond_or_followup(COG_STRINGS["music_invalid_voice"], interaction, ephemeral=True)
            return False

        if interaction.guild.id not in self.active_players:
            voice_client = await interaction.user.voice.channel.connect()
            active_player = GuildMusicPlayer(guild=interaction.guild, voice_client=voice_client)
            self.active_players[interaction.guild.id] = active_player
        elif not interaction.guild.me.voice or not interaction.guild.me.voice.channel:
            voice_client = await interaction.user.voice.channel.connect()
            self.active_players[interaction.guild.id].voice_client = voice_client

        if not interaction.guild.me.voice.deaf:
            await interaction.guild.change_voice_state(
                channel=interaction.guild.me.voice.channel,
                self_deaf=True,
                self_mute=False
            )

        self.active_players[interaction.guild.id].queue += add_to_queue

        is_playing = self.active_players[interaction.guild.id].voice_client.is_playing()
        is_paused = self.active_players[interaction.guild.id].voice_client.is_paused()
        has_current_song = self.active_players[interaction.guild.id].current_song is not None

        if is_playing or (is_paused and has_current_song):
            return True

        if self.play_next_song(interaction.guild.id):
            self.run_tasks()
            if not await self.update_embed(interaction.guild.id):
                await respond_or_followup(COG_STRINGS["music_needs_setup"], interaction, ephemeral=True, delete_after=None)
            return True
        return False

    def play_next_song(self, guild_id: int):
        try:
            next_song = self.active_players[guild_id].queue.pop(0)
        except IndexError:
            return False

        if self.active_players[guild_id].voice_client.is_playing():
            self.active_players[guild_id].voice_client.stop()

        if next_song.stream_data is None:
            stream_data = next_song.get_stream_data()
        else:
            stream_data = next_song.stream_data

        self.active_players[guild_id].current_song = next_song

        voice_source = PCMVolumeTransformer(
            FFmpegPCMAudio(stream_data.get("url"),
                           before_options=FFMPEG_PLAYER_OPTIONS,
                           options="-vn"),
            volume=float(self.active_players.get(guild_id).volume) / float(100)
        )

        self.active_players[guild_id].voice_client.play(voice_source)
        self.playing.append(guild_id)

        return True

    async def resume_or_start_playback(self, interaction: Interaction):
        if not self.check_valid_user(interaction.guild, interaction.user):
            await respond_or_followup(COG_STRINGS["music_invalid_voice"], interaction, ephemeral=True)
            return False

        if interaction.guild.id not in self.active_players:
            return await self.add_interaction_hanlder(interaction)

        if interaction.guild.id in self.inactive:
            self.inactive.pop(interaction.guild.id)
            return await self.add_interaction_hanlder(interaction)

        if self.active_players.get(interaction.guild.id).voice_client.is_playing():
            await respond_or_followup(COG_STRINGS["music_warn_already_playing"], interaction, ephemeral=True)
            return False

        if self.active_players.get(interaction.guild.id).voice_client.is_paused():
            voice_client = self.active_players.get(interaction.guild.id).voice_client
            voice_client.resume()
            if not await self.update_embed(interaction.guild.id):
                await respond_or_followup(COG_STRINGS["music_needs_setup"], interaction, ephemeral=True, delete_after=None)
            await respond_or_followup(COG_STRINGS["music_resume_success"], interaction, ephemeral=True)
            return True

        await respond_or_followup(COG_STRINGS["music_generic_error"].format(author=self.author), interaction, ephemeral=True)
        return False

    async def pause_playback(self, interaction: Interaction):
        if not self.check_valid_user(interaction.guild, interaction.user):
            await respond_or_followup(COG_STRINGS["music_invalid_voice"], interaction, ephemeral=True)
            return False

        if interaction.guild.id not in self.active_players:
            await respond_or_followup(COG_STRINGS["music_warn_not_playing"], interaction, ephemeral=True)
            return False

        voice_client = self.active_players[interaction.guild.id].voice_client
        if voice_client.is_paused():
            await respond_or_followup(COG_STRINGS["music_warn_already_paused"], interaction, ephemeral=True)
            return False

        voice_client.pause()
        if not await self.update_embed(interaction.guild.id):
            await respond_or_followup(COG_STRINGS["music_needs_setup"], interaction, ephemeral=True, delete_after=None)
        await respond_or_followup(COG_STRINGS["music_paused_success"], interaction, ephemeral=True)
        return True

    async def skip_song_handler(self, interaction: Interaction):
        if not self.check_valid_user(interaction.guild, interaction.user):
            await respond_or_followup(COG_STRINGS["music_invalid_voice"], interaction, ephemeral=True)
            return False

        if interaction.guild.id not in self.active_players:
            await respond_or_followup(COG_STRINGS["music_warn_not_playing"], interaction, ephemeral=True)
            return False

        if self.play_next_song(interaction.guild.id):
            if not await self.update_embed(interaction.guild.id):
                await respond_or_followup(COG_STRINGS["music_needs_setup"], interaction, ephemeral=True, delete_after=None)
            await respond_or_followup(COG_STRINGS["music_skip_success"], interaction, ephemeral=True)
            return True

        self.end_playback(interaction.guild.id)
        if not await self.update_embed(interaction.guild.id):
            await respond_or_followup(COG_STRINGS["music_needs_setup"], interaction, ephemeral=True, delete_after=None)
        await respond_or_followup(COG_STRINGS["music_warn_no_next_song"], interaction, ephemeral=True)
        return False

    async def get_current_queue(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)
        if interaction.guild.id not in self.active_players:
            await respond_or_followup(COG_STRINGS["music_warn_view_queue_empty"], interaction, ephemeral=True)
            return True

        current_queue = self.active_players.get(interaction.guild.id).queue
        current_song = self.active_players.get(interaction.guild.id).current_song

        current_song_text = f"__Current Song__\n{COG_STRINGS['music_embed_title_idle'] if not current_song else current_song.title}"

        QUEUE_CUTOFF = 15
        if len(current_queue) > 2 * QUEUE_CUTOFF + 5:
            first_set = current_queue[:QUEUE_CUTOFF]
            last_set = current_queue[-QUEUE_CUTOFF:]
            remaining = len(current_queue) - 2 * QUEUE_CUTOFF
            first_set_formatted = "\n".join([f"{idx+1}. {song.title}" for idx, song in enumerate(first_set)])
            last_set_formatted = "\n".join(
                [f"{idx+1+remaining+QUEUE_CUTOFF}. {song.title}" for idx,
                 song in enumerate(last_set)]
            )
            separator = f"\n\n... and **`{remaining}`** more ... \n\n"
            formatted_queue = f"{first_set_formatted}{separator}{last_set_formatted}"
        else:
            formatted_queue = "\n".join([f"{idx+1}. {song.title}" for idx, song in enumerate(current_queue)])

        current_queue_text = f"__Up Next__\n{COG_STRINGS['music_empty_queue_text'] if not current_queue else formatted_queue}"
        queue_text = f"{current_song_text}\n\n{current_queue_text}"

        await respond_or_followup(queue_text, interaction, ephemeral=True, delete_after=None)
        return True

    def end_playback(self, guild_id: int):
        if self.active_players.get(guild_id).voice_client.is_playing():
            self.active_players.get(guild_id).voice_client.stop()

        self.active_players.get(guild_id).queue = []
        self.active_players.get(guild_id).current_song = None

        self.inactive[guild_id] = datetime.now()
        self.run_tasks()

    async def update_embed(self, guild_id: int):
        db_entry = DBSession.get(MusicChannels, guild_id=guild_id)
        if not db_entry:
            return False
        embed_message = await self.bot.get_guild(guild_id).get_channel(db_entry.channel_id).fetch_message(db_entry.message_id)

        current_embed: Embed = embed_message.embeds[0]
        if self.active_players.get(guild_id) and self.active_players.get(guild_id).current_song:
            current_song = self.active_players.get(guild_id).current_song
            new_embed = create_music_embed(
                color=current_embed.color,
                author=self.author,
                title=COG_STRINGS["music_embed_title_playing"].format(song=current_song.title),
                description=COG_STRINGS["music_embed_current_volume"].format(value=self.active_players.get(guild_id).volume),
                image=current_song.thumbnail,
                url=current_song.url
            )
            voice_client = self.active_players.get(guild_id).voice_client
            is_paused = True if voice_client is None else not voice_client.is_playing()
        else:
            new_embed = create_music_embed(color=current_embed.color, author=self.author)
            is_paused = True

        await embed_message.edit(embed=new_embed, view=create_music_actionbar(is_paused))
        return True

    async def stop_playback(self, interaction: Interaction):
        if interaction.guild.id not in self.active_players:
            if interaction.guild.voice_client:
                await interaction.guild.voice_client.disconnect()
            if not await self.update_embed(interaction.guild.id):
                await respond_or_followup(COG_STRINGS["music_needs_setup"], interaction, ephemeral=True, delete_after=None)
            await respond_or_followup(COG_STRINGS["music_stopped_success"], interaction, ephemeral=True)
            return True

        if not self.check_valid_user(interaction.guild, interaction.user):
            await respond_or_followup(COG_STRINGS["music_invalid_voice"], interaction, ephemeral=True)
            return False

        self.end_playback(interaction.guild.id)
        if not await self.update_embed(interaction.guild.id):
            await respond_or_followup(COG_STRINGS["music_needs_setup"], interaction, ephemeral=True, delete_after=None)
        await respond_or_followup(COG_STRINGS["music_stopped_success"], interaction, ephemeral=True)
        return True

    @command(name=COG_STRINGS["music_set_channel_name"], description=COG_STRINGS["music_set_channel_description"])
    @describe(
        channel=COG_STRINGS["music_set_channel_channel_describe"],
        clear_messages=COG_STRINGS["music_set_channel_clear_messages_describe"],
        embed_color=COG_STRINGS["music_set_channel_embed_color_describe"],
        read_only=COG_STRINGS["music_set_channel_read_only_describe"]
    )
    @rename(
        channel=COG_STRINGS["music_set_channel_channel_rename"],
        clear_messages=COG_STRINGS["music_set_channel_clear_messages_rename"],
        embed_color=COG_STRINGS["music_set_channel_embed_color_rename"],
        read_only=COG_STRINGS["music_set_channel_read_only_rename"]
    )
    @autocomplete(embed_color=ColourTransformer.autocomplete)
    @default_permissions(administrator=True)
    @checks.has_permissions(administrator=True)
    @guild_only()
    async def set_channel(
        self,
        interaction: Interaction,
        channel: TextChannel,
        clear_messages: bool = False,
        embed_color: Transform[Color,
                               ColourTransformer] = Color(0xd462fd),
        read_only: bool = True
    ):
        await interaction.response.defer(ephemeral=True)

        if clear_messages:
            await channel.purge(before=interaction.created_at)

        embed = create_music_embed(embed_color, self.author)
        view = create_music_actionbar()

        message = await channel.send(embed=embed, view=view)

        existing = DBSession.get(MusicChannels, guild_id=interaction.guild.id)
        if existing:
            existing.channel_id = channel.id
            existing.message_id = message.id
            DBSession.update(existing)
        else:
            new_entry = MusicChannels(guild_id=interaction.guild.id, channel_id=channel.id, message_id=message.id)
            DBSession.create(new_entry)

        await interaction.followup.send(
            content=COG_STRINGS["music_set_channel_success"].format(channel=channel.mention),
            ephemeral=self.bot.only_ephemeral
        )

        if read_only:
            await channel.set_permissions(
                interaction.guild.default_role,
                overwrite=PermissionOverwrite(read_messages=True,
                                              send_messages=False,
                                              view_channel=True)
            )
            await channel.set_permissions(
                interaction.guild.me,
                overwrite=PermissionOverwrite(read_messages=True,
                                              send_messages=True,
                                              view_channel=True)
            )

    @command(name=COG_STRINGS["music_play_name"], description=COG_STRINGS["music_play_description"])
    @guild_only()
    async def play_command(self, interaction: Interaction):
        return await self.resume_or_start_playback(interaction)

    @command(name=COG_STRINGS["music_pause_name"], description=COG_STRINGS["music_pause_description"])
    @guild_only()
    async def pause_command(self, interaction: Interaction):
        return await self.pause_playback(interaction)

    @command(name=COG_STRINGS["music_skip_name"], description=COG_STRINGS["music_skip_description"])
    @guild_only()
    async def skip_command(self, interaction: Interaction):
        return await self.skip_song_handler(interaction)

    @command(name=COG_STRINGS["music_add_name"], description=COG_STRINGS["music_add_description"])
    @guild_only()
    async def add_songs_command(self, interaction: Interaction):
        return await self.add_interaction_hanlder(interaction)

    @command(name=COG_STRINGS["music_view_queue_name"], description=COG_STRINGS["music_view_queue_description"])
    @guild_only()
    async def view_queue(self, interaction: Interaction):
        return await self.get_current_queue(interaction)

    @command(name=COG_STRINGS["music_stop_name"], description=COG_STRINGS["music_stop_description"])
    @guild_only()
    async def stop_command(self, interaction: Interaction):
        return await self.stop_playback(interaction)

    @command(name=COG_STRINGS["music_volume_name"], description=COG_STRINGS["music_volume_description"])
    @describe(volume=COG_STRINGS["music_volume_volume_describe"])
    @rename(volume=COG_STRINGS["music_volume_volume_rename"])
    @guild_only()
    async def set_volume(self, interaction: Interaction, volume: Range[int, 0, 100]):
        if not self.check_valid_user(interaction.guild, interaction.user):
            await respond_or_followup(COG_STRINGS["music_invalid_voice"], interaction, ephemeral=True)
            return False

        if interaction.guild.id not in self.active_players:
            await respond_or_followup(COG_STRINGS["music_warn_not_playing"], interaction, ephemeral=True)
            return False

        self.active_players.get(interaction.guild.id).voice_client.source.volume = float(volume) / float(100)
        self.active_players.get(interaction.guild.id).volume = volume
        await self.update_embed(interaction.guild.id)
        await respond_or_followup(COG_STRINGS["music_volume_set_success"].format(value=volume), interaction)
        return True


async def setup(bot: Bot):
    await bot.add_cog(VCMusic(bot))
