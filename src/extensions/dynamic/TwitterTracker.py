import logging

from discord import Interaction, TextChannel
from discord.app_commands import (autocomplete, command, default_permissions, describe, guild_only, rename)
from discord.ext.commands import Bot, GroupCog

from common.discord import TwitterWebhookIDTransformer, respond_or_followup
from common.io import load_cog_toml
from database.gateway import DBSession
from database.models import TwitterTrackerAccounts

COG_STRINGS = load_cog_toml(__name__)
WEBHOOK_PREFIX = __name__


def entry_primary_key(twitter_id: int, webhook_id: int) -> int:
    return int(f"{twitter_id % 1000}{webhook_id % 1000}")


@default_permissions(administrator=True)
@guild_only()
class TwitterTracker(GroupCog, name=COG_STRINGS["twitter_group_name"]):

    def __init__(self, bot: Bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"{__name__} has been added as a Cog")
        self.webhooks = {}
        self.accounts = {}

    @GroupCog.listener()
    async def on_ready(self):
        webhook_count = 0
        for guild in self.bot.guilds:
            guild_webhooks = await guild.webhooks()
            self.webhooks[guild.id] = {}
            for webhook in guild_webhooks:
                if webhook.name.startswith(WEBHOOK_PREFIX):
                    self.webhooks[guild.id][webhook.id] = webhook
                    webhook_count += 1

        all_accounts = DBSession.list(TwitterTrackerAccounts)
        account_count = 0
        for entry in all_accounts:
            if entry.guild_id not in self.accounts:
                self.accounts[entry.guild_id] = {}

            if entry.twitter_id not in self.accounts.get(entry.guild_id):
                self.accounts[entry.guild_id][entry.twitter_id] = []
                account_count += 1

            self.accounts[entry.guild_id][entry.twitter_id].append(entry)

        self.logger.info(f"Found {webhook_count} webhook(s) across {len(self.webhooks)} guild(s)")
        self.logger.info(f"Found {account_count} account(s) across {len(self.webhooks)} guild(s)")

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
            name = channel.name

        name = f"{WEBHOOK_PREFIX}-{name}"
        webhook = await channel.create_webhook(name=name)
        if not interaction.guild.id in self.webhooks:
            self.webhooks[interaction.guild.id] = {}
        self.webhooks[interaction.guild.id][webhook.id] = webhook
        await respond_or_followup(f"Created webhook: {webhook.url}", interaction, ephemeral=True, delete_after=None)

    @command(name=COG_STRINGS["twitter_delete_webhook_name"], description=COG_STRINGS["twitter_delete_webhook_description"])
    @describe(webhook_id=COG_STRINGS["twitter_delete_webhook_webhook_id_describe"])
    @rename(webhook_id=COG_STRINGS["twitter_delete_webhook_webhook_id_rename"])
    @autocomplete(webhook_id=TwitterWebhookIDTransformer.autocomplete)
    async def delete_webhook(self, interaction: Interaction, webhook_id: str):
        await interaction.response.defer(ephemeral=True)

        if not webhook_id.isdigit():
            await respond_or_followup("Invalid webhook ID provided!", interaction, ephemeral=True)
            return

        webbhook_id_int = int(webhook_id)
        guild_webhooks = self.webhooks.get(interaction.guild.id)
        webhook = guild_webhooks.pop(webbhook_id_int, None)
        if not webhook:
            await respond_or_followup("The provided webhook ID is not a TwitterTracker webhook!", interaction, ephemeral=True)
            return

        if not webhook.name.startswith(WEBHOOK_PREFIX):
            await respond_or_followup(
                "The provided webhook ID is not for a TwitterTracker webhook!",
                interaction,
                ephemeral=True
            )
            return

        await webhook.delete()
        await respond_or_followup("Succesfully deleted webhook!", interaction, ephemeral=True)


async def setup(bot: Bot):
    await bot.add_cog(TwitterTracker(bot))
