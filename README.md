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
<summary>Reaction Role Menus</summary>

### Reaction Role Menus
Esportsbot now includes a slightly stripped down version of the reaction menus implementation provided by [BASED](https://github.com/Trimatix/BASED).

Making new types of reaction menus is easy - simply extend `reactionMenus.reactionMenu.ReactionMenu`.

To register a menu instance for interaction, use `lib.client.reactionMenus.add(yourMenuInstance)`. For an example of this, see `cogs.MenusCog.admin_cmd_make_role_menu`.

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

<details>
<summary>Music Bot</summary>

### Music Bot

The Esports bot now has a basic music bot that functions very similarly to the popular 'Hydra Bot'.

Commands that control the music must be performed in the defined music channel. They also require you to be in the same
voice channel as the bot, so that only the people listening can change the flow of music.

To add new songs to the queue, just put the name, youtube link, or a youtube playlist into the music channel once set.
Also requires you to be in the voice channel with the bot, or if the bot is inactive, in any voice channel.

#### !setmusicchannel <optional: {args}> {channel-id}

* Set the channel to be used for requesting music. Once set the channel will be cleared of any past messages, and the
preview messages will be sent. Any messages sent to this channel get deleted after being processed.
* If the channel being set has past messages, use the `-c` arg to indicate that the channel can be cleared and then set.
* *__Does not need to be sent in the music channel__*


#### !getmusicchannel
* Returns the current channel set as the music channel as a mentioned channel with a `#`.
* *__Does not need to be sent in the music channel__*

#### !resetmusicchannel
* This clears the current music channel and resets the preview and queue messages.
* *__Does not need to be sent in the music channel__*

#### !removesong {index}
* Removes a song from the queue at the given index.

#### !resumesong
* Resumes the current song. Only works if paused.

#### !kickbot
* Kicks the bot from the current call. Will also clear the queue

#### !skipsong
* Skips the current song. If the current song is the only song in the playlist, the bot will leave.

#### !listqueue
* Shows the current queue. Has the same output as the current queue in the music channel
* *__Can't be sent in the music channel__*

#### !clearqueue
* Clears the current queue

#### !shufflequeue
* If the queue has 3 or more items, including the current song, it will shuffle all but the current songs. 

</details>
