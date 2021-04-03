import discord
from discord.ext import commands
from discord.ext.commands.context import Context
from discord.ext.commands.context import Context
from ..db_gateway import db_gateway
from ..lib.client import EsportsBot


DEFAULT_PINGABLE_COLOUR = 0x15e012 # green


class PingablesCog(commands.Cog):
    def __init__(self, bot: "EsportsBot"):
        self.bot: "EsportsBot" = bot

    @commands.command(name="add-pingable-role", usage="add-pingable-role <@role>")
    async def cmd_add_pingable_role(self, ctx: Context, *, args: str):
        if len(ctx.message.role_mentions) != 1:
            await ctx.message.reply("please mention one role")
        else:
            role= ctx.message.role_mentions[0]
            db = db_gateway()
            roleData = db.get("pingable_roles", {"role_id": role.id})
            if roleData:
                await ctx.message.reply("that role is already pingable!")
            else:
                db.insert("pingable_roles", {"role_id": role.id, "on_cooldown": False,
                                            "last_ping": -1, "ping_count": 0, "monthly_ping_count": 0,
                                            "creator_id": ctx.author.id, "colour": DEFAULT_PINGABLE_COLOUR})
                db.insert("guild_pingables", {"guild_id": ctx.guild.id, "role_id": role.id})
                if not role.mentionable:
                    await role.edit(mentionable=True, colour=discord.Colour.green(), reason="setting up new pingable role")
                await ctx.message.reply("pingable role setup complete!")


    @commands.command(name="reset-role-ping-cooldown", usage="reset-role-ping-cooldown <@role>")
    async def cmd_reset_role_ping_cooldown(self, ctx: Context, *, args: str):
        if len(ctx.message.role_mentions) != 1:
            await ctx.message.reply("please mention one role")
        else:
            role = ctx.message.role_mentions[0]
            db = db_gateway()
            roleData = db.get("pingable_roles", {"role_id": role.id})
            if not roleData:
                await ctx.message.reply("that role is not pingable!")
            elif not roleData[0]["on_cooldown"]:
                await ctx.message.reply("that role is not on cooldown!")
            else:
                db.update("pingable_roles", {"on_cooldown": False}, {"role_id": role.id})
                if not role.mentionable:
                    await role.edit(mentionable=True, colour=discord.Colour.green(), reason="manual cooldown reset by user " + str(ctx.author.name) + "#" + str(ctx.author.id))
                await ctx.message.reply("role has been made pingable again!")




def setup(bot):
    bot.add_cog(PingablesCog(bot))
