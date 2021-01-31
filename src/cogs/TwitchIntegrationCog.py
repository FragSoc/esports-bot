from discord.ext import commands, tasks
from db_gateway import db_gateway
from base_functions import get_cleaned_id
import requests
import time
import os
import pprint


class TwitchIntegrationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.twitch_handler = TwitchAPIHandler()
        self.live_checker.start()

    def cog_unload(self):
        self.live_checker.cancel()

    @commands.command()
    async def addtwitch(self, ctx, twitch_handle=None, announce_channel=None):
        if twitch_handle is not None and announce_channel is not None:
            # Check if Twitch channel has already been added
            twitch_in_db = db_gateway().get('twitch_info', params={
                'guild_id': ctx.author.guild.id, 'twitch_handle': twitch_handle})
            cleaned_channel_id = get_cleaned_id(
                announce_channel)
            channel_mention = self.bot.get_channel(
                cleaned_channel_id).mention
            if not twitch_in_db:
                # Check user exists
                user_exists = bool(
                    self.twitch_handler.request_user(twitch_handle))
                if user_exists:
                    # Get live status of the channel
                    live_status = bool(self.twitch_handler.request_data(
                        [twitch_handle]))
                    # Insert Twitch channel into DB
                    db_gateway().insert('twitch_info', params={
                        'guild_id': ctx.author.guild.id, 'channel_id': cleaned_channel_id, 'twitch_handle': twitch_handle.lower(), 'currently_live': live_status})
                    await ctx.channel.send(f"{twitch_handle} is valid and has been added, their notifications will be placed in {channel_mention}")
                else:
                    await ctx.channel.send(f"{twitch_handle} is not a valid Twitch handle")
            else:
                await ctx.channel.send(f"{twitch_handle} is already configured to {channel_mention}")
        else:
            await ctx.channel.send("You need to provide a Twitch handle and a channel")

    @tasks.loop(seconds=50)
    async def live_checker(self):
        start_time = time.time()
        print("LIVE CHECK!")
        # Change to a DISTINCT select on handle?
        all_twitch_handles = db_gateway().getall('twitch_info')
        pprint.pprint(all_twitch_handles)
        twitch_status_arr = dict(
            lambda x: {x['twitch_handle']: x['currently_live']}, all_twitch_handles)
        pprint.pprint(twitch_status_arr)
        # if all_twitch_handles:
        #     # Create list of all twitch handles in the database
        #     twitch_handle_arr = list(
        #         map(lambda x: x['twitch_handle'], all_twitch_handles))
        #     # Query Twitch to receive array of all live users
        #     returned_data = self.twitch_handler.request_data(
        #         twitch_handle_arr)
        #     live_users = list(
        #         map(lambda x: x['user_name'].lower(), returned_data))
        #     # Loop through all users comparing them to the live list
        #     for twitch_handle in twitch_handle_arr:
        #         if twitch_handle in live_users:
        #             # User is live
        #             print(f"{twitch_handle} is LIVE")
        #         else:
        #             # User is not live
        #             print(f"{twitch_handle} is OFFLINE")
        end_time = time.time()
        print(f'Checking tweets took: {round(end_time-start_time, 3)}s')

    @live_checker.before_loop
    async def before_live_checker(self):
        print('TWITCH: Waiting until bot is ready')
        await self.bot.wait_until_ready()


class TwitchAPIHandler:

    def __init__(self):
        self.client_id = os.getenv('TWITCH_CLIENT_ID')
        self.client_secret = os.getenv('TWITCH_CLIENT_SECRET')
        self.params = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'client_credentials'
        }
        self.token = None

    def base_headers(self):
        return {
            'Authorization': f'Bearer {self.token.get("access_token")}',
            'Client-ID': self.client_id
        }

    def generate_new_oauth(self):
        OAuthURL = 'https://id.twitch.tv/oauth2/token'
        params = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'client_credentials'
        }
        oauth_response = requests.post(OAuthURL, params)
        if oauth_response.status_code == 200:
            oauth_response_json = oauth_response.json()
            oauth_response_json['expires_in'] += time.time()
            self.token = oauth_response_json
            print("GENERATED NEW TOKEN!")
            return self.token

    def request_data(self, twitch_handles):
        print(f"Current token: {self.token}")
        if self.token is None or self.token['expires_in'] < time.time():
            self.generate_new_oauth()
        data_url = 'https://api.twitch.tv/helix/streams?'
        data_url = data_url+"user_login="+("&user_login=".join(twitch_handles))
        print(f"DATA URL - {data_url}")
        data_response = requests.get(
            data_url, headers=self.base_headers(), params=self.params)
        return data_response.json()['data']

    def request_user(self, twitch_handle):
        print(f"Current token: {self.token}")
        if self.token is None or self.token['expires_in'] < time.time():
            self.generate_new_oauth()
        data_url = f'https://api.twitch.tv/helix/users?login={twitch_handle}'
        #data_url = data_url+"user_login="+("&user_login=".join(twitch_handles))
        print(f"DATA URL - {data_url}")
        data_response = requests.get(
            data_url, headers=self.base_headers(), params=self.params)
        return data_response.json()['data']


def setup(bot):
    bot.add_cog(TwitchIntegrationCog(bot))
