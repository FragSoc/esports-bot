from discord import Embed, Colour
from discord.ext.commands import HelpCommand, MissingPermissions

from esportsbot.DiscordReactableMenus.EmojiHandler import MultiEmoji
from esportsbot.DiscordReactableMenus.ReactableMenu import ReactableMenu


class CustomHelpCommand(HelpCommand):
    def __init__(self, **options):
        self.help_strings = options.pop("help_strings")
        super().__init__(**options)

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
        embed = Embed(
            title=getattr(cog,
                          "qualified_name",
                          self.help_strings.get("empty_category")),
            description="​",
            colour=Colour.random()
        )
        for command in commands:
            await self.add_command_field(embed, command)

        embed.set_footer(text=self.help_strings.get("embed_footer"))

        return embed

    async def add_command_field(self, embed, command):
        """
        Adds the embed field for a given command to an embed. If the command does not pass the checks, it is not added.
        Eg: Command needs admin but user is not an admin.
        :param embed: THe embed to add the field to.
        :param command: The command to add the help field of.
        """
        if command.hidden and not self.context.author.guild_permissions.administrator:
            return

        checks = command.checks
        checks_to_add = []
        for check in checks:
            # Remove any custom checks. Checks such as admin will not be removed.
            if check.__name__ != "predicate":
                command.remove_check(check)
                checks_to_add.append(check)

        try:
            # For some reason instead of returning False, this will just raise an error if the user is not able to run
            # the command.
            await command.can_run(self.context)
        except MissingPermissions:
            return

        for check in checks_to_add:
            command.add_check(check)

        fully_qualified_name = command.name
        if command.full_parent_name:
            fully_qualified_name = f"{command.full_parent_name} {fully_qualified_name}"

        fully_qualified_name = fully_qualified_name.strip()

        # name = <prefix><fully qualified name>
        # value = Short help string \n Alias String \n Help command string

        help_dict = self.help_strings.get(fully_qualified_name.replace(" ", "_").replace("-", "_"))
        name = self.help_strings["usage_string"].format(prefix=self.clean_prefix, fqn=fully_qualified_name)
        if not help_dict:
            # If the command is missing help string definition in the user_strings file, try and default to the defined
            # help string in the command definition.
            value = ""
            if command.help:
                value += self.help_strings["command_help_short"].format(help_string=command.help) + "\n"
            else:
                value += self.help_strings["command_help_short"].format(
                    help_string=self.help_strings["missing_help_string"]
                ) + "\n"
        else:
            value = self.help_strings["command_help_short"].format(help_string=help_dict["help_string"]) + "\n"

        if command.aliases:
            alias_string = str(command.aliases).replace("]", "").replace("[", "").replace("'", "")
            value += self.help_strings["command_alias"].format(aliases=alias_string) + "\n"
        value += self.help_strings["command_help"].format(prefix=self.clean_prefix, fqn=fully_qualified_name) + "\n"

        value += "​"

        embed.add_field(name=f"**{name}**", value=value, inline=False)

    async def send_command_help(self, command):
        """
        Runs when the help command is run with a parameter that is a command. This can be a subcommand of a group or a
        command that is not in a group.
        :param command: The command to get the help information of.
        """
        fully_qualified_name = command.name
        if command.full_parent_name:
            fully_qualified_name = f"{command.full_parent_name} {fully_qualified_name}"

        fully_qualified_name = fully_qualified_name.strip()

        title = self.help_strings["embed_title"].format(prefix=self.clean_prefix, fqn=fully_qualified_name)
        usage = self.help_strings["usage_string"].format(prefix=self.clean_prefix, fqn=fully_qualified_name)

        help_dict = self.help_strings.get(fully_qualified_name.replace(" ", "_").replace("-", "_"))
        if not help_dict:
            short = command.help if command.help else self.help_strings["missing_help_string"]
            long_string = command.description if command.description else ""
            usage += command.usage if command.usage else ""
        else:
            short = help_dict.get("help_string", self.help_strings["missing_help_string"])
            long_string = help_dict.get("description", "")
            usage += help_dict.get("usage", "")

        description = self.help_strings["command_description"].format(short_string=short, long_string=long_string)

        embed = Embed(title=title, description=description, colour=Colour.random())
        if help_dict and help_dict.get("readme_url"):
            embed.__setattr__("url", help_dict.get("readme_url"))
        embed.add_field(name="Usage:", value=usage, inline=False)
        embed.add_field(name="​", value=self.help_strings["command_footer"])
        embed.set_footer(text=self.help_strings["embed_footer"])

        await self.context.send(embed=embed)

    async def send_group_help(self, group):
        """
        Runs when the help command is run with a parameter that is a command group.
        :param group: The command group to send the help information about.
        """
        fully_qualified_name = group.name
        if group.full_parent_name:
            fully_qualified_name = f"{group.full_parent_name} {fully_qualified_name}"

        fully_qualified_name = fully_qualified_name.strip()

        title = self.help_strings["embed_title"].format(prefix=self.clean_prefix, fqn=fully_qualified_name)
        help_dict = self.help_strings.get(fully_qualified_name.replace(" ", "_").replace("-", "_"))
        if not help_dict:
            description = "​" if not group.help else group.help
        else:
            description = help_dict.get("help_string", "​")

        description += "\n​"
        embed = Embed(title=title, description=description, colour=Colour.random())

        if help_dict and help_dict.get("readme_url"):
            embed.__setattr__("url", help_dict.get("readme_url"))

        for command in group.commands:
            await self.add_command_field(embed, command)

        embed.set_footer(text=self.help_strings["embed_footer"])
        await self.context.send(embed=embed)

    async def send_cog_help(self, cog):
        """
        Send the help for a given cog.
        :param cog: The cog to get the help about.
        """
        await self.context.send(embed=await self.get_cog_help(cog, cog.get_commands()))


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
