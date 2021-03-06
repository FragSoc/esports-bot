from discord.ext import tasks, commands
from db_gateway import db_gateway
from base_functions import get_cleaned_id
import snscrape.modules.twitter as sntwitter
import time


class TwitterIntegrationCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.tweet_checker.start()

    def cog_unload(self):
        self.tweet_checker.cancel()

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def addtwitter(self, ctx, twitter_handle=None, announce_channel=None):
        if twitter_handle is not None and announce_channel is not None:
            if (twitter_handle.replace('_', '')).isalnum():
                twitter_in_db = db_gateway().get('twitter_info', params={
                    'guild_id': ctx.author.guild.id, 'twitter_handle': twitter_handle.lower()})
                if not bool(twitter_in_db):
                    cleaned_channel_id = get_cleaned_id(announce_channel)
                    channel_mention = self.bot.get_channel(
                        cleaned_channel_id).mention
                    previous_tweet_id = self.get_tweets(
                        twitter_handle)[0]['id']
                    db_gateway().insert('twitter_info', params={
                        'guild_id': ctx.author.guild.id, 'channel_id': cleaned_channel_id, 'twitter_handle': twitter_handle, 'previous_tweet_id': previous_tweet_id})
                    await ctx.channel.send(f"{twitter_handle} is valid and has been added, their Tweets will be placed in {channel_mention}")
                else:
                    await ctx.channel.send(f"{twitter_handle} is already configured to output to {self.bot.get_channel(int(twitter_in_db['channel_id'])).mention}")
            else:
                await ctx.channel.send("You need to provide a correct Twitter handle")
        else:
            await ctx.channel.send("You need to provide a Twitter handle and a channel")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def removetwitter(self, ctx, twitter_handle=None):
        if twitter_handle is not None:
            if (twitter_handle.replace('_', '')).isalnum():
                twitter_in_db = db_gateway().get('twitter_info', params={
                    'guild_id': ctx.author.guild.id, 'twitter_handle': twitter_handle.lower()})
                if bool(twitter_in_db):
                    db_gateway().delete('twitter_info', where_params={
                        'guild_id': ctx.author.guild.id, 'twitter_handle': twitter_handle})
                    await ctx.channel.send(f"Removed alerts for @{twitter_handle}")
                else:
                    await ctx.channel.send(f"No alerts set for @{twitter_handle}")
            else:
                await ctx.channel.send("You need to provide a correct Twitter handle")
        else:
            await ctx.channel.send("You need to provide a Twitter handle")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def changetwitterchannel(self, ctx, twitter_handle=None, announce_channel=None):
        if twitter_handle is not None and announce_channel is not None:
            if (twitter_handle.replace('_', '')).isalnum():
                twitter_in_db = db_gateway().get('twitter_info', params={
                    'guild_id': ctx.author.guild.id, 'twitter_handle': twitter_handle.lower()})
                if bool(twitter_in_db):
                    # In DB
                    cleaned_channel_id = get_cleaned_id(announce_channel)
                    channel_mention = self.bot.get_channel(
                        cleaned_channel_id).mention
                    db_gateway().update('twitter_info', set_params={'channel_id': cleaned_channel_id}, where_params={
                        'guild_id': ctx.author.guild.id, 'twitter_handle': twitter_handle})
                    await ctx.channel.send(f"{twitter_handle} has been updated and will now notify in {channel_mention}")
                else:
                    # Not set up
                    await ctx.channel.send(f"{twitter_handle} is not configured in this server")
            else:
                await ctx.channel.send("You need to provide a correct Twitter handle")
        else:
            await ctx.channel.send("You need to provide a Twitter handle and a channel")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def getalltwitters(self, ctx):
        all_guild_twitters = db_gateway().get(
            'twitter_info', params={'guild_id': ctx.author.guild.id})
        if all_guild_twitters:
            all_twitters_str = str()
            for twitter in all_guild_twitters:
                all_twitters_str += f"{twitter['twitter_handle']} is set to notify in {self.bot.get_channel(twitter['channel_id']).mention}\n"
            await ctx.channel.send(f"Current Twitters set in this server:\n{all_twitters_str}")
        else:
            await ctx.channel.send("No Twitters have currently been set in this server")

    def get_tweets(self, given_username, tweet_number=1):
        # Using TwitterSearchScraper to scrape data and append tweets to list
        tweets_list = list()
        for index, tweet_data in enumerate(sntwitter.TwitterSearchScraper(f'from:{given_username}').get_items()):
            #tweet_is_reply = True if tweet_data.content[0] == '@' else False
            if tweet_data.content[0] != '@':
                tweets_list.append(
                    {'id': tweet_data.id, 'content': tweet_data.content, 'link': str(tweet_data)})
            if len(tweets_list) == tweet_number:
                break
        return tweets_list

    # https://discordpy.readthedocs.io/en/latest/ext/tasks/

    @tasks.loop(seconds=50)
    async def tweet_checker(self):
        start_time = time.time()
        print("** Checking all saved handles **")
        returned_val = db_gateway().getall('twitter_info')
        for each in returned_val:
            single_tweet = self.get_tweets(each['twitter_handle'], 1)
            if single_tweet[0]['id'] == each['previous_tweet_id']:
                print(f"{each['twitter_handle']} - Same")
            else:
                print(f"{each['twitter_handle']} - Different")
                await self.bot.get_channel(each['channel_id']).send(f"@{each['twitter_handle']} has just tweeted! Link - {single_tweet[0]['link']}")
                db_gateway().update('twitter_info', set_params={'previous_tweet_id': int(single_tweet[0]['id'])}, where_params={
                    'guild_id': each['guild_id'], 'twitter_handle': each['twitter_handle']})
        end_time = time.time()
        print(f'Checking tweets took: {round(end_time-start_time, 3)}s')

    @tweet_checker.before_loop
    async def before_tweet_checker(self):
        print('Updating tweets in DB')
        returned_val = db_gateway().getall('twitter_info')
        for each in returned_val:
            single_tweet = self.get_tweets(each['twitter_handle'], 1)
            db_gateway().update('twitter_info', set_params={'previous_tweet_id': int(single_tweet[0]['id'])}, where_params={
                'guild_id': each['guild_id'], 'twitter_handle': each['twitter_handle']})
        print('Waiting on bot to become ready before start Twitter cog')
        await self.bot.wait_until_ready()


def setup(bot):
    bot.add_cog(TwitterIntegrationCog(bot))
