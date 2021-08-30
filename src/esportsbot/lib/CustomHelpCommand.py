from discord import Embed, Colour
from discord.ext.commands import HelpCommand, MissingPermissions

from esportsbot.DiscordReactableMenus.EmojiHandler import MultiEmoji
from esportsbot.DiscordReactableMenus.ReactableMenu import ReactableMenu


class CustomHelpCommand(HelpCommand):

    async def send_bot_help(self, mapping):
        """
        This function runs when the bare `help` command is run without any groups or commands specified.
        :param mapping: The mapping of Cogs -> Union [Command Groups, Commands]
        """
        embeds = []
        # Get an embed for each cog that has more than 1 field. Some cogs may have no fields if the user requesting
        # does not have permissions to use a given command. Eg: Command needs admin permissions and user is not an admin
        for cog, commands in mapping.items():
            embed = await self.get_cog_help(cog, commands)
            if len(embed.fields) > 0:
                embeds.append(embed)

        help_menu = HelpMenu(embeds=embeds)
        await help_menu.finalise_and_send(self.context.bot, self.context.channel)

    async def get_cog_help(self, cog, commands):
        """
        Gets the help embed for a given cog and its commands.
        :param cog: The cog to get the help embed of.
        :param commands: The commands and command groups in the given cog.
        :return: An embed for the cog.
        """
        embed = Embed(title=getattr(cog, "qualified_name", "No Category"), description="​", colour=Colour.random())
        for command in commands:
            await self.add_command_field(embed, command)

        embed.set_footer(text="For more help go to https://github.com/FragSoc/esports-bot")

        return embed

    async def add_command_field(self, embed, command):
        """
        Adds the embed field for a given command to an embed. If the command does not pass the checks, it is not added.
        Eg: Command needs admin but user is not an admin.
        :param embed: THe embed to add the field to.
        :param command: The command to add the help field of.
        """
        checks = command.checks
        for check in checks:
            # Remove any custom checks. Checks such as admin will not be removed.
            if check.__name__ != "predicate":
                command.remove_check(check)

        try:
            # For some reason instead of returning False, this will just raise an error if the user is not able to run
            # the command.
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

    async def send_command_help(self, command):
        """
        Runs when the help command is run with a parameter that is a command. This can be a subcommand of a group or a
        command that is not in a group.
        :param command: The command to get the help information of.
        """
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

    async def send_group_help(self, group):
        """
        Runs when the help command is run with a parameter that is a command group.
        :param group: The command group to send the help information about.
        """
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

    async def send_cog_help(self, cog):
        """
        Send the help for a given cog.
        :param cog: The cog to get the help about.
        """
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
        """
        The function to run when the help menu is reacted to.
        :param payload: The payload information of the reaction event.
        """
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
            # Bit scuffed, but if the conversion to an int fails, the "exit" option was chosen and therefore just delete
            # the help menu.
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
