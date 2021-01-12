from discord.ext import tasks, commands
from db_gateway import db_gateway
import snscrape.modules.twitter as sntwitter

class TwitterIntegrationCog(commands.Cog):


    def __init__(self, bot):
        self.bot = bot
        self.tweet_checker.start()


    async def send_to_log_channel(self, guild_id, msg):
        db_logging_call = db_gateway().get('guild_info', params={'guild_id': guild_id})
        if db_logging_call:
            await self.bot.get_channel(db_logging_call[0]['log_channel_id']).send(msg)


    def cog_unload(self):
        self.tweet_checker.cancel()


    @commands.command()
    @commands.has_permissions(administrator=True)
    async def addtwitter(self, ctx, twitter_handle=None, announce_channel=None):
        if twitter_handle is not None:
            if (twitter_handle.replace('_', '')).isalnum():
                await ctx.channel.send(f"{twitter_handle} is valid")
            else:
                await ctx.channel.send("You need to provide a correct Twitter handle")
        else:
            await ctx.channel.send("You need to provide a Twitter handle")
        

    def get_tweets(self, given_username, tweet_number=1):
        # Using TwitterSearchScraper to scrape data and append tweets to list
        tweets_list = list()
        for index, tweet_data in enumerate(sntwitter.TwitterSearchScraper(f'from:{given_username}').get_items()):
            #tweet_is_reply = True if tweet_data.content[0] == '@' else False
            if tweet_data.content[0] != '@':
                    tweets_list.append({'id': tweet_data.id, 'content': tweet_data.content, 'link': str(tweet_data)})
            if len(tweets_list) == tweet_number:
                break
        return tweets_list


    # https://discordpy.readthedocs.io/en/latest/ext/tasks/
    @tasks.loop(seconds=10)
    async def tweet_checker(self):
        print("Looped")
        for each in self.get_tweets("fragsoc", 1):
            print(each)


    @tweet_checker.before_loop
    async def before_tweet_checker(self):
        print('waiting...')
        await self.bot.wait_until_ready()

    
def setup(bot):
    bot.add_cog(TwitterIntegrationCog(bot))