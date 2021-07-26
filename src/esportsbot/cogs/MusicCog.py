import functools
import logging
import sys

from discord import ClientException, Colour, Embed, TextChannel
from discord.ext import commands

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


EMPTY_QUEUE_MESSAGE = "**__Queue list:__**\n" \
                      "Join a VoiceChannel and search a song by name or YouTube url.\n"

ESPORTS_LOGO_URL = "http://fragsoc.co.uk/wpsite/wp-content/uploads/2020/08/logo1-450x450.png"

EMPTY_PREVIEW_MESSAGE = Embed(
    title="No song currently playing",
    colour=EmbedColours.music,
    footer="Use the prefix ! for commands"
)
EMPTY_PREVIEW_MESSAGE.set_image(url=ESPORTS_LOGO_URL)
EMPTY_PREVIEW_MESSAGE.set_footer(text="Definitely not made by fuxticks#1809 on discord")


class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.db = DBGatewayActions()
        self.user_strings = bot.STRINGS["music"]
        self.unhandled_error_string = bot.STRINGS["command_error_generic"]
        self.music_channels = self.load_channels()
        self.active_guilds = {}

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
                await self.on_message_handle(message)

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
            # TODO: Handle empty VCs here
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

    async def on_message_handle(self, message):
        """
        Handles when a message is sent to a music channel.
        :param message: The message sent to the music channel.
        """
        pass

    def new_active_guild(self, guild):
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
        self.logger.info(f"Updating the voice client for {guild.name}")
        if guild.id not in self.active_guilds:
            return self.new_active_guild(guild)
        else:
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
        voice_clients = self.bot.voice_clients
        for client in voice_clients:
            if client.guild.id == guild.id:
                return client
        return None

    async def remove_active_guild(self, guild):
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

    @staticmethod
    async def join_member(member):
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
        "go to https://github.com/FragSoc/esports-bot{}"
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
        text_channel_str = str(text_channel)
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

    @commands.group(name="music")
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
        usage="[-f]",
        help="Make the bot join the channel. If you are an admin you can force it join your voice channel "
        "if it is currently in another channel with '-f' or 'force'."
    )
    async def join_channel_command(self, context: commands.Context, force: str = ""):
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
        usage="[-f]",
        help="Kicks the bot from the channel. If you are an admin you can force it join your voice channel "
        "if it is currently in another channel with '-f' or 'force'."
    )
    async def leave_channel_command(self, context: commands.Context, force: str = ""):
        disable_checks = force.lower() == "-f" or force.lower() == "force"
        if disable_checks:
            if not context.author.guild_permissions.administrator:
                await send_timed_message(context.channel, content=self.user_strings["not_admin"], timer=10)
                return
            await self.remove_active_guild(context.guild)
        else:
            if context.author in self.active_guilds.get(context.guild.id).get("voice_channel").members:
                await self.remove_active_guild(context.guild)

    @staticmethod
    async def clear_music_channel(channel):
        await channel.purge(limit=int(sys.maxsize))

    async def setup_music_channel(self, channel):
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

    async def reset_music_channel(self, context):
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
