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
            twitch_in_db = db_gateway().get('twitch_info', params={
                'guild_id': ctx.author.guild.id, 'twitch_handle': twitch_handle})
            if not bool(twitch_in_db):
                cleaned_channel_id = get_cleaned_id(announce_channel)
                channel_mention = self.bot.get_channel(
                    cleaned_channel_id).mention
                db_gateway().insert('twitch_info', params={
                    'guild_id': ctx.author.guild.id, 'channel_id': cleaned_channel_id, 'twitch_handle': twitch_handle, 'currently_live': False})
                await ctx.channel.send(f"{twitch_handle} is valid and has been added, their notifications will be placed in {channel_mention}")
            else:
                await ctx.channel.send(f"{twitch_handle} is already configured")
        else:
            await ctx.channel.send("You need to provide a Twitch handle and a channel")

    @commands.command()
    async def test(self, ctx, twitch_handle=None):
        start_time = time.time()
        if twitch_handle is not None:
            print(self.twitch_handler.request_data([twitch_handle]))
        else:
            await ctx.channel.send("You need to provide a Twitch handle")
        end_time = time.time()
        print(f'Checking tweets took: {round(end_time-start_time, 3)}s')

    @tasks.loop(seconds=50)
    async def live_checker(self):
        start_time = time.time()
        print("LIVE CHECK!")
        all_twitch_handles = db_gateway().getall('twitch_info')
        if all_twitch_handles:
            twitch_handle_arr = list(
                map(lambda x: x['twitch_handle'], all_twitch_handles))
            twitch_handle_arr.append('esl_csgo')
            twitch_handle_arr.append('zangetsushi')
            returned_data = self.twitch_handler.request_data(
                twitch_handle_arr).json()
            pprint.pprint(returned_data['data'])
            live_users = list(
                map(lambda x: x['user_name'].lower(), returned_data['data']))
            pprint.pprint(live_users)
            for each in twitch_handle_arr:
                if each in live_users:
                    print(f"{each} is LIVE")
                else:
                    print(f"{each} is OFFLINE")
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
        data_response = requests.get(
            data_url, headers=self.base_headers(), params=self.params)
        return data_response


def setup(bot):
    bot.add_cog(TwitchIntegrationCog(bot))
