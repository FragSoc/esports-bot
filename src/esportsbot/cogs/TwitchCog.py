import asyncio
import hashlib
import hmac
import os
from typing import Any, List

from tornado.httpserver import HTTPServer
import tornado.web

import ast

from discord.ext import commands
from tornado import httputil
from tornado.web import Application

import logging

SUBSCRIPTION_SECRET = os.getenv("TWITCH_SUB_SECRET")
CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
WEBHOOK_PREFIX = "TwitchHook-"


class TwitchApp(Application):
    """
    This TwitchApp is the application which the TwitchListener is serving and handling requests for.
    Mainly used to store data that is used across requests.
    """
    def __init__(self, handlers=None, default_host=None, transforms=None, **settings: Any):
        super().__init__(handlers, default_host, transforms, **settings)
        self.seen_ids = []
        self.hooks = {}

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
        pass
