"""
The TwitchCog module implements a HTTP Server to listen for requests, as well as a Discord Cog to allow for changing of where
Twitch notifications get sent and which accounts notifications are sent for.

.. codeauthor:: Fluxticks
"""

import asyncio
import json
from datetime import datetime
import hashlib
import hmac
import os
from typing import Any

import aiohttp
import discord
from discord import Webhook, Embed, AsyncWebhookAdapter
from tornado.httpserver import HTTPServer
import tornado.web

import ast

from discord.ext import commands
from tornado import httputil
from tornado.web import Application

import logging

from esportsbot.db_gateway import DBGatewayActions
from esportsbot.lib.discordUtil import get_webhook_by_name, load_discord_hooks
from esportsbot.models import Twitch_info

SUBSCRIPTION_SECRET = os.getenv("TWITCH_SUB_SECRET")
CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
BEARER_TEMP_FILE = os.getenv("TEMP_BEARER_FILE")
WEBHOOK_PREFIX = "TwitchHook-"
BEARER_PADDING = 2 * 60  # Number of minutes before expiration of bearer where the same bearer will still be used.
DATETIME_FMT = "%d/%m/%Y %H:%M:%S"
TWITCH_EMBED_COLOUR = 0x6441a4
TWITCH_ICON = "https://pbs.twimg.com/profile_images/1189705970164875264/oXl0Jhyd_400x400.jpg"
CALLBACK_URL = os.getenv("TWITCH_CALLBACK") + "/webhook"  # The URL to be used as for the event callback.
DEFAULT_HOOK_NAME = "DefaultTwitchHook"

TWITCH_HELIX_BASE = "https://api.twitch.tv/helix"
TWITCH_EVENT_BASE = TWITCH_HELIX_BASE + "/eventsub"
TWITCH_SUB_BASE = TWITCH_EVENT_BASE + "/subscriptions"
TWITCH_ID_BASE = "https://id.twitch.tv"
TWITCH_BASE = "https://twitch.tv"


class TwitchApp(Application):
    """
    This TwitchApp is the application which the TwitchListener is serving and handling requests for.
    Mainly used to store data that is used across requests, as well as handling any API requests that need to be made.
    """
    def __init__(self, handlers=None, default_host=None, transforms=None, **settings: Any):
        super().__init__(handlers, default_host, transforms, **settings)
        self.seen_ids = set()
        self.hooks = {}  # Hook ID: {"token": token, "guild id": guild id, "name": name}
        self.bearer = None
        self.tracked_channels = None  # Channel ID : {Hook ID : message}
        self.subscriptions = []
        self.logger = logging.getLogger(__name__)

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

        bearer_url = TWITCH_ID_BASE + "/oauth2/token"
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

        self.save_bearer()
        return self.bearer

    def load_bearer(self):
        try:
            with open(BEARER_TEMP_FILE, "r") as f:
                lines = f.readlines()
            self.bearer = {
                "granted_on": lines[0].replace("\n",
                                               ""),
                "expires_in": int(lines[1].replace("\n",
                                                   "")),
                "access_token": lines[2].replace("\n",
                                                 "")
            }
        except FileNotFoundError:
            self.bearer = None

    def save_bearer(self):
        if self.bearer is not None:
            with open(BEARER_TEMP_FILE, "w") as f:
                f.write(str(self.bearer.get("granted_on")) + "\n")
                f.write(str(self.bearer.get("expires_in")) + "\n")
                f.write(str(self.bearer.get("access_token")))

    async def load_tracked_channels(self, db_channels):
        """
        Set the tracked_channels attribute to db_channels param, and perform checks to ensure all the information is still
        needed or if any information is missing:

        From the channel data gathered from the database, check that each of them are being tracked by a subscription and
        remove any old subscriptions that are no longer being tracked.
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

        delete_url = TWITCH_SUB_BASE
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

    async def delete_channel_subscription(self, channel_id):
        event = None
        for subscription in self.subscriptions:
            if subscription.get("condition").get("broadcaster_user_id") == channel_id:
                event = subscription.get("id")
                break

        if not event:
            return False

        return await self.delete_subscription(event)

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

        subscription_url = TWITCH_SUB_BASE
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
                "broadcaster_user_id": str(channel_id)
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
                return response.status == 202

    async def get_channel_info(self, channel_name):
        """
        Returns the information about the given channel using its name as the lookup parameter.
        :param channel_name: The name of the channel.
        :return: A dictionary containing the information about a twitch channel or None if there was an error.
        """

        channel_url = TWITCH_HELIX_BASE + "/search/channels"
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

        events_url = TWITCH_SUB_BASE
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

    def set_hooks(self, hooks):
        self.hooks = hooks


class TwitchListener(tornado.web.RequestHandler):
    """
    This TwitchListener is the webserver that listens for requests.
    """
    def __init__(self, application: "TwitchApp", request: httputil.HTTPServerRequest, **kwargs: Any):
        super().__init__(application, request, **kwargs)
        self.application: TwitchApp = application
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
        if not channel_info:
            return
        channel_info = channel_info[0]
        game_name = channel_info.get("game_name")
        stream_title = channel_info.get("title")
        user_icon = channel_info.get("thumbnail_url")

        async with aiohttp.ClientSession() as session:
            hook_adapter = AsyncWebhookAdapter(session)
            for hook_id in self.application.tracked_channels.get(channel_info.get("id")):
                hook_token = self.application.hooks.get(hook_id).get("token")
                webhook = Webhook.partial(id=hook_id, token=hook_token, adapter=hook_adapter)
                custom_message = self.application.tracked_channels.get(channel_info.get("id")).get(hook_id)

                description = "​" if custom_message is None else custom_message

                embed = Embed(
                    title=stream_title,
                    url=f"{TWITCH_BASE}/{channel_name}",
                    description=description,
                    color=TWITCH_EMBED_COLOUR
                )
                embed.set_author(name=channel_name, url=f"{TWITCH_BASE}/{channel_name}", icon_url=user_icon)
                embed.set_thumbnail(url=user_icon)
                embed.add_field(name="**Current Game:**", value=f"**{game_name}**")

                await webhook.send(embed=embed, username=channel_name + " is Live!", avatar_url=TWITCH_ICON)
                self.logger.info("Sending Twitch notification to Discord Webhook %s(%s)", webhook.name, hook_id)


class TwitchCog(commands.Cog):
    """
    The TwitchCog that handles communications from Twitch.
    """
    def __init__(self, bot):
        self._bot = bot
        self.logger = logging.getLogger(__name__)
        self._db = DBGatewayActions()
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
        http_server = HTTPServer(app, ssl_options={"certfile": "../server.crt", "keyfile": "../server.key"})
        http_server.listen(443)
        return http_server, app

    @commands.Cog.listener()
    async def on_ready(self):
        """
        Is run when the Discord bot gives the signal that it is connected and ready.
        """

        self._twitch_app.load_bearer()

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
        hooks = load_discord_hooks(WEBHOOK_PREFIX, results, self._bot.user.id)
        self._twitch_app.set_hooks(hooks)
        self.logger.info(
            "Currently using %d Discord Webhooks in %d guilds for Twitch notifications.",
            len(self._twitch_app.hooks),
            len(self._bot.guilds)
        )

        # Load tracked channels from DB.
        db_data = self.load_db_data()
        cleaned_data = self.remove_missing_hooks(db_data)
        await self._twitch_app.load_tracked_channels(cleaned_data)
        if len(cleaned_data) > 0:
            self.logger.info("Currently tracking %d Twitch channels(s)", len(cleaned_data))
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

    async def get_channel_id(self, channel):
        """
        Gets the Twitch Channel ID for a given channel name.
        :param channel: The name of the Twitch channel to find the ID of.
        :returns None if there is no channel with that ID, else a string of the ID.
        """

        channel_info = await self._twitch_app.get_channel_info(channel)

        if not channel_info:
            return None

        channel_info = channel_info[0]
        channel_id = channel_info.get("id")
        return str(channel_id)

    def load_db_data(self):
        """
        Loads all the currently tracked Twitch channels and which guilds they are tracked in from the database.
        :return: A dictionary of Twitch channel ID to a set of guild IDs.
        """

        db_data = self._db.list(Twitch_info)
        guild_info = {}
        for item in db_data:
            if str(item.channel_id) not in guild_info:
                guild_info[str(item.channel_id)] = {item.hook_id: item.custom_message}
            else:
                guild_info[str(item.channel_id)][item.hook_id] = item.custom_message

        return guild_info

    def remove_missing_hooks(self, db_data):
        """
        Removes any hooks for channels where the Discord Webhook has been deleted.
        :param db_data: The loaded DB data.
        :return: A cleaned version of the param db_data, with missing hooks removed.
        """
        cleaned_db = {}
        for channel in db_data:
            cleaned_db[channel] = {}
            hooks = db_data.get(channel)
            for hook in hooks:
                if hook in self._twitch_app.hooks:
                    cleaned_db[channel][hook] = hooks.get(hook)
                else:
                    db_item = self._db.get(Twitch_info, channel_id=channel, hook_id=hook)
                    if db_item:
                        self._db.delete(db_item)
            if not cleaned_db.get(channel):
                # If a channel has no hooks to post to, remove it from the list.
                cleaned_db.pop(channel)

        return cleaned_db

    async def remove_hook_from_channel(self, hook_id, channel_id):
        """
        Removes a Webhook from a channels list of webhooks to post updates to.
        :param hook_id: The ID of the hook to remove.
        :param channel_id: The ID of the channel to remove the hook from.
        :return: A boolean indicating if the hook ID was removed from the channels list of webhooks.
        """
        if channel_id not in self._twitch_app.tracked_channels:
            return False
        if hook_id not in self._twitch_app.tracked_channels.get(channel_id):
            return False
        self._twitch_app.tracked_channels.get(channel_id).pop(hook_id)
        db_item = self._db.get(Twitch_info, channel_id=channel_id, hook_id=hook_id)
        if db_item:
            self._db.delete(db_item)

        if not self._twitch_app.tracked_channels.get(channel_id):
            return await self._twitch_app.delete_channel_subscription(channel_id)

    async def get_channel_id_from_command(self, channel):
        """
        Gets the ID of the given channel. The given channel can either be the username of the Twitch URL.
        :param channel: The channel to find the ID of.
        :return: A string of the Twitch user's ID or None if there is no user with the given name.
        """
        if TWITCH_BASE in channel:
            channel = channel.split("tv/")[-1]

        return await self.get_channel_id(channel)

    def get_webhook_channels_as_embed(self, webhook_id, webhook_name):
        """
        Gets the list of channels and their custom messages for a given webhook.
        :param webhook_id: The ID of the Webhook to get the channels of.
        :param webhook_name: The name of the Webhook.
        :return: An embed representing the Twitch channels that post updates to the given Webhook.
        """
        db_items = self._db.list(Twitch_info, hook_id=webhook_id)
        embed = Embed(
            title="**Currently Tracked Channels:**",
            description=f"These are the currently tracked channels for the Webhook: \n`{webhook_name}`",
            color=TWITCH_EMBED_COLOUR
        )
        embed.set_author(name="Twitch Channels", icon_url=TWITCH_ICON)
        if not db_items:
            embed.add_field(name="No channels tracked", value="​", inline=False)
            return embed

        for item in db_items:
            custom_message = item.custom_message if item.custom_message else "<empty>"
            embed.add_field(name=item.twitch_handle, value=custom_message, inline=False)
        return embed

    @commands.group(name="twitch",  invoke_without_command=True)
    async def twitch(self, ctx):
        """
        Empty command, purely used to organise subcommands to be under twitch <command> instead of having to ensure name
        uniqueness.
        """

        pass

    @twitch.command(name="createhook", aliases=["newhook",  "makehook", "addhook"])
    @commands.has_permissions(administrator=True)
    async def create_new_hook(self, context, bound_channel: discord.TextChannel, hook_name: str):
        """
        Creates a new Discord Webhook with the given name that is bound to the given channel.
        :param context: The context of the command.
        :param bound_channel: The channel to bind the Webhook to.
        :param hook_name: The name of the Webhook
        """

        hook_id, hook_info = get_webhook_by_name(self._twitch_app.hooks, hook_name, context.guild.id, WEBHOOK_PREFIX)

        if hook_id is not None:
            await context.send(self.user_strings["webhook_exists"].format(name=hook_name))
            return

        if WEBHOOK_PREFIX not in hook_name:
            hook_name = WEBHOOK_PREFIX + hook_name
        hook = await bound_channel.create_webhook(name=hook_name, reason="Created new Twitch Webhook with command!")
        self._twitch_app.add_hook(hook)
        await context.send(
            self.user_strings["webhook_created"].format(name=hook_name,
                                                        channel=bound_channel.mention,
                                                        hook_id=hook.id)
        )

    @twitch.command(name="deletehook")
    @commands.has_permissions(administrator=True)
    async def delete_twitch_hook(self, context, hook_name: str):
        """
        Deletes a Discord Webhook if a Webhook with the given name exists in the guild.
        :param context: The context of the command.
        :param hook_name: The name of the Webhook to delete.
        """
        hook_id, hook_info = get_webhook_by_name(self._twitch_app.hooks, hook_name, context.guild.id, WEBHOOK_PREFIX)

        if hook_id is None:
            await context.send(self.user_strings["webhook_missing"].format(name=hook_name))
            return

        self._twitch_app.hooks.pop(hook_id)
        async with aiohttp.ClientSession() as session:
            webhook = Webhook.partial(id=hook_id, token=hook_info.get("token"), adapter=AsyncWebhookAdapter(session))
            await webhook.delete(reason=f"Deleted {hook_name} Twitch Webhook with command!")

        # Ensure that channels that were posting to that webhook are no longer trying to:
        hook_channels = self._db.list(Twitch_info, guild_id=context.guild.id, hook_id=hook_id)
        if not hook_channels:
            await context.send(self.user_strings["webhook_deleted"].format(name=hook_info.get("name"), hook_id=hook_id))
            return

        for channel in hook_channels:
            await self.remove_hook_from_channel(hook_id, channel.channel_id)

        await context.send(self.user_strings["webhook_deleted"].format(name=hook_info.get("name"), hook_id=hook_id))

    @twitch.command(name="add")
    @commands.has_permissions(administrator=True)
    async def add_twitch_channel(self, context, channel, webhook_name, custom_message=None):
        """
        Allows the Live notifications of the given twitch channel to be sent to the Webhook given with the given custom
        message.
        :param context: The context of the command.
        :param channel: The Twitch channel to track.
        :param webhook_name: The name of the webhook to send the notifications to.
        :param custom_message: The custom message to include in the live notification.
        """
        channel_id = await self.get_channel_id_from_command(channel)
        webhook_id, webhook_info = get_webhook_by_name(self._twitch_app.hooks, webhook_name, context.guild.id, WEBHOOK_PREFIX)

        if not channel_id:
            await context.send(self.user_strings["no_channel_error"].format(channel=channel))
            return

        if not webhook_id:
            await context.send(self.user_strings["webhook_missing"].format(name=webhook_name))
            return

        if channel_id in self._twitch_app.tracked_channels:
            # The given Twitch Channel is tracked by one or more Webhooks.
            if webhook_id in self._twitch_app.tracked_channels.get(channel_id):
                # The given Twitch Channel is already tracked in the given Webhook.
                await context.send(self.user_strings["channel_already_tracked"].format(name=channel, webhook=webhook_name))
                return
            self._twitch_app.tracked_channels[channel_id][webhook_id] = custom_message
            db_item = Twitch_info(
                guild_id=context.guild.id,
                hook_id=webhook_id,
                channel_id=channel_id,
                custom_message=custom_message,
                twitch_handle=channel
            )
            self._db.create(db_item)
            return

        if await self._twitch_app.create_subscription("stream.online", channel_name=channel):
            # Ensure that the Twitch EventSub was successful before adding the info to the DB.
            self._twitch_app.tracked_channels[channel_id] = {webhook_id: custom_message}
            db_item = Twitch_info(
                guild_id=context.guild.id,
                hook_id=webhook_id,
                channel_id=channel_id,
                custom_message=custom_message,
                twitch_handle=channel
            )
            self._db.create(db_item)
            await context.send(self.user_strings["channel_added"].format(twitch_channel=channel, discord_channel=webhook_name))
        else:
            # Otherwise don't if it failed.
            await context.send(self.user_strings["generic_error"].format(channel=channel))

    @twitch.command(name="remove")
    @commands.has_permissions(administrator=True)
    async def remove_twitch_channel(self, context, channel, webhook_name):
        """
        Stops sending live notifications for the given Twitch channel being sent ot the given Webhook.
        :param context: The context of the command.
        :param channel: The channel to stop sending updates for.
        :param webhook_name: The Webhook to stop sending updates to.
        """
        channel_id = await self.get_channel_id_from_command(channel)
        webhook_id, webhook_info = get_webhook_by_name(self._twitch_app.hooks, webhook_name, context.guild.id, WEBHOOK_PREFIX)

        if not channel_id:
            await context.send(self.user_strings["no_channel_error"].format(channel=channel))
            return

        if not webhook_name:
            await context.send(self.user_strings["webhook_missing"].format(name=webhook_name))
            return

        if channel_id in self._twitch_app.tracked_channels:
            # The given Twitch Channel is tracked by one or more Webhooks.
            if webhook_id not in self._twitch_app.tracked_channels.get(channel_id):
                # The given Twitch Channel is not tracked in the given Webhook.
                await context.send(self.user_strings["channel_not_tracked"].format(name=channel, webhook=webhook_name))
                return
            if await self.remove_hook_from_channel(webhook_id, channel_id):
                await context.send(
                    self.user_strings["channel_removed"].format(twitch_channel=channel,
                                                                discord_channel=webhook_name)
                )
                return
        else:
            await context.send(self.user_strings["channel_not_tracked"].format(name=channel, webhook=webhook_name))
            return

    @twitch.command(name="list")
    @commands.has_permissions(administrator=True)
    async def get_accounts_tracked(self, context, webhook_name=None):
        """
        Shows the accounts tracked and their custom message in the given Webhook, or every Webhook if no Webhook is given.
        :param context: The context of the command.
        :param webhook_name: The name of the webhook to get the accounts of.
        """
        if webhook_name:
            # Get the accounts for a specific Webhook.
            webhook_id, webhook_info = get_webhook_by_name(
                    self._twitch_app.hooks,
                    webhook_name,
                    context.guild.id, WEBHOOK_PREFIX
            )
            embed = self.get_webhook_channels_as_embed(webhook_id, webhook_info.get("name"))
            await context.send(embed=embed)
            return

        # Get the accounts for all the Webhooks.
        for hook in self._twitch_app.hooks:
            embed = self.get_webhook_channels_as_embed(hook, self._twitch_app.hooks.get(hook).get("name"))
            await context.send(embed=embed)

    @twitch.command(name="webhooks")
    @commands.has_permissions(administrator=True)
    async def get_current_webhooks(self, context):
        """
        Gets a list of the current Webhooks for the Twitch Cog in the given guild.
        :param context: The context of the command.
        """
        guild_hooks = list(
            filter(lambda x: self._twitch_app.hooks.get(x).get("guild_id") == context.guild.id,
                   self._twitch_app.hooks)
        )
        if not guild_hooks:
            await context.send(self.user_strings["no_webhooks"])
            return
        string = ", ".join(self._twitch_app.hooks.get(x).get("name") for x in guild_hooks)
        await context.send(self.user_strings["current_webhooks"].format(webhooks=string, prefix=WEBHOOK_PREFIX))

    @twitch.command(name="setmessage")
    @commands.has_permissions(administrator=True)
    async def set_channel_message(self, context, channel, webhook_name, custom_message=None):
        """
        Sets the custom message for a Twitch channel for the given Webhook.
        If the message is left empty, it deletes the custom message.
        :param context: The context of the command.
        :param channel: The channel to set the custom message of.
        :param webhook_name: The name of the Webhook to set the message in.
        :param custom_message: The custom message to set.
        """
        channel_id = await self.get_channel_id_from_command(channel)
        webhook_id, webhook_info = get_webhook_by_name(self._twitch_app.hooks, webhook_name, context.guild.id, WEBHOOK_PREFIX)

        if not channel_id:
            await context.send(self.user_strings["channel_missing_error"].format(channel=channel))
            return

        if not webhook_name:
            await context.send(self.user_strings["webhook_missing"].format(name=webhook_name))
            return

        if channel_id in self._twitch_app.tracked_channels:
            # The given Twitch Channel is tracked by one or more Webhooks.
            if webhook_id not in self._twitch_app.tracked_channels.get(channel_id):
                # The given Twitch Channel is not tracked in the given Webhook.
                await context.send(self.user_strings["channel_not_tracked"].format(name=channel, webhook=webhook_name))
                return
            self._twitch_app.tracked_channels[channel_id][webhook_id] = custom_message
            db_item = self._db.get(Twitch_info, guild_id=context.guild.id, channel_id=channel_id, hook_id=webhook_id)
            if db_item:
                db_item.custom_message = custom_message
                self._db.update(db_item)
            if not custom_message:
                custom_message = "<empty>"
            await context.send(
                self.user_strings["set_custom_message"].format(channel=channel,
                                                               message=custom_message,
                                                               webhook=webhook_name)
            )
        else:
            await context.send(self.user_strings["channel_not_tracked"].format(name=channel, webhook=webhook_name))
            return

    @twitch.command(name="getmessage")
    async def get_channel_message(self, context, channel, webhook_name=None):
        """
        Gets the custom channel message for a Webhook. If no Webhook name is given, get all the custom messages.
        :param context: The context of the command.
        :param channel: The channel to get the custom messages of.
        :param webhook_name: The Webhook to get the custom message of.
        """
        channel_id = await self.get_channel_id_from_command(channel)

        if channel_id not in self._twitch_app.tracked_channels:
            # The requested channel is not tracked.
            await context.send(self.user_strings["no_channel_error"].format(channel=channel))
            return

        if webhook_name:
            webhook_id, webhook_info = get_webhook_by_name(
                self._twitch_app.hooks,
                webhook_name,
                context.guild.id,
                WEBHOOK_PREFIX
            )
            custom_message = self._twitch_app.tracked_channels.get(channel_id).get(webhook_id)
            if not custom_message:
                custom_message = "<empty>"
            await context.send(
                self.user_strings["get_custom_message"].format(channel=channel,
                                                               webhook=webhook_name,
                                                               message=custom_message)
            )
            return

        string = f"The custom messages for the channel `{channel}` are: \n"
        for webhook_id in self._twitch_app.tracked_channels.get(channel_id):
            message = self._twitch_app.tracked_channels.get(channel_id).get(webhook_id)
            if not message:
                message = "<empty>"
            next_string = f"`{self._twitch_app.hooks.get(webhook_id).get('name')}` : '{message}'"
            string += next_string + "\n"

        await context.send(string)

    @twitch.command(name="preview")
    async def get_channel_preview(self, context, channel, webhook_name):
        """
        Gets a preview embed for a given Twitch channel in a given Webhook.
        :param context: The context of the command.
        :param channel: The channel to preview.
        :param webhook_name: The name of the Webhook to get the preview of.
        """
        channel_info = await self._twitch_app.get_channel_info(channel_name=channel)

        if not channel_info:
            await context.send(self.user_strings["no_channel_error"].format(channel=channel))
            return

        channel_info = channel_info[0]
        channel_id = channel_info.get("id")
        webhook_id, webhook_info = get_webhook_by_name(self._twitch_app.hooks, webhook_name, context.guild.id, WEBHOOK_PREFIX)

        if not channel_id:
            await context.send(self.user_strings["channel_missing_error"].format(channel=channel))
            return

        if not webhook_name:
            await context.send(self.user_strings["webhook_missing"].format(name=webhook_name))
            return

        if channel_id not in self._twitch_app.tracked_channels:
            # The given channel is not tracked.
            await context.send(self.user_strings["channel_not_tracked"].format(name=channel, webhook=webhook_name))
            return

        if webhook_id not in self._twitch_app.tracked_channels.get(channel_id):
            # The given Twitch Channel is not tracked in the given Webhook.
            await context.send(self.user_strings["channel_not_tracked"].format(name=channel, webhook=webhook_name))
            return

        custom_message = self._twitch_app.tracked_channels.get(channel_id).get(webhook_id)
        if not custom_message:
            custom_message = "​"

        embed = Embed(
            title=channel_info.get("title"),
            url=f"{TWITCH_BASE}/{channel_info.get('broadcaster_login')}",
            description=f"**{custom_message}**",
            color=TWITCH_EMBED_COLOUR
        )
        embed.set_author(
            name=channel_info.get("broadcaster_login"),
            url=f"{TWITCH_BASE}/{channel_info.get('broadcaster_login')}",
            icon_url=channel_info.get("thumbnail_url")
        )
        embed.set_thumbnail(url=channel_info.get("thumbnail_url"))
        embed.add_field(name="Current Game:", value=f"{channel_info.get('game_name')}")

        await context.send(embed=embed)


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
