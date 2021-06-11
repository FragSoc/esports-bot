# UoY Esport Bot Rewrite

<a href="https://travis-ci.com/FragSoc/esports-bot"><img src="https://img.shields.io/travis/com/fragsoc/esports-bot?style=flat-square" /></a>
<a href="https://hub.docker.com/r/fragsoc/esports-bot"><img src="https://img.shields.io/docker/pulls/fragsoc/esports-bot?style=flat-square" /></a>
<a href="https://github.com/FragSoc/esports-bot"><img src="https://img.shields.io/github/license/fragsoc/esports-bot?style=flat-square" /></a>

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
GOOGLE_API=
ENABLE_MUSIC=TRUE
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

### Without Docker

If you don't want to or cannot use docker, you can run the bot outside of docker.
You will need:

- Python 3
- Pip
- Your `secrets.env` file setup as above, or the env vars within set in your environment
- [A postgres database](https://www.postgresql.org/docs/current/admin.html).
  You must set the `PG_HOST`, `PG_USER`, `PG_PWD` and `PG_DATABASE` environment variables according to your postgres setup.

```bash
pip install -r requirements.txt
source secrets.env
python3 src/main.py
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
<summary>Pingme: User-Created Roles With Ping Cooldown</summary>

### Pingme: User-Created Roles With Ping Cooldown
Users can start a vote to create a new role. If enough votes are reached, a new role is created. The role can be pinged by anyone, but is placed on cooldown afterwards.

To help administrators manage the number of roles, a usage report is sent to the server's logging channel on a monthly basis.

##### !pingme register {@role or role_id} {role_name}
Admin command: Register a new role for use with `!pingme`, with the given name. This does not have to be the same as the role's name.

##### !pingme unregister {@role or role_id}
Admin command: Unregister a role from use with `!pingme`, without deleting the role from the server.

##### !pingme delete {@role or role_id}
Admin command: Unregister a `!pingme` role from the role from the server.

##### !pingme reset-cooldown {@role or role_id}
Admin command: Reset the pinging cooldown for a `!pingme` role, making it pingable again instantly.

##### !pingme set-cooldown [seconds=...] [minutes=...] [hours=...] [days=...]
Admin command: Set the cooldown between `!pingme` role pings.

##### !pingme set-create-threshold {num_votes}
Admin command: Set minimum number of votes required to create a new role during `!pingme create`.

##### !pingme set-create-poll-length [seconds=...] [minutes=...] [hours=...] [days=...]
Admin command: Set the amount of time which `!pingme create` polls run for.

##### !pingme set-role-emoji {emoji}
Admin command: Set the emoji which appears before the names of `!pingme` roles. Must be a built in emoji, not custom.

##### !pingme remove-role-emoji
Admin command: Remove the emoji which appears before the names of `!pingme` roles.

##### !pingme create {role_name}
User command: Start a poll for the creation of a new `!pingme` role.

##### !pingme for {role_name}
User command: Get yourself a `!pingme` role, to be notified about events and games.

##### !pingme list
User command: List all available `!pingme` roles.

##### !pingme clear
User command: Unsubscribe from all `!pingme` roles, if you have any.
</details>


<details>
<summary>Event Channel Management</summary>

### Event Category Management
Each server can have any number of named event categories, each with a registered signin role menu granting an event specific role. All commands in this cog are administrator commands.

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
<summary>Twitch Integration</summary>

### Twitch Integration

##### !addtwitch {twitch_handle} {#channel or channel_id}
Add a Twitch handle to notify in the specified channel when they go live

##### !addcustomtwitch {twitch_handle} {#channel or channel_id} "{custom_message}"
Add a Twitch handle to notify in the specified channel when they go live using the placeholders - handle, game, title and link

##### !edittwitch {twitch_handle} {#channel or channel_id}
Edit a configured Twitch handle to use a different channel

##### !editcustomtwitch {twitch_handle} "{custom_message}"
Edit a configured Twitch handle to display a custom message using the placeholders - handle, game, title and link

##### !removetwitch {twitch_handle}
Remove the specified twitch handle from alerting

##### !removealltwitch
Remove all the Twitch alerts in the guild

##### !getalltwitch
List all the current Twitch handles configured in the server

</details>

<details>
<summary>Reaction Role Menus and Polls</summary>

### Reaction Menus
Esportsbot now includes a slightly stripped down version of the reaction menus implementation provided by [BASED](https://github.com/Trimatix/BASED).

Making new types of reaction menus is easy - simply extend `reactionMenus.reactionMenu.ReactionMenu`.

To register a menu instance for interaction, use `client.reactionMenus.add(yourMenuInstance)`. For an example of this, see `cogs.MenusCog.admin_cmd_make_role_menu`.

All saveable reaction menus are automatically added and removed from Esportsbot's PostgreSQL database, and will be loaded in again on bot startup. To register your `ReactionMenu` subclass as saveable, use the `reactionMenu.saveableMenu` class decorator. Saveable menus **MUST** provide complete `toDict` and `fromDict` implementations. For examples of this, see `reactionMenus.reactionRoleMenu`.

`ReactionMenu`s store each option in the menu as an instance of a `reactionMenu.ReactionMenuOption` subclass - each `ReactionMenuOption` has its own individual behaviour for when reactions are added and removed. This already provides a huge amount of flexibility, but you can achieve even more with a custom `ReactionMenuOption` subclass. To make your `ReactionMenuOption` saveable, provide complete `toDict` and `fromDict` implementations. For an example of this, see `reactionMenus.reactionRoleMenu.ReactionRoleMenuOption`.

### Reaction Role Menus
Allows admins to create and maintain menus which grant and remove roles from users upon interaction. Currently, anyone can interact with any role menu. However, reaction role menus are already set up to be limited to a certain role or user. To make use of this functionality, the `!make-role-menu` command must be extended to also pass a `targetRole` or `targetMember` to the menu constructor.

### Reaction Polls
Allows any user to run a time-limited poll, where voters can select one (or many) of several string options, by adding reactions to the menu. After the menu runs out of time, a bar chart of the results is edited into the menu message. Each guild may only run a limited number of polls at once.

##### !make-role-menu
```
!make-role-menu {title}
{option1 emoji} {@option1 role}
...    ...
```
Admin command: Create a reaction role menu.

Each option must be on its own new line, as an emoji, followed by a space, followed by a mention of the role to grant.

The `title` is displayed at the top of the menu and is optional, to exclude your title simply give a new line.

##### !add-role-menu-option {menu-id} {emoji} {@role mention}
Admin command: Add a role to a role menu.

To get the ID of a reaction menu, enable discord's developer mode, right click on the menu, and click Copy ID.

Your emoji must not be in the menu already, adding the same role more than once is allowed.

Give your role to grant/remove as a mention.

##### !del-role-menu-option {menu-id} {emoji}
Admin command: Remove a role from a role menu.

To get the ID of a reaction menu, enable discord's developer mode, right click on the menu, and click Copy ID.

Your emoji must be an option in the menu.

##### !poll
```
!poll] {title}
{option1 emoji} {@option1 role}
...    ...
[multipleChoice=...]
[seconds=...]
[minutes=...]
[hours=...]
[days=...
```
User command: Run a reaction-based poll.

Each option must be on its own new line, as an emoji, followed by a space, followed by the name, or short description, of the option.

The `title` is displayed at the top of the menu and is optional, to exclude your title simply give a new line.

The time to run the poll for can be specified by keywords. The number of votes allowed to each user can also be specified, with multiplechoice=yes meaning that users can submit as many votes as they like, and multiplechoice=no meaning that only one of each user's votes will be counted. This setting will be indicated to voters in the menu.

The default args are: `seconds=0` `minutes=5` `hours=0` `days=0` `multipleChoice=yes`

##### !del-menu {id}
Admin command: Remove the specified reaction menu. You can also just delete the message, if you have permissions. This is not restricted to role menus or polls.

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

#### !pausesong
* Pauses the current song. Only works if there is something playing.

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
<summary>User Created Roles w/ Cooldown-Limited Pings</summary>

### User Created Pingable Roles

Roles which may be voted into existance by anyone.

On creation request, a poll will be triggered. If the poll receives a certain number of votes, the role will be created.

While the role takes its requested colour (default green), it is pingable by anyone. If the role is pinged, its colour will be changed the grey, and the role is no longer pingable by anyone. Once a cooldown period has passed (default 5 hours), the colour and pingable status will be reverted.

Every month, a report of the use of all pingable roles will be sent to the servers logging channel, if one is set.

##### !pingme list
User command: list out all available `!pingme` roles

##### !pingme register {@role mention} {name}
Admin command: register an existing role for use with `!pingme`.

##### !pingme unregister {@role mention}
Admin command: unregister a role for use with `!pingme`, without deleting the role from the server.

##### !pingme delete {@role mention}
Admin command: unregister a role for use with `!pingme`, and deleting the role from the server.

Alternatively, if you have permission, you can simply delete the role from the server within discord, and the role will automatically be unregistered from `!pingme`.

##### !pingme reset-cooldown {@role mention}
Admin command: reset the cooldown for mentioning the given `!pingme` role. The role will immediately become pingable again by anyone.

##### !pingme set-cooldown seconds={seconds} minutes={minutes} hours={hours} days={days}
Admin command: set the cooldown between a `!pingme` role being pinged, and it becoming pingable again. All args should be given as keyword args as shown. All args are optional.
This does not update the cooldown for roles that are already on cooldown.

##### !pingme set-create-threshold {num votes}
Admin comman: set the minimum number of votes required for users to create a role with `!pingme create`. This does not affect already running polls.

##### !pingme set-create-poll-length seconds={seconds} minutes={minutes} hours={hours} days={days}
Admin command: set the amount of time `!pingme create` polls run for. All args should be given as keyword args as shown. All args are optional.
This does not affect already running polls.

##### !pingme set-role-emoji {emoji}
Admin command: set a single unicode emoji to be prefixed onto all `!pingme` role names. This will update the names of all existing `!pingme` roles.

##### !pingme remove-role-emoji
Admin command: remove the emoji prefix for all `!pingme` role names. This will update the names of all existing `!pingme` roles.

##### !pingme create {name}
User command: request the creation of a `!pingme` role with the given name. A `!pingme` role with the given name must not already exist.
On command use, a poll will be created. If a minimum number of votes is reached, a role with the given name is created, and registered for `!pingme` cooldown etc.

##### !pingme for {name}
User command: add or removing the `!pingme` role with the given name to/from the user.

##### !pingme clear
User command: remove all `!pingme` roles from the user.

</details>
