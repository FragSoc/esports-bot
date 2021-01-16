from discord.ext import commands
import requests
import time
import os
import pprint

class TwitchIntegrationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.twitch_handler = TwitchAPIHandler()

    @commands.command()
    async def test(self, ctx):
        print("TEST endpoint hit")
        twitch_handles = ['lcs', 'fragsoc', 'riotgames']
        print(self.twitch_handler.request_data(twitch_handles))

    
def setup(bot):
    bot.add_cog(TwitchIntegrationCog(bot))


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
            return self.token

    def request_data(self, twitch_handles):
        data_url = 'https://api.twitch.tv/helix/streams?'
        data_url = data_url+"user_login="+("&user_login=".join(twitch_handles))
        print(data_url)
        self.generate_new_oauth()
        data_response = requests.get(data_url, headers=self.base_headers(), params=self.params)
        pprint.pprint(data_response.json())
        return data_response