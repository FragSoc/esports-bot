import hashlib
import hmac
import os

import tornado.httpserver
import tornado.web

import ast

SUBSCRIPTION_SECRET = os.getenv("TWITCH_SUB_SECRET")


class TwitchListener(tornado.web.RequestHandler):
    async def post(self):
        current_request = self.request
        message_body = current_request.body.decode("utf-8")
        body_dict = ast.literal_eval(message_body)
        message_headers = current_request.headers
        query_args = current_request.query_arguments

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
            self.set_status(403)
            await self.finish()
            return

        if message_headers.get("Twitch-Eventsub-Message-Type") == "webhook_callback_verification":
            # POST request is to verify if we own the requested notification.
            # Twitch wants us to return the challenge as a raw string to verify:
            challenge = body_dict.get("challenge")
            await self.finish(challenge)

        elif message_headers.get("Twitch-Eventsub-Message-Type") == "notification":
            # POST request was a notification
            self.set_status(200)
            # TODO: Act upon the received message.
