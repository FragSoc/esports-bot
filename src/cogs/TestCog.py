from discord.ext import commands

class TestCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def test(self, ctx):
        print("TEST endpoint hit")

    
def setup(bot):
    bot.add_cog(TestCog(bot))