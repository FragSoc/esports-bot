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
    def __init__(self, handlers=None, default_host=None, transforms=None, **settings: Any):
        super().__init__(handlers, default_host, transforms, **settings)
        self.seen_ids = []
        self.hooks = {}

    def load_discord_hooks(self, guild_hooks: List[List[Webhook]], bot_user_id: int):
        for guild in guild_hooks:
            # For each guild in the list...
            for g_hook in guild:
                # And for each Webhook in the guild...
                if WEBHOOK_PREFIX in g_hook.name and g_hook.user.id == bot_user_id:
                    # Only if the Webhook was created for the TwitterCog and by the bot.
                    self.hooks[g_hook.id] = {"token": g_hook.token, "name": g_hook.name, "guild_id": g_hook.guild_id}


class TwitchListener(tornado.web.RequestHandler):
    def __init__(self, application: "Application", request: httputil.HTTPServerRequest, **kwargs: Any):
        super().__init__(application, request, **kwargs)
        self.logger = logging.getLogger(__name__)
        self._seen_ids = set()
        self._hooks = {}

    async def post(self):
        # The steps taken in the code below are outlined in the Twitch documentation:
        # https://dev.twitch.tv/docs/eventsub#subscriptions
        self.logger.info("Received a POST request on /webhook")
        current_request = self.request
        message_body = current_request.body.decode("utf-8")
        body_dict = ast.literal_eval(message_body)
        message_headers = current_request.headers
        query_args = current_request.query_arguments

        if message_headers.get("Twitch-Eventsub-Message-Id") in self.application.seen_ids:
            # Filter out messages already received. If Twitch thinks we have not received the message Twitch will
            # keep sending data with the same message ID, which we do not want to process again.
            self.logger.info("The message was already received before, ignoring!")
            self.set_status(208)
            await self.finish()
            return
        else:
            self.application.seen_ids.add(message_headers.get("Twitch-Eventsub-Message-Id"))

        # Verify the message came from Twitch
        message_signature = message_headers.get("Twitch-Eventsub-Message-Signature")
        hmac_message = message_headers.get("Twitch-Eventsub-Message-Id") + \
                       message_headers.get("Twitch-Eventsub-Message-Timestamp") + \
                       message_body

        hmac_message_bytes = bytes(hmac_message, "utf-8")
        sub_secret_bytes = bytes(SUBSCRIPTION_SECRET, "utf-8")

        # Calculate the HMAC using our known secret key and the message from Twitch:
        calculated_hmac = hmac.new(sub_secret_bytes, hmac_message_bytes, hashlib.sha256)
        expected_hmac = "sha256=" + calculated_hmac.hexdigest()

        if expected_hmac != message_signature:
            # If the calculated HMAC is not the same as the signature provided in the header, return
            self.logger.error(
                "The message received at %s was not a legitimate message from Twitch, ignoring!",
                message_headers.get("Twitch-Eventsub-Message-Timestamp")
            )
            self.set_status(403)
            await self.finish()
            return

        if message_headers.get("Twitch-Eventsub-Message-Type") == "webhook_callback_verification":
            # POST request is to verify if we own the requested notification.
            # Twitch wants us to return the challenge as a raw string to verify:
            challenge = body_dict.get("challenge")
            self.logger.info("Responding to Webhook Verification Callback with challenge: %s", challenge)
            await self.finish(challenge)

        elif message_headers.get("Twitch-Eventsub-Message-Type") == "notification":
            # POST request was a notification
            self.logger.info("Received valid notification from Twitch!")
            self.set_status(200)
            # TODO: Act upon the received message.
