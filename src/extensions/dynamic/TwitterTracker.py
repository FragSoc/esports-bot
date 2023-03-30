import logging

from discord import Interaction, TextChannel
from discord.app_commands import default_permissions, guild_only, command, describe, rename
from discord.ext.commands import Bot, GroupCog

from common.discord import respond_or_followup
from common.io import load_cog_toml

COG_STRINGS = load_cog_toml(__name__)
WEBHOOK_PREFIX = __name__


@default_permissions(administrator=True)
@guild_only()
class TwitterTracker(GroupCog, name=COG_STRINGS["twitter_group_name"]):

    def __init__(self, bot: Bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"{__name__} has been added as a Cog")
        self.webhooks = {}

    @command(name=COG_STRINGS["twitter_create_webhook_name"], description=COG_STRINGS["twitter_create_webhook_description"])
    @describe(
        name=COG_STRINGS["twitter_create_webhook_name_describe"],
        channel=COG_STRINGS["twitter_create_webhook_channel_describe"]
    )
    @rename(
        name=COG_STRINGS["twitter_create_webhook_name_rename"],
        channel=COG_STRINGS["twitter_create_webhook_channel_rename"]
    )
    async def create_webhook(self, interaction: Interaction, name: str = None, channel: TextChannel = None):
        await interaction.response.defer(ephemeral=True)

        if not channel:
            channel = interaction.channel

        if not name:
            name = f"{WEBHOOK_PREFIX}-{channel.name}"

        webhook = await channel.create_webhook(name=name)
        if not interaction.guild.id in self.webhooks:
            self.webhooks[interaction.guild.id] = {}
        self.webhooks[interaction.guild.id][webhook.id] = webhook
        await respond_or_followup(f"Created webhook: {webhook.url}", interaction, ephemeral=True, delete_after=None)


async def setup(bot: Bot):
    await bot.add_cog(TwitterTracker(bot))
