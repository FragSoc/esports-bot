from discord.ext import commands
from db_gateway import db_gateway

class LoggingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def send_to_log_channel(self, guild_id, msg):
    db_logging_call = db_gateway().get('guild_info', params={'guild_id': guild_id})
    if db_logging_call:
        await client.get_channel(db_logging_call[0]['log_channel_id']).send(msg)
    
def setup(bot):
    bot.add_cog(LoggingCog(bot))