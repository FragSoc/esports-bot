import json
from typing import List, Tuple, Union, Dict

import discord
import tweepy
from discord.ext import commands
from discord import Webhook, AsyncWebhookAdapter
from discord.errors import Forbidden

from esportsbot.db_gateway import DBGatewayActions
from esportsbot.lib.stringTyping import strIsInt, strIsChannelMention
import aiohttp
import asyncio
import logging
from collections import defaultdict

import os

from esportsbot.models import Twitter_info

bot_hook_prefix = "TwitterHook-"
CONSUMER_KEY = os.getenv("TWITTER_CONSUMER_KEY")
CONSUMER_SECRET = os.getenv("TWITTER_CONSUMER_SECRET")

ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")


class TwitterWebhook(tweepy.StreamListener):
    def __init__(self, api, loop=None):
        super().__init__(api)
        self.loop = loop if loop is not None else asyncio.get_event_loop()
        self.api = api
        self.me = api.me
        self.logger = logging.getLogger(__name__)
        self.logger.info("Loaded Twitter Webhook")
        self._hooks = {}
        self._tracked_accounts = defaultdict(set)

    def on_data(self, data):
        """
        This is called whenever something matching the stream filter happens. In this case it will be when a tracked
        user Tweets, ReTweets, Quotes, or Replies.
        :param data: The new status of the tracked user.
        :type data:
        :return: None
        :rtype: NoneType
        """

        status = json.loads(data)

        if "in_reply_to_status_id" not in status:
            # Not a status update.
            return

        if not len(self.hooks) > 0:
            # There are no hooks to send the new status to.
            self.logger.error("Discord webhooks have not been loaded or ther are no webhooks!")
            return

        self.logger.info("Recieve new status for account %s...", status["user"]["screen_name"])
        self.logger.info("Pushing to webhooks...")

        if status.get("retweeted_status") is not None:
            self.logger.info("Skipping tweet, it is a retweet")
            return

        if status.get("in_reply_to_status_id") is not None:
            self.logger.info("Skipping tweet, it is a reply")
            return

        self.loop.create_task(self.send_to_webhook(status))

    def on_error(self, error: int):
        """
        Called when the API returns an error.
        Common ones are: 420 -> We are being rate limited.
                         406 -> Invalid request format. Usually because of incorrect filter values.
        :param error: The error code that was returned from the API.
        :type error: int
        :return: None
        :rtype: NoneType
        """

        self.logger.error("There was an error in the Twitter Webhook: %s", error)

    def load_discord_hooks(self, guild_hooks: List[List[Webhook]], bot_user_id: int):
        """
        Load the Webhooks used to send the Tweets to discord.
        :param bot_user_id: The discord user id of the bot that the cog is running in.
        :type bot_user_id: int
        :param guild_hooks: The list of guild Webhooks, each index being one guild.
        :type guild_hooks: List[List[Webhook]]
        :return: None
        :rtype: NoneType
        """

        for guild in guild_hooks:
            # For each guild in the list...
            for g_hook in guild:
                # And for each Webhook in the guild...
                if bot_hook_prefix in g_hook.name and g_hook.user.id == bot_user_id:
                    # Only if the Webhook was created for the TwitterCog and by the bot.
                    self.hooks[g_hook.id] = {"token": g_hook.token, "name": g_hook.name, "guild_id": g_hook.guild_id}

    def add_hook(self, hook: Webhook) -> bool:
        """
        Add a new hook to send status' to.
        :param hook: The new Webhook to add.
        :type hook: discord.Webhook
        :return: Whether the Webhook was added to the list of Webhooks.
        :rtype: bool
        """
        if hook.id in self._hooks:
            return False

        self.hooks[hook.id] = {"token": hook.token, "name": hook.name, "guild_id": hook.guild_id}
        return True

    def remove_hook(self, hook_id: str) -> bool:
        """
        Removes a hook so that status' are no longer sent to that Webhook.
        :param hook_id: The ID of the Webhook to remove.
        :type hook_id: str
        :return: Whether a Webhook with the given ID was removed from the list of Webhooks.
        :rtype: bool
        """
        if not strIsInt(hook_id):
            return False

        hook_id = int(hook_id)

        return self._hooks.pop(hook_id, None) is not None

    def set_tracked_accounts(self, accounts):
        """
        Sets the list of tracked Twitter accounts.
        :param accounts: The dictionary of accounts to track and which guilds to send their updates to.
        :type accounts: dict
        :return: None
        :rtype: NoneType
        """
        self._tracked_accounts = accounts

    def add_tracked_account(self, user_id, guild_id):
        """
        Adds a guild to send updates to for a given account.
        :param user_id: The Twitter ID of the user.
        :type user_id: str
        :param guild_id: The ID of the guild to send updates to.
        :type guild_id: int
        :return: None
        :rtype: NoneType
        """

        # This can be done as it is a defaultdict and will just create a new key with an empty set as its value if it
        # is a new account.
        self._tracked_accounts[user_id].add(guild_id)

    def remove_tracked_account(self, user_id, guild_id) -> bool:
        """
        Removes a guild from an accounts list of guilds to send updates to.
        :param user_id: The Twitter ID of the user.
        :type user_id: str
        :param guild_id: The ID of the guild to remove.
        :type guild_id: int
        :return: None
        :rtype: NoneType
        """

        tracked_guilds = self.tracked_accounts.get(user_id)

        if len(tracked_guilds) == 1 and guild_id in tracked_guilds:
            # This guild is the only guild the account is tracked in.
            self.tracked_accounts.pop(user_id)
            self.logger.info(
                "%s(guild id) was the only guild id %s(account id) was tracked in,"
                " popping from tracked accounts.",
                guild_id,
                user_id
            )
            return True
        elif guild_id in tracked_guilds:
            self.logger.info("%s(guild id) removed from %s(account id) tracked accounts.", guild_id, user_id)
            self.tracked_accounts[user_id].remove(guild_id)
            return False
        else:
            # This account is not being tracked in this guild.
            self.logger.warning("%s(account id) is not being tracked in %s(guild id)", user_id, guild_id)
            return False

    @property
    def hooks(self) -> Dict[str, dict]:
        """
        Gets the dictionary of current hooks.
        :return: A dictionary of the hooks currently being used.
        :rtype: Dict[str, dict]
        """

        return self._hooks

    @property
    def tracked_accounts(self) -> Dict[str, set]:
        """
        Gets the dictionary of the currently tracked accounts and their set of guilds to send updates to.
        :return: The dictionary of tracked accounts and their set of guilds.
        :rtype: Dict[str, set]
        """
        return self._tracked_accounts

    async def send_to_webhook(self, status: dict):
        """
        Send the new status received from one of the tracked accounts to the discord Webhooks.
        :param status: The new status received.
        :type status: dict
        :return: None
        :rtype: NoneType
        """

        screen_name = status["user"]["screen_name"]
        status_id = status["id"]
        url = f"https://twitter.com/{screen_name}/status/{status_id}"
        self.logger.info("Pushing %s to webhooks...", url)

        # Get the set of guilds to send the updates to for the account that has the new status.
        account_guilds = self._tracked_accounts.get(status.get("user").get("id_str"))

        async with aiohttp.ClientSession() as session:
            hook_adapter = AsyncWebhookAdapter(session)
            for hook_id in self._hooks:
                if self._hooks.get(hook_id).get("guild_id") not in account_guilds:
                    # Ignore hooks for guilds that don't get the updates for this account.
                    continue

                hook_token = self._hooks.get(hook_id).get("token")
                webhook = Webhook.partial(id=hook_id, token=hook_token, adapter=hook_adapter)
                self.logger.info("Sending to Webhook %s(%s)", self._hooks.get(hook_id).get("name"), hook_id)
                # TODO: Decide how to title the Webhook in discord
                await webhook.send(
                    content=url,
                    username=screen_name + " Tweeted",
                    avatar_url=status["user"]["profile_image_url_https"]
                )


class TwitterCog(commands.Cog):
    def __init__(self, bot, loop=None):
        self._bot = bot
        self.logger = logging.getLogger(__name__)
        self.loop = loop if loop is not None else asyncio.get_event_loop()
        self.user_strings = self._bot.STRINGS["twitter"]
        self._db = DBGatewayActions()

        auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
        auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
        self._api = tweepy.API(auth)
        self._api.verify_credentials()
        self._stream_listener = TwitterWebhook(self._api)
        self._filter = tweepy.Stream(self._api.auth, self._stream_listener)
        self.logger.info(f"Finished loading {__name__}... waiting for ready")

    @commands.Cog.listener()
    async def on_ready(self):
        """
        The bot needs to be ready before the discord Webhooks can be loaded as they can only be fetched once logged in.
        """
        await self.load_discord_hooks()
        guild_info = self.load_db_data()

        if len(guild_info) > 0:
            self._filter.filter(follow=list(guild_info.keys()), is_async=True)
            self._stream_listener.set_tracked_accounts(guild_info)
            self.logger.info("Currently tracking %d account(s)!", len(guild_info))
        else:
            self.logger.warning("There are no accounts that are currently tracked!")
        self.logger.info(f"{__name__} is now ready!")

    async def load_discord_hooks(self):
        """
        Loads all Webhooks from all guilds whose name starts with the bot prefix and adds them to the Stream Listener.
        """

        self.logger.info("Loading Discord Webhooks...")
        tasks = []
        for guild in self._bot.guilds:
            self.logger.info("Loading webhooks from %s(%s)", guild.name, guild.id)
            if guild.me.guild_permissions.manage_webhooks:
                tasks.append(guild.webhooks())
            else:
                self.logger.error("Missing permission 'manage webhooks' in guild %s(%s)", guild.name, guild.id)

        # Getting webhooks requires a fetch, hence the use of gather.
        results = await asyncio.gather(*tasks)

        self._stream_listener.load_discord_hooks(results, self._bot.user.id)

        self.logger.info("Got %d webhook(s) to post updates to.", len(self._stream_listener.hooks))

    def load_db_data(self) -> Dict[str, set]:
        """
        Loads the Twitter accounts and which guilds they should send updates to. Uses a defaultdict to enable easier
        additions of new accounts.
        :return: A dictionary with the Twitter accounts as the keys and a set of guild ids as the values.
        :rtype: dict
        """

        db_data = self._db.list(Twitter_info)
        guild_info = defaultdict(set)
        for item in db_data:
            guild_info[str(item.twitter_user_id)].add(item.guild_id)
        return guild_info

    @commands.group(
        name="twitter",
        help="Commands that are used to post twitter status updates to channels.",
        invoke_without_command=True
    )
    async def command_group(self, context: commands.Context):
        pass

    @command_group.command(
        name="hook",
        alias=["addtwitterhook",
               "create-hook"],
        usage="[text channel] [hook name]",
        help="Creates a new Discord Webhook in a server. If the parameter for hook name is filled, "
        "the channel parameter must also be filled."
    )
    async def twitterhook(self, ctx: commands.Context, channel=None, hook_name=None) -> bool:
        """
        Creates a Webhook in a guild. If the channel is specified the Webhook will be bound to that channel
        (can be changed in the Integrations panel for a guild's settings), otherwise will be bound to the channel where
        the message was sent. If the name is not specified a default name is used.
        :param ctx: The context of the command.
        :type ctx: discord.ext.commands.Context
        :param channel: The channel to bind the Webhook to if not None.
        :type channel: str
        :param hook_name: The name of the Webhook if not None.
        :type hook_name: str
        :return: Whether a Webhook was created with the given name and bound to the given channel.
        :rtype: bool
        """

        if hook_name is None:
            hook_name = "DefaultTwitterHook"

        if channel is not None:
            text_channel = await self.channel_from_mention(channel)
        else:
            text_channel = ctx.channel

        if text_channel is None:
            # Unable to find the channel with the given name or mention.
            await ctx.send(
                self.user_strings["webhook_error"].format(operation="create",
                                                          reason="I am unable to find that channel")
            )
            return False

        hook_name = bot_hook_prefix + hook_name
        existing, _ = self.get_webhook_by_name(hook_name, ctx.guild.id)
        if existing is not None:
            # A Webhook already exists with that name.
            self.logger.warning(
                "Attempted to create Webhook with name %s but one already exists with that name in %s(%s)",
                hook_name,
                ctx.guild.name,
                ctx.guild.id
            )
            await ctx.send(
                self.user_strings["webhook_error"].format(
                    operation="create",
                    reason=f"there is already a Webhook "
                    f"with the name {hook_name}"
                )
            )
            return False

        self.logger.info("Creating Webhook for guild %s(%s) with name %s", ctx.guild.name, ctx.guild.id, hook_name)

        hook = await text_channel.create_webhook(
            name=hook_name,
            reason=f"{ctx.author.name}#{ctx.author.discriminator} created a "
            f"webhook for #{text_channel.name} channel using the "
            f"createhook command."
        )

        self.logger.info(
            "%s#%s created Webhook for guild %s(%s) with name %s in channel %s(%s)",
            ctx.author.name,
            ctx.author.discriminator,
            ctx.guild.name,
            ctx.guild.id,
            hook_name,
            text_channel.name,
            text_channel.id
        )

        self.logger.info(
            "[%s] id: %s , url: %s , token: %s , channel: %s(%s)",
            hook.name,
            hook.id,
            hook.url,
            hook.token,
            hook.channel.name,
            hook.channel.id
        )

        # Add the hook to the Stream Listener so that it can send the updates to that Webhook.
        self._stream_listener.add_hook(hook)
        await ctx.send(self.user_strings["webhook_created"].format(name=hook.name, hook_id=hook.id))
        return True

    async def channel_from_mention(self, c_id: str) -> Union[Union[discord.TextChannel, discord.VoiceChannel], None]:
        """
        Returns the instance of a channel when the channel has been mentioned.
        :param c_id: The mentioned channel.
        :type c_id: str
        :return: An instance of a channel if there is a channel with that ID, None otherwise.
        :rtype: Union[Union[discord.TextChannel, discord.VoiceChannel], None]
        """

        if not strIsChannelMention(c_id):
            # The string was not a mentioned channel.
            return None

        # Gets just the ID of the channel.
        cleaned_id = c_id[2:-1]
        channel = self._bot.get_channel(cleaned_id)
        if channel is None:
            try:
                channel = await self._bot.fetch_channel(cleaned_id)
            except Forbidden as e:
                self.logger.error("Unable to access channel with id %s due to permission errors: %s", cleaned_id, e.text)
                return None
        return channel

    def get_webhook_by_name(self, name: str, guild_id: int) -> Union[Tuple[str, dict], Tuple[None, None]]:
        """
        Gets the Webhook ID and other details needed to use the Webhook using the name of a Webhook and a guild.
        :param name: The name of the Webhook to find. Can include the prefix or not.
        :type name: str
        :param guild_id: The id of the guild to find the Webhook in.
        :type guild_id: int
        :return: A tuple containing the Webhook ID and a dictionary containing the token and some other information.
                Returns a Tuple of None, None if there is no Webhook with that name.
        :rtype: Union[Tuple[int, dict], Tuple[None, None]]
        """

        current_hooks = self._stream_listener.hooks
        for hook in current_hooks:
            if current_hooks.get(hook).get("name") == name or current_hooks.get(hook).get("name") == (bot_hook_prefix + name):
                # Check for the name as well as the name combined with the prefix.
                if current_hooks.get(hook).get("guild_id") == guild_id:
                    return hook, current_hooks.get(hook)

        return None, None

    @command_group.command(
        name="remove-hook",
        alias=["deltwitterhook",
               "delete-hook"],
        usage="<hook name>",
        help="Deletes a Discord Webhook with the name given."
    )
    async def removetwitterhook(self, ctx: discord.ext.commands.Context, name: str) -> bool:
        """
        Deletes a discord Webhook from the calling guild using the name of the Webhook.
        :param ctx: The context of the command being called.
        :type ctx: discord.ext.commands.Context
        :param name: The name of the Webhook to delete. Can include the prefix or not.
        :type name: str
        :return: Whether a Webhook with the given name was deleted from the calling guild.
        :rtype: bool
        """

        self.logger.info("Deleting Webhook with name: %s", name)
        h_id, hook_info = self.get_webhook_by_name(name, ctx.guild.id)
        if hook_info is None:
            # Unable to find a Webhook with the given name in the guild.
            await ctx.send(
                self.user_strings["webhook_error"].format(
                    operation="remove",
                    reason=f"there is no webhook with name {name} "
                    f"or {bot_hook_prefix + name}"
                )
            )
            return False

        async with aiohttp.ClientSession() as session:
            webhook = Webhook.partial(id=h_id, token=hook_info.get("token"), adapter=AsyncWebhookAdapter(session))
            await webhook.delete(reason="Deleted with removehook comand")
            self._stream_listener.remove_hook(h_id)
        await ctx.send(self.user_strings["webhook_deleted"].format(name=hook_info.get("name"), hook_id=h_id))
        return True

    @command_group.command(
        name="add",
        usage="<account handle>",
        help="Starts tracking a given twitter account in this server."
    )
    async def addtwitter(self, ctx: discord.ext.commands.Context, account: str) -> bool:
        """
        Adds a new account to be tracked in the guild from which the command was called.
        :param ctx: The context of the command being called.
        :type ctx: discord.ext.commands.Context
        :param account: The Twitter handle of the account to track, no @ required.
        :type account: str
        :return: Whether the account was added to the list of tracked accounts.
        :rtype: bool
        """

        try:
            user = self._api.get_user(account)
            # The list of accounts that are currently being tracked across any guild.
            if self._filter.body is None:
                current_following = []
            else:
                current_following = self._filter.body.get("follow").decode("utf-8").split(",")
            user_id = user.id_str
            tracked_guilds = self._stream_listener.tracked_accounts.get(user_id)

            if tracked_guilds is not None and ctx.guild.id in tracked_guilds:
                # The account is already tracked in the current guild.
                self.logger.info(
                    "Not adding %s to %s(%s) as it is aleady tracked in the guild",
                    account,
                    ctx.guild.name,
                    ctx.guild.id
                )
                await ctx.send(self.user_strings["account_exists_error"].format(account=account))
                return False

            if user_id not in current_following:
                # The account is not currently tracked in any guild.
                self.logger.info("%s is a fresh account, adding to Twitter Webhook filter", account)
                current_following.append(user_id)
                self._stream_listener.add_tracked_account(user_id, ctx.guild.id)
                asyncio.create_task(self.refresh_filter(current_following))

            if tracked_guilds is None or ctx.guild.id not in tracked_guilds:
                db_item = Twitter_info(guild_id=ctx.guild.id, twitter_user_id=user_id, twitter_handle=account)
                self._db.create(db_item)

            self.logger.info("Added %s to accounts tracked", account)
            await ctx.send(self.user_strings["account_added"].format(account=account))
            return True
        except tweepy.TweepError as e:
            self.logger.warning("Unable to add %s as a tracked account due to the following error: %s", account, e)
            await ctx.send(self.user_strings["account_missing_error"].format(account=account, operation="add"))
            return False

    @command_group.command(
        name="remove",
        usage="<account handle>",
        help="Stops tracking a given twitter account in this server."
    )
    async def removetwitter(self, ctx: discord.ext.commands.Context, account: str) -> bool:
        """
        Removes an account from the guild from which the command was called.
        :param ctx: The context of the command being called.
        :type ctx: discord.ext.commands.Context
        :param account: The Twitter handle of the account to remove, no @ required.
        :type account: str
        :return: Whether the account was removed from the list of tracked accounts.
        :rtype: bool
        """

        if self._filter.body is None:
            # There are no current accounts being tracked.
            self.logger.warning("Current filter is empty! Can't remove any tracked accounts.")
            await ctx.send(self.user_strings["account_missing_error"].format(operation="remove", account=account))
            return False

        try:
            user = self._api.get_user(account)
            user_id = user.id_str
            tracked_accounts = self._stream_listener.tracked_accounts.get(user_id)
            current_filter = self._filter.body.get("follow").decode("utf-8").split(",")

            if tracked_accounts is None or ctx.guild.id not in tracked_accounts:
                # Not tracked in this guild.
                self.logger.info(
                    "Cannot remove %s from being tracked as it is not tracked in %s(%s)",
                    account,
                    ctx.guild.name,
                    ctx.guild.id
                )
                await ctx.send(self.user_strings["account_missing_error"].format(operation="remove", account=account))
                return False

            if self._stream_listener.remove_tracked_account(user_id, ctx.guild.id):
                # The account is no longer tracked in any guild, can be removed from the filter.
                current_filter.remove(user_id)
                asyncio.create_task(self.refresh_filter(current_filter))
            db_item = self._db.get(Twitter_info, guild_id=ctx.guild.id, twitter_user_id=user_id)
            self._db.delete(db_item)
            self.logger.info("Removed %s from being tracked in %s(%s)", account, ctx.guild.name, ctx.guild.id)
            await ctx.send(self.user_strings["account_removed"].format(account=account))

        except tweepy.TweepError as e:
            self.logger.warning("Unable to remove %s account due to the following error: %s", account, e)
            await ctx.send(self.user_strings["account_missing_error".format(account=account, operation="remove")])
            return False

    @command_group.command(
        name="list",
        alias=["accounts",
               "get-all"],
        help="Gets a list of the currently tracked accounts in this server."
    )
    async def gettwitters(self, ctx: discord.ext.commands.Context):
        """
        Gets the list of Twitter handles that are currently tracked in the guild that called the command.
        :param ctx: The context of the command being called.
        :type ctx: discord.ext.commands.Context
        :return: None
        :rtype: NoneType
        """
        handles = self._db.list(Twitter_info, guild_id=ctx.guild.id)
        if not handles:
            await ctx.send(self.user_strings["accounts_empty"])
            return

        handle_names = [x.twitter_handle for x in handles]
        handle_string = ",".join(handle_names)
        await ctx.send(self.user_strings["accounts_list"].format(tracked_accounts=handle_string))

    async def refresh_filter(self, new_filter: List[str]):
        """
        Sets the Twitter stream filter to the new_filter param.
        :param new_filter: The list of user ids to track on Twitter.
        :type new_filter: List[str]
        """

        self.logger.info("Refreshing filter with new values: %s", new_filter)
        # Tweepy is extremely fucky, and disconnect() doesn't do anything but set the running Flag to False.
        if self._filter.running:
            self._filter.disconnect()
        # Hence manually calling del, as the old filter is still running and causes messages to be duplicated.
        del self._filter
        if len(new_filter) == 0:
            self.logger.info("New filter is empty, stopping stream")
            return
        # Without the delay we get rate limited momentarily by Twitter.
        await asyncio.sleep(5)
        self._filter = tweepy.Stream(self._api.auth, self._stream_listener, daemon=True)
        self.logger.info("Disconnected current stream... Current Status: %s", "Running" if self._filter.running else "Stopped")
        self._filter.filter(follow=new_filter, is_async=True)
        self.logger.info("Reconnected filter with new parameters")
        self.logger.info("Current Stream Status: %s", "Running" if self._filter.running else "Stopped")


def setup(bot):
    if CONSUMER_KEY is None or CONSUMER_SECRET is None or ACCESS_TOKEN is None or ACCESS_TOKEN_SECRET is None:
        raise ValueError("Twitter Env Vars are not set!")
    bot.add_cog(TwitterCog(bot))
