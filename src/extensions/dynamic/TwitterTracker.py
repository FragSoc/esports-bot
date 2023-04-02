import logging
import os

from discord import Interaction, TextChannel
from discord.app_commands import (autocomplete, command, default_permissions, describe, guild_only, rename)
from discord.ext.commands import Bot, GroupCog
from tweepy import API, OAuthHandler, Stream, StreamListener

from common.discord import TwitterWebhookIDTransformer, respond_or_followup
from common.io import load_cog_toml
from database.gateway import DBSession
from database.models import TwitterTrackerAccounts

COG_STRINGS = load_cog_toml(__name__)
WEBHOOK_PREFIX = __name__

CONSUMER_KEY = os.getenv("TWITTER_CONSUMER_KEY")
CONSUMER_SECRET = os.getenv("TWITTER_CONSUMER_SECRET")
ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")


def entry_primary_key(twitter_id: int, webhook_id: int) -> int:
    return int(f"{twitter_id % 1000}{webhook_id % 1000}")


class CustomStreamListener(StreamListener):

    def __init__(self, twitter_api: API):
        super().__init__(twitter_api)


@default_permissions(administrator=True)
@guild_only()
class TwitterTracker(GroupCog, name=COG_STRINGS["twitter_group_name"]):

    def __init__(self, bot: Bot):
        self.bot = bot
        self.webhooks = {}
        self.accounts = {}

        twitter_auth = OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
        twitter_auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
        self.twitter_api = API(twitter_auth)
        self.twitter_api.verify_credentials()
        self.stream_listener = CustomStreamListener(self.twitter_api)
        self.account_filter = Stream(self.twitter_api.auth, self.stream_listener)

        self.logger = logging.getLogger(__name__)
        self.logger.info(f"{__name__} has been added as a Cog")

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
            account_count += self.add_account(entry)

        self.logger.info(f"Found {webhook_count} webhook(s) across {len(self.webhooks)} guild(s)")
        self.logger.info(f"Found {account_count} account(s) across {len(self.webhooks)} guild(s)")

    def add_account(self, db_entry: TwitterTrackerAccounts):
        ret_val = 0
        if db_entry.guild_id not in self.accounts:
            self.accounts[db_entry.guild_id] = {}

        if db_entry.twitter_id not in self.accounts.get(db_entry.guild_id):
            self.accounts[db_entry.guild_id][db_entry.twitter_id] = []
            ret_val = 1

        self.accounts[db_entry.guild_id][db_entry.twitter_id].append(db_entry)
        return ret_val

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

    @command(name=COG_STRINGS["twitter_track_account_name"], description=COG_STRINGS["twitter_track_account_description"])
    @describe(
        twitter_id=COG_STRINGS["twitter_track_account_twitter_id_describe"],
        webhook_id=COG_STRINGS["twitter_track_account_webhook_id_describe"]
    )
    @rename(
        twitter_id=COG_STRINGS["twitter_track_account_twitter_id_rename"],
        webhook_id=COG_STRINGS["twitter_track_account_webhook_id_rename"]
    )
    @autocomplete(webhook_id=TwitterWebhookIDTransformer.autocomplete)
    async def track_account(self, interaction: Interaction, twitter_id: str, webhook_id: str):
        await interaction.response.defer(ephemeral=True)

        if not twitter_id.isdigit():
            await respond_or_followup("The given twitter ID is not valid!", interaction, ephemeral=True)
            return

        if not webhook_id.isdigit():
            await respond_or_followup("The given webhook ID is not valid!", interaction, ephemeral=True)
            return

        current_webhooks = self.accounts.get(interaction.guild.id, {}).get(int(twitter_id), [])
        exists = [x for x in current_webhooks if int(webhook_id) == x.webhook_id]
        if exists:
            await respond_or_followup("The account given is already tracked with that webhhook!", interaction, ephemeral=True)
            return

        db_item = TwitterTrackerAccounts(
            primary_key=entry_primary_key(int(twitter_id),
                                          int(webhook_id)),
            guild_id=interaction.guild.id,
            twitter_id=int(twitter_id),
            webhook_id=int(webhook_id),
            twitter_name="TwitterHandle"
        )
        DBSession.create(db_item)
        self.add_account(db_item)
        await respond_or_followup(f"Now trackiing {twitter_id} in {webhook_id}", interaction, ephemeral=True)

    @command(name=COG_STRINGS["twitter_untrack_account_name"], description=COG_STRINGS["twitter_untrack_account_description"])
    @describe(
        twitter_id=COG_STRINGS["twitter_untrack_account_twitter_id_describe"],
        webhook_id=COG_STRINGS["twitter_untrack_account_webhook_id_describe"],
        all_webhooks=COG_STRINGS["twitter_untrack_account_all_webhooks_describe"]
    )
    @rename(
        twitter_id=COG_STRINGS["twitter_untrack_account_twitter_id_rename"],
        webhook_id=COG_STRINGS["twitter_untrack_account_webhook_id_rename"],
        all_webhooks=COG_STRINGS["twitter_untrack_account_all_webhooks_rename"]
    )
    @autocomplete(webhook_id=TwitterWebhookIDTransformer.autocomplete)
    async def untrack_account(
        self,
        interaction: Interaction,
        twitter_id: str,
        all_webhooks: bool = False,
        webhook_id: str = None
    ):
        if not all_webhooks and not webhook_id:
            await respond_or_followup(
                "You must confirm to untrack from all webhooks or provide a webhook to untrack from",
                interaction,
                ephemeral=True
            )

        if not twitter_id.isdigit():
            await respond_or_followup("The given twitter ID is not valid!", interaction, ephemeral=True)
            return

        if all_webhooks:
            entries = self.accounts.get(interaction.guild.id, {}).pop(int(twitter_id), [])
            for entry in entries:
                DBSession.delete(entry)
            await respond_or_followup(f"No longer trakcing {twitter_id} in any webhook!", interaction, ephemeral=True)
            return

        if not webhook_id.isdigit():
            await respond_or_followup("The given webhook ID is not valid!", interaction, ephemeral=True)
            return

        entries = self.accounts.get(interaction.guild.id, {}).get(int(twitter_id), [])
        found = -1
        db_item = None
        for idx, item in enumerate(entries):
            if item.webhook_id == int(webhook_id):
                found = idx
                db_item = item
                break

        if found >= 0:
            self.accounts.get(interaction.guild.id).get(int(twitter_id)).pop(found)

        if db_item:
            DBSession.delete(db_item)

        await respond_or_followup(f"No longer tracking {twitter_id} in {webhook_id}", interaction, ephemeral=True)


async def setup(bot: Bot):
    await bot.add_cog(TwitterTracker(bot))
