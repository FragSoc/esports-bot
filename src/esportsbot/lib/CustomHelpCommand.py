from discord import Embed, Colour
from discord.ext.commands import HelpCommand, MissingPermissions

from esportsbot.DiscordReactableMenus.EmojiHandler import MultiEmoji
from esportsbot.DiscordReactableMenus.ReactableMenu import ReactableMenu


class CustomHelpCommand(HelpCommand):
    def __init__(self, **options):
        super().__init__(**options)

    # !help
    async def send_bot_help(self, mapping):
        embeds = []
        for cog, commands in mapping.items():
            embed = await self.get_cog_help(cog, commands)
            if len(embed.fields) > 0:
                embeds.append(embed)

        help_menu = HelpMenu(embeds=embeds)
        await help_menu.finalise_and_send(self.context.bot, self.context.channel)

    async def get_cog_help(self, cog, commands):
        embed = Embed(title=getattr(cog, "qualified_name", "No Category"), description="​", colour=Colour.random())
        for command in commands:
            await self.add_command_field(embed, command)

        embed.set_footer(text="For more help go to https://github.com/FragSoc/esports-bot")

        return embed

    async def add_command_field(self, embed, command):
        checks = command.checks
        for check in checks:
            if check.__name__ != "predicate":
                command.remove_check(check)

        try:
            await command.can_run(self.context)
        except MissingPermissions:
            return

        name = command.name
        if command.full_parent_name:
            name = command.full_parent_name + " " + name

        value = ""
        if command.help:
            value += f"• {command.help}"

        aliases = command.aliases
        if aliases:
            alias_string = str(aliases).replace("]", "").replace("[", "").replace("'", "")
            value += f"\n• Aliases: {alias_string}"

        value += f"\n• Help command: {self.clean_prefix}help {name}\n​"

        embed.add_field(name=f"**{self.clean_prefix}{name}**", value=value, inline=False)

    # !help <command>
    async def send_command_help(self, command):
        name = command.name
        if command.full_parent_name:
            name = f"{command.full_parent_name} {name}"
        title = f"Showing help for — {self.clean_prefix}{name}"
        description = "<No description>" if not command.help else command.help
        embed = Embed(title=title, description=description, colour=Colour.random())
        usage = "<No parameters>" if not command.usage else f"{self.clean_prefix}{name} {command.usage}"
        embed.add_field(name=f"Usage:", value=usage, inline=False)
        embed.add_field(
            name="​",
            value="• Parameters with `<>` around them are required parameters.\n"
            "• Parameters with `[]` are optional parameters.\n"
            "• The brackets are not required when executing the command."
        )
        embed.set_footer(text="For more help go to https://github.com/FragSoc/esports-bot")
        await self.context.send(embed=embed)

    # !help <group>
    async def send_group_help(self, group):
        name = group.name
        if group.full_parent_name:
            name = f"{group.full_parent_name} {name}"
        title = f"Showing help for — {self.clean_prefix}{name}"
        description = "​" if not group.help else f"{group.help}\n​"
        embed = Embed(title=title, description=description, colour=Colour.random())
        for command in group.commands:
            await self.add_command_field(embed, command)
        embed.set_footer(text="For more help go to https://github.com/FragSoc/esports-bot")
        await self.context.send(embed=embed)

    # !help <cog>
    async def send_cog_help(self, cog):
        await self.context.send(embed=self.get_cog_help(cog, cog.get_commands()))


class HelpMenu(ReactableMenu):
    def __init__(self, **kwargs):
        if kwargs.get("add_func") is None:
            kwargs["add_func"] = self.react_add_func
        super().__init__(**kwargs)
        self.embeds = kwargs.get("embeds", None)
        if self.embeds is None:
            raise ValueError("No embeds supplied to the help menu!")

        self.auto_enable = True
        self.show_ids = False
        self.current_index = 0
        self.max_index = len(self.embeds)
        self.add_option("⬅", "-1")
        self.add_option("➡", "+1")
        self.add_option("❌", "exit")

    async def react_add_func(self, payload):
        emoji_triggered = payload.emoji
        channel_id: int = payload.channel_id
        message_id: int = payload.message_id
        guild = self.message.guild

        if emoji_triggered not in self:
            channel = guild.get_channel(channel_id)
            message = await channel.fetch_message(message_id)
            await message.clear_reaction(emoji_triggered)
            return False

        formatted_emoji = MultiEmoji(emoji_triggered)
        option = self.options.get(formatted_emoji.emoji_id).get("descriptor")
        try:
            self.current_index += int(option)
            if self.current_index >= self.max_index:
                self.current_index = 0
            if self.current_index < 0:
                self.current_index = self.max_index - 1

            await self.update_message()
            channel = guild.get_channel(channel_id)
            message = await channel.fetch_message(message_id)
            await message.remove_reaction(emoji_triggered, payload.member)
        except ValueError:
            await self.message.delete()

    def generate_embed(self) -> Embed:
        return self.embeds[self.current_index]
