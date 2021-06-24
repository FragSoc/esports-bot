"""
The TwitchCog module implements a HTTP Server to listen for requests, as well as a Discord Cog to allow for changing of where
Twitch notifications get sent and which accounts notifications are sent for.

.. codeauthor::Fluxticks
"""

import asyncio
import json
from collections import defaultdict
from datetime import datetime
import hashlib
import hmac
import os
from typing import Any

import aiohttp
from discord import Webhook, Embed, AsyncWebhookAdapter, Forbidden
from tornado.httpserver import HTTPServer
import tornado.web

import ast

from discord.ext import commands
from tornado import httputil
from tornado.web import Application

import logging

from src.esportsbot.db_gateway import db_gateway
from src.esportsbot.lib.stringTyping import strIsChannelMention

SUBSCRIPTION_SECRET = os.getenv("TWITCH_SUB_SECRET")
CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
WEBHOOK_PREFIX = "TwitchHook-"
BEARER_PADDING = 2 * 60  # Number of minutes before expiration of bearer where the same bearer will still be used.
DATETIME_FMT = "%d/%m/%Y %H:%M:%S"
TWITCH_EMBED_COLOUR = 0x6441a4
TWITCH_ICON = "https://pbs.twimg.com/profile_images/1189705970164875264/oXl0Jhyd_400x400.jpg"
CALLBACK_URL = os.getenv("TWITCH_CALLBACK") + "/webhook"  # The URL to be used as for the event callback.
DEFAULT_HOOK_NAME = "DefaultTwitchHook"


class TwitchApp(Application):
    """
    This TwitchApp is the application which the TwitchListener is serving and handling requests for.
    Mainly used to store data that is used across requests, as well as handling any API requests that need to be made.
    """

    def __init__(self, handlers=None, default_host=None, transforms=None, **settings: Any):
        super().__init__(handlers, default_host, transforms, **settings)
        self.seen_ids = set()
        self.hooks = {}
        self.bearer = None
        self.tracked_channels = defaultdict(set)
        self.subscriptions = []
        self.logger = logging.getLogger(__name__)

    # TODO: Probably best to move this to lib or some other as it is shared by TwitterCog
    def load_discord_hooks(self, guild_hooks, bot_user_id: int):
        """
        Loads the list of Discord Webhooks which are where the Event Notifications are sent to.
        :param guild_hooks: The list of lists of Webhooks, where each index is for a different Guild.
        :param bot_user_id: The Discord user ID of the bot that is running.
        """

        for guild in guild_hooks:
            # For each guild in the list...
            for g_hook in guild:
                # And for each Webhook in the guild...
                if WEBHOOK_PREFIX in g_hook.name and g_hook.user.id == bot_user_id:
                    # Only if the Webhook was created for the TwitterCog and by the bot.
                    self.hooks[g_hook.id] = {"token": g_hook.token, "name": g_hook.name, "guild_id": g_hook.guild_id}

    async def get_bearer(self):
        """
        Gets the current bearer token and information or generates a new one if the current one has expired.
        :return: A dictionary containing when the token was created, how long it lasts for and the token itself.
        """

        self.logger.debug("Checking Twitch bearer token status...")
        current_time = datetime.now()
        if self.bearer is not None:
            # If there is a currently active bearer, check if it is still valid.
            grant_time = datetime.strptime(self.bearer.get("granted_on"), DATETIME_FMT)
            time_delta = current_time - grant_time
            delta_seconds = time_delta.total_seconds()
            expires_in = self.bearer.get("expires_in")  # Number of seconds the token is valid for.
            if delta_seconds + BEARER_PADDING < expires_in:
                # The bearer is still valid, and will be still valid for the BEARER_PADDING time.
                self.logger.debug(
                    "Current Twitch bearer token is still valid, there are %d seconds remaining!",
                    (expires_in - delta_seconds)
                )
                return self.bearer

        bearer_url = "https://id.twitch.tv/oauth2/token"
        params = {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "grant_type": "client_credentials"}

        # Get a new bearer:
        async with aiohttp.ClientSession() as session:
            async with session.post(url=bearer_url, params=params) as response:
                if response.status != 200:
                    self.bearer = None
                else:
                    data = await response.json()
                    self.bearer = {
                        "granted_on": current_time.strftime(DATETIME_FMT),
                        "expires_in": data.get("expires_in"),
                        "access_token": data.get("access_token")
                    }

        # TODO: Remove temp code
        if self.bearer is not None:
            with open("bearer", "w") as f:
                f.write(self.bearer.get("granted_on") + "\n")
                f.write(self.bearer.get("expires_in") + "\n")
                f.write(self.bearer.get("access_token"))
        return self.bearer

    def set_bearer(self, bearer):
        """
        Sets the current bearer information.
        :param bearer: The bearer information to set the bearer to .
        """

        self.bearer = bearer

    async def load_tracked_channels(self, db_channels):
        """
        From the channel data gathered from the database, check that each of them are being tracked by a subscription and
        removes any old subscriptions that are no longer being tracked and sets the tracked_channels attribute to db_channels.
        :param db_channels: The dictionary of channel IDs to set of guild IDs
        """

        # Get the list of events we are subscribed to from Twitch's end.
        subscribed_events = await self.get_subscribed_events()
        self.subscriptions = subscribed_events
        channels_not_tracked = list(db_channels.keys())

        # Ensure that the events that are tracked by Twitch are still ones we want to track:
        for event in subscribed_events:
            if event.get("type") != "stream.online":
                # Event isn't for a stream coming online, we don't want to track any other events so delete it...
                self.logger.info(
                    "Twitch Event for %s is not a Stream Online event, deleting!",
                    event.get("condition").get("broadcaster_user_id")
                )
                await self.delete_subscription(event.get("id"))
                continue
            channel_tracked = event.get("condition").get("broadcaster_user_id")

            if channel_tracked not in db_channels:
                # The channel is no longer tracked in the DB, assume we no longer want to track the channel so delete it...
                self.logger.info(
                    "Twitch Event for %s is no longer tracked, deleting!",
                    event.get("condition").get("broadcaster_user_id")
                )
                await self.delete_subscription(event.get("id"))
            else:
                channels_not_tracked.remove(channel_tracked)

        # Any channels here are ones that we want to have tracked but there is no event we are subscribed to for it.
        for channel in channels_not_tracked:
            self.logger.warning("No Twitch event for channel with ID %s, subscribing to new event...", channel)
            await self.create_subscription("stream.online", channel_id=channel)

        self.tracked_channels = db_channels

    async def delete_subscription(self, event_id):
        """
        Deletes a Twitch Event Subscription given the Event's ID.
        :param event_id: The ID of the event to delete.
        """

        delete_url = "https://api.twitch.tv/helix/eventsub/subscriptions"
        params = {"id": event_id}
        bearer_info = await self.get_bearer()
        headers = {"Client-ID": CLIENT_ID, "Authorization": "Bearer " + bearer_info.get("access_token")}

        async with aiohttp.ClientSession() as session:
            async with session.delete(url=delete_url, params=params, headers=headers) as response:
                if response.status == 204:
                    # Remove the event from the list:
                    self.subscriptions = [x for x in self.subscriptions if x.get("id") != event_id]
                    return True
                return False

    async def create_subscription(self, event_type, channel_id=None, channel_name=None):
        """
        Creates a new Event Subscription for a given channel ID for a given Event Type.
        :param event_type: The Event to subscribe to.
        :param channel_id: The ID of the channel.
        :param channel_name: The name of the channel.
        """

        if channel_id is None and channel_name is None:
            self.logger.error("A Twitch channel ID or Twitch channel name must be supplied. Both cannot be None.")
            return False

        if channel_id is None:
            # Get the channel ID from the channel name.
            channel_info = await self.get_channel_info(channel_name)

            if len(channel_info) == 0:
                return False

            channel_info = channel_info[0]
            channel_id = channel_info.get("id")

        subscription_url = "https://api.twitch.tv/helix/eventsub/subscriptions"
        bearer_info = await self.get_bearer()
        headers = {
            "Client-ID": CLIENT_ID,
            "Authorization": "Bearer " + bearer_info.get("access_token"),
            "Content-Type": "application/json"
        }

        # The required body to subscribe to an event:
        body = {
            "type": event_type,
            "version": "1",
            "condition": {
                "broadcaster_user_id": channel_id
            },
            "transport": {
                "method": "webhook",
                "callback": CALLBACK_URL,
                "secret": SUBSCRIPTION_SECRET
            }
        }

        # Needs to be as a json:
        body_json = json.dumps(body)
        async with aiohttp.ClientSession() as session:
            async with session.post(url=subscription_url, data=body_json, headers=headers) as response:
                if response.status == 202:
                    return True
                return False

    async def get_channel_info(self, channel_name):
        """
        Returns the information about the given channel using its name as the lookup parameter.
        :param channel_name: The name of the channel.
        :return: A dictionary containing the information about a twitch channel or None if there was an error.
        """

        channel_url = "https://api.twitch.tv/helix/search/channels"
        params = {"query": channel_name}
        bearer_info = await self.get_bearer()
        headers = {"Client-ID": CLIENT_ID, "Authorization": "Bearer " + bearer_info.get("access_token")}

        async with aiohttp.ClientSession() as session:
            async with session.get(url=channel_url, params=params, headers=headers) as response:
                if response.status != 200:
                    self.logger.error("Unable to get Twitch channel info! Response status was %d", response.status)
                    return None
                data = await response.json()
                return data.get("data")

    async def get_subscribed_events(self):
        """
        Returns a list of information about the current events that are currently subscribed to.
        :return: A list of dictionaries.
        """

        events_url = "https://api.twitch.tv/helix/eventsub/subscriptions"
        bearer_info = await self.get_bearer()
        headers = {"Client-ID": CLIENT_ID, "Authorization": "Bearer " + bearer_info.get("access_token")}
        async with aiohttp.ClientSession() as session:
            async with session.get(url=events_url, headers=headers) as response:
                if response.status != 200:
                    self.logger.error("Unable to get subscribed event list! Response status was %d", response.status)
                    return None
                data = await response.json()
                return data.get("data")

    def add_hook(self, hook):
        """
        Adds a new hook the dictionary of tracked hooks.
        :param hook: The hook to add.
        :return: A boolean of weather the hook was added to the dictionary of hooks.
        """

        if hook.id in self.hooks:
            return False
        self.hooks[hook.id] = {"token": hook.token, "name": hook.name, "guild_id": hook.guild_id}
        return True


class TwitchListener(tornado.web.RequestHandler):
    """
    This TwitchListener is the webserver that listens for requests.
    """

    def __init__(self, application: "Application", request: httputil.HTTPServerRequest, **kwargs: Any):
        super().__init__(application, request, **kwargs)
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def verify_twitch(headers, body):
        """
        Using the headers and the body of a message, confirm weather or not the incoming request came from Twitch.
        :param headers: The request's headers.
        :param body: The raw body of the request, not turned into a dict or other kind of data.
        :return: True if the signature provided in the header is the same as the calculated signature.
        """

        message_signature = headers.get("Twitch-Eventsub-Message-Signature")
        hmac_message = headers.get("Twitch-Eventsub-Message-Id") + headers.get("Twitch-Eventsub-Message-Timestamp") + body
        hmac_message_bytes = bytes(hmac_message, "utf-8")
        secret_bytes = bytes(SUBSCRIPTION_SECRET, "utf-8")

        calculated_signature = hmac.new(secret_bytes, hmac_message_bytes, hashlib.sha256)
        expected_signature = "sha256=" + calculated_signature.hexdigest()

        return expected_signature == message_signature

    async def post(self):
        """
        When a POST request is received by this web listener, this method is called to determine what to do with the
        incoming request. The general structure to this method can be found in the Twitch documentation:
        https://dev.twitch.tv/docs/eventsub#subscriptions.
        """

        self.logger.debug("Received a POST request on /webhook")
        current_request = self.request
        message_body = current_request.body.decode("utf-8")
        body_dict = ast.literal_eval(message_body)
        message_headers = current_request.headers

        # Check for messages that have already been received and processed. Twitch will repeat a message if it
        # thinks we have not received it.
        if message_headers.get("Twitch-Eventsub-Message-Id") in self.application.seen_ids:
            self.logger.debug("The message was already received before, ignoring!")
            self.set_status(208)
            await self.finish()
            return
        else:
            self.application.seen_ids.add(message_headers.get("Twitch-Eventsub-Message-Id"))

        # Verify that the message we have received has come from Twitch.
        if not self.verify_twitch(message_headers, message_body):
            self.logger.error(
                "The message received at %s was not a legitimate message from Twitch, ignoring!",
                message_headers.get("Twitch-Eventsub-Message-Timestamp")
            )
            self.set_status(403)
            await self.finish()
            return

        # POST requests from Twitch will either be to confirm that we own the webhook we just created or will be a notification
        # for an event we are subscribed to.
        if message_headers.get("Twitch-Eventsub-Message-Type") == "webhook_callback_verification":
            # Received shortly after creating a new EventSub.
            challenge = body_dict.get("challenge")
            self.application.subscriptions.append(body_dict.get("subscription"))
            self.logger.info("Responding to Webhook Verification Callback with challenge: %s", challenge)
            await self.finish(challenge)
        elif message_headers.get("Twitch-Eventsub-Message-Type") == "notification":
            # Received once a subscribed event occurs.
            self.logger.info("Received valid notification from Twitch!")
            self.set_status(200)
            asyncio.create_task(self.send_webhook(body_dict))

    async def send_webhook(self, request_body: dict):
        """
        Formats a message and send the information of the event to the required discord hooks.
        :param request_body: The body of the request that was received.
        """

        event = request_body.get("event")

        channel_name = event.get("broadcaster_user_login")

        channel_info = await self.application.get_channel_info(channel_name)
        game_name = channel_info.get("game_name")
        stream_title = channel_info.get("title")
        user_icon = channel_info.get("thumbnail_url")

        # Create the embed to send to the webhook.
        embed = Embed(
            title=stream_title,
            url=f"https://www.twitch.tv/{channel_name}",
            description=f"Playing {game_name}",
            color=TWITCH_EMBED_COLOUR
        )
        embed.set_author(name=channel_name, url=f"https://www.twitch.tv/{channel_name}", icon_url=user_icon)
        embed.set_thumbnail(url=user_icon)

        # Get the list of guilds to send the update to.
        channel_guilds = self.application.tracked_channels.get(channel_info.get("id"))

        async with aiohttp.ClientSession() as session:
            hook_adapter = AsyncWebhookAdapter(session)
            for hook_id in self.application.hooks:
                if self.application.hooks.get(hook_id).get("guild_id") not in channel_guilds:
                    # Webhook's guild is not one in the channels guilds.
                    continue

                hook_token = self.application.hooks.get(hook_id).get("token")
                webhook = Webhook.partial(id=hook_id, token=hook_token, adapter=hook_adapter)
                self.logger.info(
                    "Sending Twitch notification to Discord Webhook %s(%s) in guild %s",
                    webhook.name,
                    hook_id,
                    webhook.guild.name
                )
                await webhook.send(embed=embed, username=channel_name + " is Live!", avatar_url=TWITCH_ICON)


class TwitchCog(commands.Cog):
    """
    The TwitchCog that handles communications from Twitch.
    """

    def __init__(self, bot):
        self._bot = bot
        self.logger = logging.getLogger(__name__)
        self._db = db_gateway()
        self.user_strings = self._bot.STRINGS["twitch"]
        self._http_server, self._twitch_app = self.setup_http_listener()

    @staticmethod
    def setup_http_listener():
        """
        Sets up the HTTP server to receive the requests from Twitch.
        :return: A tuple containing the instance of the HTTP server and the Application running in the server.
        """

        # Setup the TwitchListener to listen for /webhook requests.
        app = TwitchApp([(r"/webhook", TwitchListener)])
        http_server = HTTPServer(app, ssl_options={"certfile": "server.crt", "keyfile": "server.key"})
        http_server.listen(443)
        return http_server, app

    @commands.Cog.listener()
    async def on_ready(self):
        """
        Is run when the Discord bot gives the signal that it is connected and ready.
        """

        # TODO: Remove temp code
        with open("bearer", "r") as f:
            lines = f.readlines()
        bearer = {
            "granted_on": lines[0].replace("\n", ""),
            "expires_in": int(lines[1].replace("\n", "")),
            "access_token": lines[2].replace("\n", "")
        }
        self._twitch_app.set_bearer(bearer)
        # TODO: Temp code above

        self._http_server.start()

        self.logger.info("Loading Discord Webhooks for Twitch Cog...")

        tasks = []
        for guild in self._bot.guilds:
            self.logger.info("Loading webhooks from guild %s(%s)", guild.name, guild.id)
            if guild.me.guild_permissions.manage_webhooks:
                tasks.append(guild.webhooks())
            else:
                self.logger.error("Missing permission 'manage webhooks' in guild %s(%s)", guild.name, guild.id)

        # Wait for all the tasks to finish.
        results = await asyncio.gather(*tasks)

        # Add the hooks to the App.
        self._twitch_app.load_discord_hooks(results, self._bot.user.id)
        self.logger.info(
            "Currently using %d Discord Webhooks in %d guilds for Twitch notifications.",
            len(self._twitch_app.hooks),
            len(self._bot.guilds)
        )

        # Load tracked channels from DB.
        db_data = self.load_db_data()
        await self._twitch_app.load_tracked_channels(db_data)
        if len(db_data) > 0:
            self.logger.info("Currently tracking %d Twitch channels(s)", len(db_data))
        else:
            self.logger.warning("There are no Twitch channels that are currently tracked!")

    @commands.Cog.listener()
    async def on_disconnect(self):
        """
        Is executed whenever the client loses a connection to Discord. Could be when no internet or when logged out.
        """

        if self._bot.is_closed:
            self._http_server.stop()

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel):
        pass
        # TODO: Capture this event to determine when a webhook gets deleted not using the command.

    def load_db_data(self):
        """
        Loads all the currently tracked Twitch channels and which guilds they are tracked in from the database.
        :return: A dictionary of Twitch channel ID to a set of guild IDs.
        """

        db_data = self._db.pure_return("SELECT guild_id, twitch_channel_id FROM twitch_info")
        guild_info = defaultdict(set)
        for item in db_data:
            guild_info[str(item.get("twitch_channel_id"))].add(item.get("guild_id"))
        return guild_info

    @commands.group(
        pass_context=True,
        invoke_without_command=True,
        help="Access the Twitch integration functions with this command"
    )
    async def twitch(self, ctx):
        """
        Empty command, purely used to organise subcommands to be under twitch <command> instead of having to ensure name
        uniqueness.
        """

        pass

    @twitch.command(
        name="createhook",
        usage="[#channel] [hook name]",
        help="Creates a new Discord Webhook that will be used to post the notifications of Twitch channels going live"
    )
    async def createhook(self, ctx, channel=None, hook_name=None):
        """
        Creates a new Discord Webhook for use of the Twitch updates.
        :param ctx: The context of the command.
        :param channel: The channel to bind the Webhook to if not None.
        :param hook_name: The name of the Webhook if not None.
        :return: Whether a Webhook was created with the given name and bound to the given channel.
        """

        if hook_name is None:
            hook_name = DEFAULT_HOOK_NAME

        if hook_name == WEBHOOK_PREFIX:
            hook_name = DEFAULT_HOOK_NAME

        # If the channel was given, get the channel instance, else get the current channel from context.
        if channel is not None:
            text_channel = await self.channel_from_mention(channel)
        else:
            text_channel = ctx.channel

        if text_channel is None:
            await ctx.send(
                self.user_strings["webhook_error"].format(operation="create",
                                                          reason="I am unable to find that channel")
            )
            return False

        hook_name = WEBHOOK_PREFIX + hook_name
        existing, _ = self.get_webhook_by_name(hook_name, ctx.guild.id)

        if existing is not None:
            # Webhook already exists with the given name.
            self.logger.warning(
                "Attempted to create Webhook with name %s but one already exists with that name in %s(%s)",
                hook_name,
                ctx.guild.name,
                ctx.guild.id
            )
            await ctx.send(
                self.user_strings["webhook_error"].format(
                    operation="create",
                    reason=f"there is already a Webhook with the name {hook_name}"
                )
            )
            return False

        self.logger.info(
            "Creating Webhook for guild %s(%s) with name %s in channel %s(%s)",
            ctx.guild.name,
            ctx.guild.id,
            hook_name,
            text_channel.name,
            text_channel.id
        )

        hook = await text_channel.create_webhook(
            name=hook_name,
            reason=f"{ctx.author.name}#{ctx.author.discriminator} "
            f"created a webhook for #{text_channel.name} using the twitchhook command."
        )

        self.logger.debug(
            "Twitch Webhook Info: [%s] id: %s , url: %s , token: %s , channel: %s(%s)",
            hook.name,
            hook.id,
            hook.url,
            hook.token,
            hook.channel.name,
            hook.channel.id
        )
        self._twitch_app.add_hook(hook)
        await ctx.send(self.user_strings["webhook_created"].format(name=hook.name, hook_id=hook.id))
        return True

    @twitch.command(
        name="deletehook",
        usage="<hook name>",
        help="Deletes a Discord Webhook that was created for posting Twitch notifications by supplying the name of the Webhook"
    )
    async def deletehook(self, ctx, name):
        """
        Deletes a Discord Webhook using the given name.
        :param ctx: The context of the command.
        :param name: The name of the Webhook to delete.
        :return: A boolean of if the Webhook was deleted or not.
        """

        h_id, hook_info = self.get_webhook_by_name(name, ctx.guild.id)
        if hook_info is None:
            await ctx.send(
                self.user_strings["webhook_error"].format(
                    operation="remove",
                    reason=f"there is no Webhook with name {name} or {WEBHOOK_PREFIX + name}"
                )
            )
            return False

        async with aiohttp.ClientSession() as session:
            webhook = Webhook.partial(id=h_id, token=hook_info.get("token"), adapter=AsyncWebhookAdapter(session))
            await webhook.delete(reason="Deleted with removetwitchhook command")
            self._twitch_app.hooks.pop(h_id)
        await ctx.send(self.user_strings["webhook_deleted"].format(name=hook_info.get("name"), hook_id=h_id))
        return True

    @twitch.command(
        name="add",
        usage="<channel name|channel url> [custom message]",
        help="Adds a Twitch channel to be tracked for when it goes live. If a custom 'go live' message is given it must be "
        "surrounded by double quotes"
    )
    async def add(self, ctx, channel, custom_message=None):
        """
        Add a Twitch channel to be tracked in the current guild.
        :param ctx: The context of the command.
        :param channel: The name of the Twitch channel to track.
        :param custom_message: The custom message to send along with the notification.
        :return: A boolean if the channel was added to the tracked channels.
        """

        # Accept urls and get just the channel from the url.
        if "https://twitch.tv/" in channel:
            channel = channel.split("tv/")[-1]

        if channel_id := (await self.get_channel_id(ctx, channel)):
            if channel_id in self._twitch_app.tracked_channels:
                # Channel is already tracked in one or more guilds:
                if ctx.guild.id in self._twitch_app.tracked_channels.get(channel_id):
                    # Channel is already tracked in this guild.
                    self.logger.info(
                        "Not adding %s to tracked Twitch channels as it is already tracked in %s(%s)",
                        channel,
                        ctx.guild.name,
                        ctx.guild.id
                    )
                    await ctx.send(self.user_strings["channel_exists_error"].format(channel=channel))
                    return False
                else:
                    # Channel is tracked in other guilds, but not this one, add it to the tracked channels:
                    self._twitch_app.tracked_channels[channel_id].add(ctx.guild.id)
                    self._db.insert(
                        "twitch_info",
                        params={
                            "guild_id": ctx.guild.id,
                            "twitch_channel_id": str(channel_id),
                            "twitch_handle": channel,
                            "custom_message": custom_message
                        }
                    )
                    await ctx.send(self.user_strings["channel_added"].format(channel=channel))
                    return True

            # Channel is not tracked in any guild yet:
            if await self._twitch_app.create_subscription("stream.online", channel_name=channel):
                self.logger.info("Successfully created a new EventSub for %s Twitch channel", channel)
                self._db.insert(
                    "twitch_info",
                    params={
                        "guild_id": ctx.guild.id,
                        "twitch_channel_id": str(channel_id),
                        "twitch_handle": channel,
                        "custom_message": custom_message
                    }
                )
                await ctx.send(self.user_strings["channel_added"].format(channel=channel))
                return True
            else:
                self.logger.error("Unable to create new EventSub for %s Twitch channel", channel)
                await ctx.send(self.user_strings["generic_error"].format(channel=channel))
                return False
        return False

    @twitch.command(
        name="remove",
        usage="<channel name>",
        help="Stops tracking a Twitch channel so that notifications of when it goes live are no longer posted"
    )
    async def remove(self, ctx, channel):
        """
        Remove a Twitch channel from being tracked in the current guild.
        :param ctx: The context of the command.
        :param channel: The Twitch channel to stop tracking.
        :return: A boolean if the channel is no longer being tracked in the current guild.
        """

        if channel_id := (await self.get_channel_id(ctx, channel)):

            if channel_id not in self._twitch_app.tracked_channels:
                # The channel was not tracked in any guild.
                self.logger.info("No longer tracking %s Twitch channel, was not tracked before", channel)
                await ctx.send(self.user_strings["channel_not_added_error"].format(channel=channel))
                return False

            if ctx.guild.id not in self._twitch_app.tracked_channels.get(channel_id):
                # The channel was not tracked in the current guild.
                self.logger.info("No longer tracking %s Twitch channel, was not tracked before in current guild", channel)
                await ctx.send(self.user_strings["channel_not_added_error"].format(channel=channel))
                return False

            if ctx.guild.id in self._twitch_app.tracked_channels.get(channel_id) and \
                    len(self._twitch_app.tracked_channels.get(channel_id)) > 1:
                # The channel is tracked in other guilds.
                self._twitch_app.tracked_channels[channel_id].remove(ctx.guild.id)
                self._db.delete("twitch_info", where_params={"guild_id": ctx.guild.id, "twitch_channel_id": channel_id})
                self.logger.info("No longer tracking %s Twitch channel in %s(%s)", channel, ctx.guild.name, ctx.guild.id)
                await ctx.send(self.user_strings["channel_removed"].format(channel=channel))
                return True

            event = None
            # Find the event id to be used to delete the EventSub.
            for subscription in self._twitch_app.subscriptions:
                if subscription.get("condition").get("broadcaster_user_id") == channel_id:
                    event = subscription.get("id")
                    break

            if event is not None:
                result = await self._twitch_app.delete_subscription(event)

            self._db.delete("twitch_info", where_params={"guild_id": ctx.guild.id, "twitch_channel_id": channel_id})
            self._twitch_app.tracked_channels.pop(channel_id)
            self.logger.info("No longer tracking %s Twitch channel in %s(%s)", channel, ctx.guild.name, ctx.guild.id)
            await ctx.send(self.user_strings["channel_removed"].format(channel=channel))
            return True
        return False

    @twitch.command(name="list", help="Shows a list of currently tracked Twitch channels and their custom messages, if any")
    async def list(self, ctx):
        """
        Sends a list of the currently tracked Twitch channels in the current guild and their custom messages.
        :param ctx: The context of the command.
        """

        all_channels = self._db.pure_return(
            f"SELECT twitch_handle, custom_message "
            f"FROM twitch_info "
            f"WHERE guild_id={ctx.guild.id}"
        )

        if len(all_channels) == 0:
            await ctx.send(self.user_strings["channels_empty"])
            return

        embed = Embed(title="**Currently Tracked Channels:**", description="​", color=TWITCH_EMBED_COLOUR)
        embed.set_author(name="Twitch Channels", icon_url=TWITCH_ICON)

        for channel in all_channels:
            custom_message = "​" if channel.get("custom_message") is None else channel.get("custom_message")
            embed.add_field(name=channel.get("twitch_handle"), value=custom_message, inline=False)

        await ctx.send(embed=embed)

    @twitch.command(
        name="setmessage",
        usage="<channel name> [message]",
        help="Sets the custom 'go live' message for a Twitch channel. Leave the message empty if you want to remove the "
        "custom message. If the message is not empty be sure to surround the message with double quotes"
    )
    async def setmessage(self, ctx, channel, message: str = None):
        """
        Sets the custom live message for a Twitch channel.
        :param ctx: The context of the command.
        :param channel: The Twitch channel to set the custom message for.
        :param message: The message to set the custom message to.
        """

        if channel_id := (await self.get_channel_id(ctx, channel)):

            db_return = self._db.pure_return(
                f"SELECT custom_message from twitch_info WHERE guild_id={ctx.guild.id} AND twitch_channel_id='{channel_id}'"
            )
            if len(db_return) == 0:
                await ctx.send(self.user_strings["channel_not_added_error"].format(channel=channel))
                return

            if message is not None and message.strip() == "" or message == "":
                message = None

            self._db.pure_return(
                f"UPDATE twitch_info "
                f"SET custom_message={message} "
                f"WHERE guild_id={ctx.guild.id} "
                f"AND twitch_channel_id={channel_id}"
            )
            await ctx.send(self.user_strings["set_custom_message"].format(channel=channel, message=message))

    @twitch.command(
        name="getmessage",
        usage="<channel name>",
        help="Retrieves the currently set custom 'go live' message for a Twitch channel"
    )
    async def getmessage(self, ctx, channel):
        """
        Gets the custom message for a Twitch channel.
        :param ctx: The context of the command.
        :param channel: The Twitch channel to get the custom message of.
        """

        if channel_id := (await self.get_channel_id(ctx, channel)):

            message = self._db.pure_return(
                f"SELECT custom_message from twitch_info WHERE guild_id={ctx.guild.id} AND twitch_channel_id='{channel_id}'"
            )
            if len(message) == 0:
                await ctx.send(self.user_strings["channel_not_added_error"].format(channel=channel))
                return
            custom_message = message[0].get("custom_message")

            if custom_message is None:
                custom_message = "not set"

            await ctx.send(self.user_strings["get_custom_message"].format(channel=channel, message=custom_message))

    # TODO: Probably best to move this to lib or some other as it is shared by TwitterCog
    async def channel_from_mention(self, c_id):
        """
        Gets an instance of a channel when the channel was mentioned in the message.
        :param c_id: The mentioned channel.
        :return: An instance of a channel or None if there is no channel with the given mention.
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

    # TODO: Probably best to move this to lib or some other as it is shared by TwitterCog
    def get_webhook_by_name(self, name, guild_id):
        """
        Gets the information about a Discord Webhook given its name.
        :param name: The name of the Webhook.
        :param guild_id: The ID of the guild where the Webhook is in.
        :return: A Tuple of hook ID and hook information.
        """

        current_hooks = self._twitch_app.hooks
        if WEBHOOK_PREFIX not in name:
            # Only find webhooks created for this cog.
            name = WEBHOOK_PREFIX + name
        for hook in current_hooks:
            if current_hooks.get(hook).get("name") == name:
                if current_hooks.get(hook).get("guild_id") == guild_id:
                    return hook, current_hooks.get(hook)

        return None, None

    async def get_channel_id(self, ctx, channel):
        """
        Gets the Twitch Channel ID for a given channel name.
        :param ctx: The context of the command.
        :param channel: The name of the Twitch channel to find the ID of.
        :returns None if there is no channel with that ID, else a string of the ID.
        """

        channel_info = await self._twitch_app.get_channel_info(channel)

        if len(channel_info) == 0:
            await ctx.send(self.user_strings["channel_missing_error"].format(channel=channel))
            return None

        channel_info = channel_info[0]
        channel_id = channel_info.get("id")
        return channel_id


def setup(bot):
    logger = logging.getLogger(__name__)
    try:
        assert CLIENT_ID != "" and CLIENT_ID is not None, \
            "A CLIENT_ID must be provided in your secrets file. " \
            "If you don't want to use the Twitch integration, set ENABLE_TWITCH to FALSE"
        assert CLIENT_SECRET != "" and CLIENT_SECRET is not None, \
            "A CLIENT_SECRET must be provided in your secrets file. " \
            "If you don't want to use the Twitch integration, set ENABLE_TWITCH to FALSE"
        assert SUBSCRIPTION_SECRET != "" and SUBSCRIPTION_SECRET is not None, \
            "A SUBSCRIPTION_SECRET must be provided in your secrets file. " \
            "If you don't want to use the Twitch integration, set ENABLE_TWITCH to FALSE"
        assert CALLBACK_URL != "/webhook" and CALLBACK_URL is not None, \
            "A CALLBACK_URL must be provided in your secrets file. " \
            "If you don't want to use the Twitch integration, set ENABLE_TWITCH to FALSE"
        bot.add_cog(TwitchCog(bot))
    except AssertionError:
        logger.error(
            "There were one or more environment variables not supplied to the TwitchCog. Disabling the Cog...",
            exc_info=True
        )
