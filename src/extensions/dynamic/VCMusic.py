from enum import IntEnum

MUSIC_INTERACTION_PREFIX = f"{__name__}.interaction"
INTERACTION_SPLIT_CHARACTER = "."


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
