import asyncio
import json
from collections import defaultdict
from datetime import datetime
import hashlib
import hmac
import os
from typing import Any, List

import aiohttp
import coloredlogs
import dotenv
from discord import Webhook, Embed, AsyncWebhookAdapter
from tornado.httpserver import HTTPServer
import tornado.web

import ast

from discord.ext import commands
from tornado import httputil
from tornado.ioloop import IOLoop
from tornado.web import Application

import logging

from src.esportsbot.db_gateway import db_gateway

SUBSCRIPTION_SECRET = os.getenv("TWITCH_SUB_SECRET")
CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
WEBHOOK_PREFIX = "TwitchHook-"
BEARER_PADDING = 2 * 60  # Number of minutes before expiration of bearer where the same bearer will still be used.
DATETIME_FMT = "%d/%m/%y %H:%M:%S"
TWITCH_EMBED_COLOUR = 0x6441a4
CALLBACK_URL = ""  # The URL to be used as for the event callback.
DEFAULT_HOOK_NAME = "DefaultTwitchHook"


class TwitchApp(Application):
    """
    This TwitchApp is the application which the TwitchListener is serving and handling requests for.
    Mainly used to store data that is used across requests, as well as handling any API requests that need to be made.
    """

    def __init__(self, handlers=None, default_host=None, transforms=None, **settings: Any):
        super().__init__(handlers, default_host, transforms, **settings)
        self.seen_ids = []
        self.hooks = {}
        self.bearer = None
        self.tracked_channels = defaultdict(set)
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

        self.logger.debug("Checking bearer token status...")
        current_time = datetime.now()
        if self.bearer is not None:
            # If there is a currently active bearer, check if it is still valid.
            grant_time = datetime.strptime(self.bearer.get("granted_on"), DATETIME_FMT)
            time_delta = current_time - grant_time
            delta_seconds = time_delta.total_seconds()
            expires_in = self.bearer.get("expires_in")  # Number of seconds the token is valid for.
            if delta_seconds + BEARER_PADDING < expires_in:
                # The bearer is still valid, and will be still valid for the BEARER_PADDING time.
                self.logger.info(
                    "Current bearer is still valid, there are %d seconds remaining!",
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
        self.bearer = bearer

    async def load_tracked_channels(self, db_channels):
        """
        From the channel data gathered from the database, check that each of them are being tracked by a subscription and
        removes any old subscriptions that are no longer being tracked and sets the tracked_channels attribute to db_channels
        :param db_channels: The dictionary of channel IDs to set of guild IDs
        """

        # Get the list of events we are subscribed to from Twitch's end.
        subscribed_events = await self.get_subscribed_events()
        channels_not_tracked = list(db_channels.keys())

        # Ensure that the events that are tracked by Twitch are still ones we want to track:
        for event in subscribed_events:
            if event.get("type") != "streams.online":
                # Event isn't for a stream coming online, we don't want to track any other events so delete it...
                await self.delete_subscription(event.get("id"))
                continue
            channel_tracked = event.get("condition").get("broadcaster_user_id")

            if channel_tracked not in db_channels:
                # The channel is no longer tracked in the DB, assume we no longer want to track the channel so delete it...
                await self.delete_subscription(event.get("id"))
            else:
                channels_not_tracked.pop(channel_tracked)

        # Any channels here are ones that we want to have tracked but there is no event we are subscribed to for it.
        for channel in channels_not_tracked:
            self.logger.warning("No event for channel %s, subscribing to new event...", channel)
            await self.create_subscription("stream.online", channel_id=channel)

        self.tracked_channels = db_channels

    async def delete_subscription(self, event_id):
        """
        Deletes a Twitch Event Subscription given the Event's ID
        :param event_id: The ID of the event to delete.
        """

        delete_url = "https://api.twitch.tv/helix/eventsub/subscriptions"
        params = {"id": event_id}
        bearer_info = await self.get_bearer()
        headers = {"Client-ID": CLIENT_ID, "Authorization": "Bearer " + bearer_info.get("access_token")}

        async with aiohttp.ClientSession() as session:
            async with session.delete(url=delete_url, params=params, headers=headers) as response:
                return response.status == 204

    async def create_subscription(self, event_type, channel_id=None, channel_name=None):
        """
        Creates a new Event Subscription for a given channel ID for a given Event Type.
        :param event_type: The Event to subscribe to.
        :param channel_id: The ID of the channel.
        :param channel_name: The name of the channel.
        """

        if channel_id is None and channel_name is None:
            self.logger.error("An channel ID or channel name must be supplied. Both cannot be None.")
            return

        if channel_id is None:
            # Get the channel ID from the channel name
            channel_info = await self.get_channel_info(channel_name)
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
            async with session.post(url=subscription_url, body=body_json, headers=headers) as response:
                return response.status == 200

    async def get_channel_info(self, channel_name):
        """
        Returns the information about the given channel using its name as the lookup parameter.
        :param channel_name: The name of the channel.
        :return:
        """

        channel_url = "https://api.twitch.tv/helix/search/channels"
        params = {"query": channel_name}
        bearer_info = await self.get_bearer()
        headers = {"client-id": CLIENT_ID, "Authorization": "Bearer" + bearer_info.get("access_token")}

        async with aiohttp.ClientSession() as session:
            async with session.get(url=channel_url, params=params, headers=headers) as response:
                if response.status != 200:
                    self.logger.error("Unable to get channel info!")
                    return None
                data = await response.json()
                return data.get("data")[0]

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
                    self.logger.error("Unable to get subscribed event list!")
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
        :return: True if the signature provided in the header is the same as the caluclated signature.
        """

        message_signature = headers.get("Twitch-Eventsub-Message-Signature")
        hmac_message = headers.get("Twitch-Eventsub-Message-Id") + headers.get("Twitch-Eventsub-Message-Timestamp") + body
        hmac_message_bytes = bytes(hmac_message, "utf-8")
        secret_bytes = bytes(SUBSCRIPTION_SECRET, "utf-8")

        calculated_signature = hmac.new(secret_bytes, hmac_message_bytes, hashlib.sha256)
        expected_signature = "sha256=" + calculated_signature.hexdigest()

        if expected_signature != message_signature:
            return False
        return True

    async def post(self):
        """
        When a POST request is received by this web listener, this method is called to determine what to do with the
        incoming request. The general structure to this method can be found in the Twitch documentation:
        https://dev.twitch.tv/docs/eventsub#subscriptions.
        """

        self.logger.info("Received a POST request on /webhook")
        current_request = self.request
        message_body = current_request.body.decode("utf-8")
        body_dict = ast.literal_eval(message_body)
        message_headers = current_request.headers

        # Check for messages that have already been received and processed. Twitch will repeat a mesage if it
        # thinks we have not received it.
        if message_headers.get("Twitch-Eventsub-Message-Id") in self.application.seen_ids:
            self.logger.info("The message was already received before, ignoring!")
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
            # Received shortly after creating a new EventSub
            challenge = body_dict.get("challenge")
            self.logger.info("Responding to Webhook Verification Callback with challenge: %s", challenge)
            await self.finish(challenge)
        elif message_headers.get("Twitch-Eventsub-Message-Type") == "notification":
            # Receieved once a subscribed event occurs.
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

        # Create the embed to send to the webhook
        embed = Embed(
            title=stream_title,
            url=f"https://www.twitch.tv/{channel_name}",
            description=f"Playing {game_name}",
            color=TWITCH_EMBED_COLOUR
        )
        embed.set_author(
            name=channel_name,
            url=f"https://www.twitch.tv/{channel_name}",
            icon_url="https://assets.help.twitch.tv/Glitch_Purple_RGB.png"
        )
        embed.set_thumbnail(url=user_icon)

        channel_guilds = self.application.tracked_channels.get(channel_info.get("id"))

        async with aiohttp.ClientSession() as session:
            hook_adapter = AsyncWebhookAdapter(session)
            for hook_id in self.application.hooks:
                if self.application.hooks.get(hook_id).get("guild_id") not in channel_guilds:
                    continue

                hook_token = self.application.hooks.get(hook_id).get("token")
                webhook = Webhook.partial(id=hook_id, token=hook_token, adapter=hook_adapter)
                self.logger.info("Sending to Webhook %s(%s)", self.application.hooks.get(hook_id).get("name"), hook_id)
                await webhook.send(embed=embed, username=channel_name + " is Live!", avatar_url=user_icon)
