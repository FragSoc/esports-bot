import re
from dataclasses import dataclass
from enum import IntEnum
from typing import Union

from youtubesearchpython import VideosSearch

MUSIC_INTERACTION_PREFIX = f"{__name__}.interaction"
INTERACTION_SPLIT_CHARACTER = "."
EMBED_IMAGE_URL = "https://static.wixstatic.com/media/d8a4c5_b42c82e4532c4f8e9f9b2f2d9bb5a53e~mv2.png/v1/fill/w_287,h_287,al_c,q_85,usm_0.66_1.00_0.01/esportslogo.webp"
QUERY_RESULT_LIMIT = 15


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

    @property
    def id(self) -> str:
        match self:
            case UserActionType.PLAY:
                return f"{MUSIC_INTERACTION_PREFIX}{INTERACTION_SPLIT_CHARACTER}actionplay"
            case UserActionType.PAUSE:
                return f"{MUSIC_INTERACTION_PREFIX}{INTERACTION_SPLIT_CHARACTER}actionpause"
            case UserActionType.STOP:
                return f"{MUSIC_INTERACTION_PREFIX}{INTERACTION_SPLIT_CHARACTER}actionstop"
            case UserActionType.ADD_SONG:
                return f"{MUSIC_INTERACTION_PREFIX}{INTERACTION_SPLIT_CHARACTER}actionadd"
            case UserActionType.VIEW_QUEUE:
                return f"{MUSIC_INTERACTION_PREFIX}{INTERACTION_SPLIT_CHARACTER}actionview"
            case UserActionType.EDIT_QUEUE:
                return f"{MUSIC_INTERACTION_PREFIX}{INTERACTION_SPLIT_CHARACTER}actionedit"
            case UserActionType.ADD_SONG_MODAL_SUBMIT:
                return f"{MUSIC_INTERACTION_PREFIX}{INTERACTION_SPLIT_CHARACTER}submitadd"
            case UserActionType.EDIT_QUEUE_MODAL_SUBMIT:
                return f"{MUSIC_INTERACTION_PREFIX}{INTERACTION_SPLIT_CHARACTER}submitedit"
            case UserActionType.ADD_SONG_MODAL_SINGLE:
                return f"{MUSIC_INTERACTION_PREFIX}{INTERACTION_SPLIT_CHARACTER}addmodalsingle"
            case UserActionType.ADD_SONG_MODAL_MULTIPLE:
                return f"{MUSIC_INTERACTION_PREFIX}{INTERACTION_SPLIT_CHARACTER}addmodalmultiple"
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
            case SongRequestType.YOUTUBE_VIDEO:
                result = string_request_query(self)
            case SongRequestType.YOUTUBE_PLAYLIST:
                return None
            case _:
                raise ValueError("Invalid SongRequestType given!")

        if result == None or result == {}:
            return self

        parsed_result = parse_string_query_result(result)
        self.url = parsed_result.get("url")
        self.title = parsed_result.get("title")
        self.thumbnail = parsed_result.get("thumbnail")
        return self


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
        return SongRequestType.YOUTUBE_VIDEO

    if re.search(yt_playlist_regex, request):
        return SongRequestType.YOUTUBE_PLAYLIST

    if re.search(yt_mobile_regex, request):
        return SongRequestType.YOUTUBE_VIDEO

    if re.search(yt_thumbnail_regex, request):
        return SongRequestType.YOUTUBE_THUMBNAIL

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


def string_request_query(request: SongRequest) -> dict:
    if request.request_type == SongRequestType.STRING:
        query = f"'{request.raw_request}'"
    else:
        query = request.raw_request

    video_results = VideosSearch(query, limit=QUERY_RESULT_LIMIT).resultComponents
    if request.request_type != SongRequestType.STRING and video_results:
        return video_results[0]

    filtered_results = list(filter(lambda x: x.get("publishedTime") is None, video_results))
    if filtered_results:
        return filtered_results[0]

    preferred_keywords = ["official", "music"]
    alternate_keywords = ["lyric", "audio"]

    best_result = None
    best_views = 0.0

    is_preferred = False
    keyword_found = ""

    for result in video_results:
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
    if parse_url_type(video_url) != SongRequestType.YOUTUBE_VIDEO:
        raise ValueError(f"Unable to find correct video URL type for {video_title}")

    thumbnails = sorted(result.get("thumbnails"), key=lambda x: x.get("width"), reverse=True)
    video_thumbnail = thumbnails[0].get("url")

    if parse_url_type(video_thumbnail) != SongRequestType.YOUTUBE_THUMBNAIL:
        video_thumbnail = EMBED_IMAGE_URL

    return {"title": video_title, "url": video_url, "thumbnail": video_thumbnail}
