import logging

from discord import ButtonStyle, Colour, Embed, Interaction, TextChannel
from discord.app_commands import (Transform, autocomplete, command, describe, guild_only, rename)
from discord.ext.commands import Bot, GroupCog
from discord.ui import Button, View

from client import EsportsBot
from common.discord import ColourTransformer
from common.io import load_cog_toml

from enum import Enum

COG_STRINGS = load_cog_toml(__name__)
# AUTHOR_ID = 244050529271939073  # it me :)
AUTHOR_ID = 202978567741505536  # alt account :)
MUSIC_INTERACTION_PREFIX = f"{__name__}.interaction"
EMBED_IMAGE_URL = "https://static.wixstatic.com/media/d8a4c5_b42c82e4532c4f8e9f9b2f2d9bb5a53e~mv2.png/v1/fill/w_287,h_287,al_c,q_85,usm_0.66_1.00_0.01/esportslogo.webp"


class MusicButtons(Enum):
    PLAY = "play"
    PAUSE = "pause"
    ADD = "add"
    VIEW = "view"
    EDIT = "edit"
    STOP = "stop"


def make_custom_id(action: Enum):
    return f"{MUSIC_INTERACTION_PREFIX}-{action.value}"


def make_empty_embed(color: Colour, author: str):
    embed = Embed(title=COG_STRINGS["music_embed_title_idle"], color=color)
    embed.set_image(url=EMBED_IMAGE_URL)
    embed.set_footer(text=f"Made by {author} 💖")
    return embed


def make_default_action_row():
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

        action = interaction.data.get("custom_id")

        await interaction.response.send_message(f"Recieved action: {action}", ephemeral=True)

    @GroupCog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            for member in guild.members:
                if member.id == AUTHOR_ID:
                    self.logger.info(f"Found {member} as VCMusic author !")
                    self.author = f"{member}"
                    return True
        self.logger.info(f"Unable to find VCMusic author with id {AUTHOR_ID}, defaulting to {self.author}")
        return False

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
