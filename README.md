# UoY Esport Bot Rewrite

## How to set up an instance of this bot

1. Clone this repository:
```console
$ git clone https://github.com/FragSoc/Esports-Bot-Rewrite.git
```

2. Change into the repo directory:
```console
$ cd Esports-Bot-Rewrite
```

3. Create a `secrets.env` file and edit it in your favourite text editor:
```console
$ vim secrets.env
```

4. Edit the below environment variables:
```console
DISCORD_TOKEN=
TWITCH_CLIENT_ID=
TWITCH_CLIENT_SECRET=
```

<details>
<summary>Optional Variables</summary>

- Provide your bot's command prefix as a string into `COMMAND_PREFIX` (default `!`)
-  Provide either a unicode emoji (string), or the ID of a custom emoji (int), into `UNKNOWN_COMMAND_EMOJI` to set the emoji which is reacted to messages calling unknown commands (default `⁉`)

</details>

5. Run docker-compose:
```console
$ docker-compose up
```

## Current commands
<details>
<summary>Voicemaster</summary>

### Voicemaster

##### !setvmmaster {channel_id}
Make the given ID a Voicemaster master

##### !getvmmasters
Get all the Voicemaster masters in the server

##### !removevmmaster {channel_id}
Remove the given ID as a Voicemaster master

##### !removeallmasters
Remove all Voicemaster masters from the server

##### !killallslaves
Kill all the Voicemaster slave channels in the server

##### !lockvm
Locks the Voicemaster slave you're currently in to the number of current members

##### !unlockvm
Unlocks the Voicemaster slave you're currently in
</details>

<details>
<summary>Default Role</summary>

### Default role

##### !setdefaultrole {@role or role_id}
Set the default role to the @'ed role or given role ID

##### !getdefaultrole
Gets the current default role value

##### !removedefaultrole
Removes the current default role
</details>

<details>
<summary>Log Channel</summary>

### Log Channel

##### !setlogchannel {#channel or channel_id}
Set the log channel to the #'ed channel or given role ID

##### !getlogchannel
Gets the current log channel value

##### !removelogchannel
Removes the current log channel value
</details>

<details>
<summary>Administrator Tools</summary>

### Administrator Tools

##### !clear
Clear the specified number of messages from the current text channel

##### !members
List the current number of members in the server
</details>

<details>
<summary>Twitter Integration</summary>

### Twitter Integration

##### !addtwitter {twitter_handle} {#channel or channel_id}
Add a Twitter handle to notify in the specified channel when they tweet or quote retweet

##### !removetwitter {twitter_handle}
Remove the given Twitter handle from notifications

##### !changetwitterchannel {twitter_handle} {#channel or channel_id}
Change the notify channel for the given Twitter handle

##### !getalltwitters
List all the current Twitter handles configured in the server
</details>

<details>
<summary>Event Channel Management</summary>

### Event Channel Management
Each server can have any number of named event categories, each with a registered signin role menu granting an event specific role.

##### !open-event {event_name}
Set the event's signin channel as visible to the server's shared role.

##### !close-event {event_name}
Set the event's signin channel as invisible, remove the event's role from all users, and reset the event's signin menu.

##### !register-event-category {menu_id} {@role or role_id} {event_name}
Register an existing category and role as an event category, allowing you to use `!open-event` and `!close-event` with it.

##### !create-event-category {event_name}
Create a new event category with a signin menu, general text and voice channels, and an event role. This category will automatically be registered for use with `open-event` and `!close-event`

##### !unregister-event-category {event_name}
Unregister an event category and role, without deleting them from the server.

##### !delete-event-category {event_name}
Delete an event category from the server, including the category, channels and role. You will be asked for confirmation first.

##### !set-event-signin-menu {menu_id} {event_name}
Change the reaction menu to clear during `!close-event`. This will also tell the bot which channel to set visibility for during `!open-event`.

##### !set-shared-role {@role or role_id}
Change the role to deny signin channel visiblity to during `!close-event`. All users should have ths role.

##### !set-event-role {@role or role_id} {event_name}
Change the role to remove from users during `!close-event`.
</details>

<details>
<summary>Reaction Role Menus</summary>

### Reaction Role Menus
Esportsbot now includes a slightly stripped down version of the reaction menus implementation provided by [BASED](https://github.com/Trimatix/BASED).

Making new types of reaction menus is easy - simply extend `reactionMenus.reactionMenu.ReactionMenu`.

To register a menu instance for interaction, use `client.reactionMenus.add(yourMenuInstance)`. For an example of this, see `cogs.MenusCog.admin_cmd_make_role_menu`.

All saveable reaction menus are automatically added and removed from Esportsbot's PostgreSQL database, and will be loaded in again on bot startup. To register your `ReactionMenu` subclass as saveable, use the `reactionMenu.saveableMenu` class decorator. Saveable menus **MUST** provide complete `toDict` and `fromDict` implementations. For examples of this, see `reactionMenus.reactionRoleMenu`.

`ReactionMenu`s store each option in the menu as an instance of a `reactionMenu.ReactionMenuOption` subclass - each `ReactionMenuOption` has its own individual behaviour for when reactions are added and removed. This already provides a huge amount of flexibility, but you can achieve even more with a custom `ReactionMenuOption` subclass. To make your `ReactionMenuOption` saveable, provide complete `toDict` and `fromDict` implementations. For an example of this, see `reactionMenus.reactionRoleMenu.ReactionRoleMenuOption`.

##### !make-role-menu
```
!make-role-menu {title}
{option1 emoji} {@option1 role}
...    ...
```
Create a reaction role menu.

Each option must be on its own new line, as an emoji, followed by a space, followed by a mention of the role to grant.

The `title` is displayed at the top of the meny and is optional, to exclude your title simply give a new line.

##### !add-role-menu-option {menu-id} {emoji} {@role mention}
Add a role to a role menu.

To get the ID of a reaction menu, enable discord's developer mode, right click on the menu, and click Copy ID.

Your emoji must not be in the menu already, adding the same role more than once is allowed.

Give your role to grant/remove as a mention.

##### !del-role-menu-option {menu-id} {emoji}
Remove a role from a role menu.

To get the ID of a reaction menu, enable discord's developer mode, right click on the menu, and click Copy ID.

Your emoji must be an option in the menu.

##### !del-menu {id}
Remove the specified reaction menu. You can also just delete the message, if you have permissions.

To get the ID of a reaction menu, enable discord's developer mode, right click on the menu, and click Copy ID.
</details>
