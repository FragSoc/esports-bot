import logging
import re
from enum import Enum, IntEnum

from discord import (ButtonStyle, Colour, Embed, Interaction, Member, TextChannel, TextStyle)
from discord.app_commands import (Transform, autocomplete, command, describe, guild_only, rename)
from discord.ext.commands import Bot, GroupCog
from discord.ui import Button, Modal, TextInput, View

from client import EsportsBot
from common.discord import ColourTransformer
from common.io import load_cog_toml

from youtubesearchpython import VideosSearch

COG_STRINGS = load_cog_toml(__name__)
# AUTHOR_ID = 244050529271939073  # it me :)
AUTHOR_ID = 202978567741505536  # alt account :)
MUSIC_INTERACTION_PREFIX = f"{__name__}.interaction"
EMBED_IMAGE_URL = "https://static.wixstatic.com/media/d8a4c5_b42c82e4532c4f8e9f9b2f2d9bb5a53e~mv2.png/v1/fill/w_287,h_287,al_c,q_85,usm_0.66_1.00_0.01/esportslogo.webp"
QUERY_RESULT_LIMIT = 15


class MusicButtons(Enum):
    PLAY = "play"
    PAUSE = "pause"
    ADD = "add"
    VIEW = "view"
    EDIT = "edit"
    STOP = "stop"


class MusicModalActions(Enum):
    ADD_MODAL = "modal.add"
    ADD_MODAL_SINGLE = "modal.add.single"
    ADD_MODAL_MULTI = "modal.add.multi"


class SongRequestType(IntEnum):
    STRING = 0
    YT_VIDEO = 1
    YT_PLAYLIST = 2
    YT_THUMBNAIL = 3
    INVALID = 4


def make_custom_id(action: Enum) -> str:
    return f"{MUSIC_INTERACTION_PREFIX}-{action.value}"


def make_empty_embed(color: Colour, author: str) -> Embed:
    embed = Embed(title=COG_STRINGS["music_embed_title_idle"], color=color)
    embed.set_image(url=EMBED_IMAGE_URL)
    embed.set_footer(text=f"Made by {author} 💖")
    return embed


def make_default_action_row() -> View:
    view = View(timeout=None)

    play_button = Button(style=ButtonStyle.secondary, emoji="▶️", custom_id=make_custom_id(MusicButtons.PLAY))
    pause_button = Button(style=ButtonStyle.secondary, emoji="⏸️", custom_id=make_custom_id(MusicButtons.PAUSE))
    add_button = Button(
        style=ButtonStyle.primary,
        label=COG_STRINGS["music_button_add_song"],
        emoji="➕",
        custom_id=make_custom_id(MusicButtons.ADD)
    )
    view_button = Button(
        style=ButtonStyle.primary,
        label=COG_STRINGS["music_button_view_queue"],
        emoji="📋",
        custom_id=make_custom_id(MusicButtons.VIEW)
    )
    edit_button = Button(
        style=ButtonStyle.primary,
        label=COG_STRINGS["music_button_edit_queue"],
        emoji="✏️",
        custom_id=make_custom_id(MusicButtons.EDIT)
    )
    stop_button = Button(
        style=ButtonStyle.danger,
        label=COG_STRINGS["music_button_stop_queue"],
        emoji="⏹️",
        custom_id=make_custom_id(MusicButtons.STOP)
    )

    view.add_item(play_button)
    view.add_item(pause_button)
    view.add_item(add_button)
    view.add_item(view_button)
    view.add_item(edit_button)
    view.add_item(stop_button)

    return view


def parse_request_type(request: str) -> SongRequestType:
    website_regex = r"^(https:\/\/)?(www.)?"
    if re.search(website_regex, request).group():
        return parse_url_type(request)
    else:
        return SongRequestType.STRING


def parse_url_type(request: str) -> SongRequestType:
    yt_desktop_regex = r"youtube\.com\/watch\?v="
    yt_playlist_regex = r"youtube\.com\/playlist\?list="
    yt_mobile_regex = r"youtu\.be\/"
    yt_thumbnail_regex = r"i\.ytimg\.com\/vi\/"

    if re.search(yt_desktop_regex, request):
        return SongRequestType.YT_VIDEO

    if re.search(yt_playlist_regex, request):
        return SongRequestType.YT_PLAYLIST

    if re.search(yt_mobile_regex, request):
        return SongRequestType.YT_VIDEO

    if re.search(yt_thumbnail_regex, request):
        return SongRequestType.YT_PLAYLIST

    return SongRequestType.INVALID


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


def perform_string_query(query: str) -> dict:
    results = VideosSearch(f"'{query}'", limit=QUERY_RESULT_LIMIT).resultComponents
    filtered = list(filter(lambda x: x.get("publishedTime") is None, results))
    if filtered:
        return filtered[0]

    preferred_keywords = ["official", "music"]
    alternate_keywords = ["lyric", "audio"]

    best_result = None
    best_views = 0.0

    is_preferred = False
    keyword_found = ""

    for result in results:
        video_title = result.get("title").lower()
        try:
            for keyword in (preferred_keywords + alternate_keywords):
                if keyword in video_title:
                    keyword_found = keyword
                    raise StopIteration
        except StopIteration:
            if not is_preferred or keyword_found in preferred_keywords:
                view_count = convert_viewcount_to_float(result.get("viewCount").get("short"))
                if view_count > best_views:
                    best_result = result
                    best_views = view_count

            if keyword_found in preferred_keywords:
                is_preferred = True

    return best_result


def parse_string_query_result(result: dict) -> dict:

    def get_video_title():
        views_long = result.get("viewCount").get("text")
        duration_long = result.get("accessibility").get("duration")
        title_long = result.get("accessibility").get("title")
        title = title_long.replace(views_long, "").replace(duration_long, "")
        return title

    video_title = get_video_title()
    video_url = None
    video_thumbnail = None

    video_url = result.get("link")
    if parse_url_type(video_url) != SongRequestType.YT_VIDEO:
        raise ValueError(f"Unable to find correct video URL type for {video_title}")

    thumbnails = sorted(result.get("thumbnails"), key=lambda x: x.get("width"), reverse=True)
    video_thumbnail = thumbnails[0].get("url")

    if parse_url_type(video_thumbnail) != SongRequestType.YT_THUMBNAIL:
        video_thumbnail = EMBED_IMAGE_URL

    return {"title": video_title, "url": video_url, "thumbnail": video_thumbnail}


class VCMusic(GroupCog, name=COG_STRINGS["music_group_name"]):

    def __init__(self, bot: EsportsBot):
        self.bot = bot
        self.author = "fuxticks"
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"{__name__} has been added as a Cog")

    @GroupCog.listener()
    async def on_interaction(self, interaction: Interaction):
        if not interaction.data or not interaction.data.get("custom_id"):
            return False

        if not interaction.data.get("custom_id").startswith(MUSIC_INTERACTION_PREFIX):
            return False

        action = interaction.data.get("custom_id").split("-")[-1]

        match action:
            case MusicButtons.PLAY.value:
                await interaction.response.send_message("Playing music now!", ephemeral=True)
            case MusicButtons.PAUSE.value:
                await interaction.response.send_message("Pausing music!", ephemeral=True)
            case MusicButtons.ADD.value:
                await self.add_song_request(interaction)
            case MusicButtons.VIEW.value:
                await interaction.response.send_message("View queue..", ephemeral=True)
            case MusicButtons.EDIT.value:
                await interaction.response.send_message("Edit queue..", ephemeral=True)
            case MusicButtons.STOP.value:
                await interaction.response.send_message("Stopping queue!", ephemeral=True)
            case MusicModalActions.ADD_MODAL.value:
                await self.add_song_response(interaction)
            case _:
                await interaction.response.send_message(
                    f"Recieved action: {interaction.data.get('custom_id')}",
                    ephemeral=True
                )

    @GroupCog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            for member in guild.members:
                if member.id == AUTHOR_ID:
                    self.logger.info(f"Found {member} as VCMusic author !")
                    self.author = member
                    return True
        self.logger.info(f"Unable to find VCMusic author with id {AUTHOR_ID}, defaulting to {self.author}")
        return False

    async def add_song_request(self, interaction: Interaction):
        modal = Modal(
            title=COG_STRINGS["music_add_song_modal_title"],
            timeout=None,
            custom_id=make_custom_id(MusicModalActions.ADD_MODAL)
        )
        single = TextInput(
            label="Add one song to queue",
            custom_id=make_custom_id(MusicModalActions.ADD_MODAL_SINGLE),
            required=False
        )
        multi = TextInput(
            label="Add multiple songs to queue",
            custom_id=make_custom_id(MusicModalActions.ADD_MODAL_MULTI),
            required=False,
            style=TextStyle.paragraph
        )
        modal.add_item(single)
        modal.add_item(multi)
        await interaction.response.send_modal(modal)

    async def add_song_response(self, interaction: Interaction):
        if not await self.check_valid_user(interaction.user):
            await interaction.response.send_message(COG_STRINGS["music_add_song_warn_invalid_voice"], ephemeral=True)
            return False

        interaction_data = interaction.data.get("components")

        single_id = make_custom_id(MusicModalActions.ADD_MODAL_SINGLE)
        multi_id = make_custom_id(MusicModalActions.ADD_MODAL_MULTI)

        single_request_data = [x for x in interaction_data if x.get("components")[0].get("custom_id") == single_id][0]
        multi_request_data = [x for x in interaction_data if x.get("components")[0].get("custom_id") == multi_id][0]

        single_request = single_request_data.get("components")[0].get("value")
        multi_request = multi_request_data.get("components")[0].get("value")

        request_list = [x.strip() for x in multi_request.split("\n") if x.strip() not in ('', ' ')]
        if single_request.strip() not in ('', ' '):
            request_list = [single_request.strip()] + request_list

        failed_requests = []
        for request in request_list:
            if not await self.process_song_request(request, interaction):
                failed_requests.append(request)


        await interaction.response.send_message(
            f"Succesfully added `{len(request_list) - len(failed_requests)}` song(s)!",
            ephemeral=True
        )

    async def process_song_request(self, request: str, interaction: Interaction) -> bool:

        request_type = parse_request_type(request)

        if request_type == SongRequestType.YT_VIDEO or request_type == SongRequestType.YT_PLAYLIST:
            return False
        elif request_type == SongRequestType.STRING:
            query = perform_string_query(request)
            parsed_result = parse_string_query_result(query)
        else:
            return False

        return True

    async def check_valid_user(self, user: Member):
        bot_in_channel = user.guild.me.voice is not None
        user_in_channel = user.voice is not None

        if not bot_in_channel and user_in_channel:
            return True

        if not user_in_channel:
            return False

        return user.guild.me.voice.channel == user.voice.channel

    @command(name=COG_STRINGS["music_set_channel_name"], description=COG_STRINGS["music_set_channel_description"])
    @describe(
        channel=COG_STRINGS["music_set_channel_channel_describe"],
        clear_messages=COG_STRINGS["music_set_channel_clear_messages_describe"],
        embed_color=COG_STRINGS["music_set_channel_embed_color_describe"]
    )
    @rename(
        channel=COG_STRINGS["music_set_channel_channel_rename"],
        clear_messages=COG_STRINGS["music_set_channel_clear_messages_rename"],
        embed_color=COG_STRINGS["music_set_channel_embed_color_rename"]
    )
    @autocomplete(embed_color=ColourTransformer.autocomplete)
    @guild_only()
    async def set_channel(
        self,
        interaction: Interaction,
        channel: TextChannel,
        clear_messages: bool = False,
        embed_color: Transform[Colour,
                               ColourTransformer] = Colour(0xd462fd)
    ):
        await interaction.response.defer(ephemeral=True)

        if clear_messages:
            await channel.purge()

        embed = make_empty_embed(embed_color, self.author)
        view = make_default_action_row()

        await channel.send(embed=embed, view=view)

        await interaction.followup.send(content=COG_STRINGS["music_set_channel_success"].format(channel=channel.mention))


async def setup(bot: Bot):
    await bot.add_cog(VCMusic(bot))
