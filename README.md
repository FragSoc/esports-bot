
# UoY Esports Bot Rewrite
<div align=left>
    <a href="https://travis-ci.com/FragSoc/esports-bot"><img src="https://img.shields.io/travis/com/fragsoc/esports-bot?style=flat-square" /></a>
    <a href="https://hub.docker.com/r/fragsoc/esports-bot"><img src="https://img.shields.io/docker/pulls/fragsoc/esports-bot?style=flat-square" /></a>
    <a href="https://github.com/FragSoc/esports-bot"><img src="https://img.shields.io/github/license/fragsoc/esports-bot?style=flat-square" /></a>
</div>
Dependency Versions:
<div align=left>
    <img src="https://img.shields.io/badge/min%20python%20version-3.8.0-green?style=flat-square" />
    <img src="https://img.shields.io/badge/min%20postgres%20version-11-lightgrey?style=flat-square" />
    <img src="https://img.shields.io/badge/min%20docker%20version-20.0.0-blue?style=flat-square" />
    <img src="https://img.shields.io/badge/min%20docker--compose%20version-1.25.0-blue?style=flat-square" />
</div>

This Discord bot was written to merge all the functions of different bots used in the Fragsoc Discord server into one bot that is maintained by Fragsoc members.

## How to set up an instance of this bot with Docker

1. Clone this repository:
```console
$ git clone https://github.com/FragSoc/Esports-Bot-Rewrite.git
```
2. Change into the repo directory:
```console
$ cd Esports-Bot-Rewrite
```
3. Rename the `secrets.template` to `secrets.env` and set all the variables. Be sure to read the `Current Functions` section below for the Cog you want to enable in case of any special setup instructions:
```console
$ nano secrets.env
```
4. Run docker-compose:
```console
$ docker-compose up
```
## How to set up an instance of this bot without Docker
Requirements needed to run:
- Python 3.8
- Pip
- [A postgres 11 database](https://www.postgresql.org/docs/current/admin.html)
1. Clone this repository:
```console
$ git clone https://github.com/FragSoc/Esports-Bot-Rewrite.git
```
2. Change into the repo directory:
```console
$ cd Esports-Bot-Rewrite
```
3. Rename the `secrets.template` to `secrets.env` and set all the variables. Be sure to read the `Current Functions` section below for the Cog you want to enable in case of any special setup instructions:
```console
$ nano secrets.env
$ source secrets.env
```
4. Change into the `src` directory
```bash
cd src
```
4. Install all the requirements for python:
```bash
pip install -r requirements.txt
```
5. Run the bot:
```bash
python3 main.py
```

## Current Functions
The list below describes the different "Cogs" of the bot, their associated commands, and any additional information required to set them up.

<details>
<summary>Voicemaster</summary>

### Voicemaster
 #### !setvmmaster <channel_id>
* Make the given ID a Voicemaster master.

#### !getvmmasters * Get all the Voicemaster masters in the server.

#### !removevmmaster <channel_id>
* Remove the given ID as a Voicemaster master.

#### !removeallmasters * Remove all Voicemaster masters from the server.

#### !killallslaves * Kill all the Voicemaster slave channels in the server.

#### !lockvm * Locks the Voicemaster slave you're currently in to the number of current members.

#### !unlockvm * Unlocks the Voicemaster slave you're currently in.
</details>

<details>
<summary>Default Role</summary>

### Default role
 #### !setdefaultrole <role_mention | role_id> * Set the default role to the @'ed role or given role ID.

#### !getdefaultrole * Gets the current default role value.

#### !removedefaultrole * Removes the current default role.
</details>

<details>
<summary>Log Channel</summary>

### Log Channel
 #### !setlogchannel <channel_mention | channel_id> * Set the log channel to the #'ed channel or given role ID.

#### !getlogchannel * Gets the current log channel value.

#### !removelogchannel * Removes the current log channel value.
</details>

<details>
<summary>Administrator Tools</summary>

### Administrator Tools
 Adds a few commands useful for admin operations.
#### !clear_message * Aliases: `cls, purge, delete`
* Clear the specified number of messages from the current text channel.

#### !members * List the current number of members in the server.
</details>

<details>
<summary>Twitter Integration</summary>

### Twitter Integration
Enables forwarding tweets when they are tweeted to a discord channel for specific Twitter accounts.

Requires the `ENABLE_TWITTER` variable to be set to `TRUE` in order to function.
#### !addtwitter <twitter_handle>
* Add a Twitter handle to notify when they tweet or quote retweet.

#### !removetwitter <twitter_handle>
* Remove the given Twitter handle from notifications.

#### !twitterhook [optional: channel_mention] [optional: hook_name]
* Aliases:  `addtwitterhook`
* Creates a Discord Webhook bound to the channel the command was executed in, unless a channel is given, and with a default name unless a name is given.

#### !removetwitterhook <hook_name>
* Aliases: `deltwitterhook`
* Deletes the Discord Webhook so that updates are no longer sent to that channel

#### !gettwitters
* Aliases: `getalltwitter, gettwitterhandles`.
* Returns a list of the currently tracked Twitter accounts for the server.
</details>

<details>
<summary>Pingme: User-Created Roles With Ping Cooldown</summary>

### Pingme: User-Created Roles With Ping Cooldown
Users can start a vote to create a new role. If enough votes are reached, a new role is created. The role can be pinged by anyone, but is placed on cooldown afterwards.

To help administrators manage the number of roles, a usage report is sent to the server's logging channel on a monthly basis.

#### !pingme register <role_mention | role_id> <role_name>
* Register a new role for use with `!pingme`, with the given name. This does not have to be the same as the role's name.
* *__Can only be executed by an Administrator__*

#### !pingme unregister <role_mention | role_id>
* Unregister a role from use with `!pingme`, without deleting the role from the server.
* *__Can only be executed by an Administrator__*

#### !pingme delete <role_mention | role_id>
* Unregister a `!pingme` role from the role from the server.
* *__Can only be executed by an Administrator__*

#### !pingme reset-cooldown <role_mention | role_id>
* Reset the pinging cooldown for a `!pingme` role, making it pingable again instantly.
* *__Can only be executed by an Administrator__*

#### !pingme set-cooldown [seconds=...] [minutes=...] [hours=...] [days=...]
* Set the cooldown between `!pingme` role pings.
* *__Can only be executed by an Administrator__*

#### !pingme set-create-threshold <num_votes>
* Set minimum number of votes required to create a new role during `!pingme create`.
* *__Can only be executed by an Administrator__*

#### !pingme set-create-poll-length [seconds=...] [minutes=...] [hours=...] [days=...]
* Set the amount of time which `!pingme create` polls run for.
* *__Can only be executed by an Administrator__*

#### !pingme set-role-emoji <emoji>
* Set the emoji which appears before the names of `!pingme` roles. Must be a built-in emoji, not custom.
* *__Can only be executed by an Administrator__*

#### !pingme remove-role-emoji
* Remove the emoji which appears before the names of `!pingme` roles.
* *__Can only be executed by an Administrator__*

#### !pingme create <role_name>
* Start a poll for the creation of a new `!pingme` role.

#### !pingme for <role_name>
* Get yourself a `!pingme` role, to be notified about events and games.

#### !pingme list
* List all available `!pingme` roles.

#### !pingme clear
* Unsubscribe from all `!pingme` roles, if you have any.
</details>

<details>
<summary>Event Channel Management</summary>

### Event Category Management
Each server can have any number of named event categories, each with a registered signin role menu granting an event specific role. All commands in this cog are administrator commands.

#### !open-event <event_name>
* Set the event's signin channel as visible to the server's shared role.

#### !close-event <event_name>
* Set the event's signin channel as invisible, remove the event's role from all users, and reset the event's signin menu.

#### !register-event-category <menu_id> <role_mention | role_id> <event_name>
* Register an existing category and role as an event category, allowing you to use `!open-event` and `!close-event` with it.

#### !create-event-category <event_name>
* Create a new event category with a signin menu, general text and voice channels, and an event role. This category will automatically be registered for use with `!open-event` and `!close-event`

#### !unregister-event-category <event_name>
* Unregister an event category and role, without deleting them from the server.

#### !delete-event-category <event_name>
* Delete an event category from the server, including the category, channels and role. You will be asked for confirmation first.

#### !set-event-signin-menu <menu_id> <event_name>
* Change the reaction menu to clear during `!close-event`. This will also tell the bot which channel to set visibility for during `!open-event`.

#### !set-shared-role <role_mention | role_id>
* Change the role to deny signin channel visibility to during `!close-event`. All users should have ths role.

#### !set-event-role <role_mention | role_id> <event_name>
* Change the role to remove from users during `!close-event`.
</details>

<details>
<summary>Twitch Integration</summary>

### Twitch Integration
Enables sending notifications to a Discord channel whenever a tracked channel goes live.

Requires the  `ENABLE_TWITCH` variable to be set to  `TRUE` in order to function.

### Creating your self-signed SSL keys:
1. Create the Certificate Authority (CA) private key:
```console
$ openssl genrsa -des3 -out servercakey.pem
```
2. Create the CA public certificate:
```console
$ openssl req -new -x509 -key servercakey.pem -out root.crt
```
3. Create the server's private key file:
```console
$ openssl genrsa -out server.key
```
4. Create the server's certificate request:
```console
$ openssl req -new -out reqout.txt -key server.key
```
5. Use the CA private key file to sign the server's certificate:
```
$ openssl x509 -req -in reqout.txt -days 3650 -sha1 -CAcreateserial -CA root.crt -CAkey servercakey.pem -out server.crt
```
6. Move the `server.crt` file and `server.key` to the root file directory of the bot (i.e., the same directory as your `.env` etc.)

### Getting your Twitch Credentials:
1. Go to the [Twitch Developers](https://dev.twitch.tv/) site.
2. Once logged in, in the top left, go to `Your Console` or [this](https://dev.twitch.tv/console) site.
3. Register a new application using any name and the OAuth Redirect URL of `http://localhost`.
4. Once created, click `manage`. Copy the string that is in `Client ID` and then click the `New Secret` button to generate a new `Client Secret` and then copy the string it generates.

In your `.env` file the `TWITCH_SUB_SECRET` should be a string that is 10-100 characters long and should not be shared anywhere. This is used to authenticate if a message has come from Twitch or if it has been altered along the way.

The `TWITCH_CALLBACK` is the URL to your HTTPS server. For testing you can use `ngrok`:
- Run `ngrok http 443` and copy the `https` URL **not** the `htttp` URL and use that as your `TWITCH_CALLBACK` variable.

#### !twitch createhook [optional: channel_mention] [optional: hook_name]
* Creates a Discord Webhook bound to the channel the command was executed in, unless a channel is given, and with a default name unless a name is given.

#### !twitch deletehook <hook_name>
* Deletes the given Discord Webhook.

#### !twitch add <twitch_handle | twitch_url> [optional: custom_message]
* Adds a Twitch channel to be tracked in the current Discord server.
* *__If a custom message is given, it must be surrounded by double quotes__*: `!twitch add <twitch_handle> "custom_message"`

#### !twitch remove <twitch_handle>
* Removes a Twitch channel from being tracked in the current Discord server.

#### !twitch list
* Shows a list of all the currently tracked Twitch accounts and their custom messages.

#### !twitch setmessage <twitch_handle> [optional: custom_message]
* Sets the custom message of a Twitch channel. Can be left empty if the custom message is to be removed.
* *__If a custom message is given, it must be surrounded by double quotes__*: `!twitch setmessage <twitch_handle> "custom_message"`

#### !twitch getmessage <twitch_handle>
* Gets the currently set custom message for a Twitch channel.

</details>

<details>
<summary>Reaction Role Menus</summary>

### Reaction Role Menus Esportsbot now includes a slightly stripped down version of the reaction menus implementation provided by [BASED](https://github.com/Trimatix/BASED).

Making new types of reaction menus is easy - simply extend `reactionMenus.reactionMenu.ReactionMenu`.

To register a menu instance for interaction, use `client.reactionMenus.add(yourMenuInstance)`. For an example of this, see `cogs.MenusCog.admin_cmd_make_role_menu`.

All saveable reaction menus are automatically added and removed from Esportsbot's PostgreSQL database and will be loaded in again on bot startup. To register your `ReactionMenu` subclass as saveable, use the `reactionMenu.saveableMenu` class decorator. Saveable menus **MUST** provide complete `toDict` and `fromDict` implementations. For examples of this, see `reactionMenus.reactionRoleMenu`.

`ReactionMenu`s store each option in the menu as an instance of a `reactionMenu.ReactionMenuOption` subclass - each `ReactionMenuOption` has its own behaviour for when reactions are added and removed. This already provides a huge amount of flexibility, but you can achieve even more with a custom `ReactionMenuOption` subclass. To make your `ReactionMenuOption` saveable, provide complete `toDict` and `fromDict` implementations. For an example of this, see `reactionMenus.reactionRoleMenu.ReactionRoleMenuOption`.

#### !make-role-menu
```
!make-role-menu {title}
{option1 emoji} {@option1 role}
...    ...
```
Create a reaction role menu.

Each option must be on its own new line, as an emoji, followed by a space, followed by a mention of the role to grant.

The `title` is displayed at the top of the menu and is optional, to exclude your title simply give a new line.

#### !add-role-menu-option <menu_id> <emoji> <role_mention>
Add a role to a role menu.

To get the ID of a reaction menu, enable discord's developer mode, right-click on the menu, and click Copy ID.

Your emoji must not be in the menu already, adding the same role more than once is allowed.

Give your role to grant/remove as a mention.

#### !del-role-menu-option <menu_id> <emoji>
Remove a role from a role menu.

To get the ID of a reaction menu, enable discord's developer mode, right-click on the menu, and click Copy ID.

Your emoji must be an option in the menu.

##### !del-menu <menu_id>
Remove the specified reaction menu. You can also just delete the message, if you have permissions.

To get the ID of a reaction menu, enable discord's developer mode, right-click on the menu, and click Copy ID.
</details>

<details>
<summary>Music Bot</summary>

### Music Bot

The Esports bot now has a basic music bot that functions very similarly to the popular 'Hydra Bot'.

Commands that control the music must be performed in the defined music channel. They also require you to be in the same
voice channel as the bot, so that only the people listening can change the flow of music.

To add new songs to the queue, just put the name, YouTube link, or a YouTube playlist into the music channel once set.
Also requires you to be in the voice channel with the bot, or if the bot is inactive, in any voice channel.

### To create your Google API credentials:
1. Go to the [Google Cloud API]("https://console.cloud.google.com/apis/") site.
2. Create a new project and name it whatever you want.
3. In the [dashboard](https://console.cloud.google.com/apis/dashboard), click the `Enable APIs and Services` and search for `YouTube Data API v3`.
4. Click `Enable` to enable the use of the YouTube API.
5. Keep going back until at your [dashboard](https://console.cloud.google.com/apis/dashboard), and go to the [credentials](https://console.cloud.google.com/apis/credentials) section on the left.
6. Click on `Create Credentials` and then `API key`.
7. Copy the key given. For security, it is recommended that you "restrict key" and only enable `YouTube Data API v3`.

#### !setmusicchannel [optional: {args}] <channel_id>

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

#### !removesong <index>
* Aliases: `remove, removeat`
* Removes a song from the queue at the given index.

#### !resumesong
* Aliases: `resume, play`
* Resumes the current song. Only works if paused.

#### !pausesong
* Aliases: `pause, stop`
* Pauses the current song. Only works if there is something playing.

#### !kickbot
* Aliases: `kick`
* Kicks the bot from the current call. Will also clear the queue

#### !skipsong
* Aliases: `skip`
* Skips the current song. If the current song is the only song in the playlist, the bot will leave.

#### !listqueue
* Aliases: `list, queue`
* Shows the current queue. Has the same output as the current queue in the music channel
* *__Can't be sent in the music channel__*

#### !clearqueue
* Aliases: `clear, empty`
* Clears the current queue

#### !shufflequeue
* Aliases: `shuffle, randomise`
* If the queue has 3 or more items, including the current song, it will shuffle all but the current songs.
</details>

<details>
<summary>User Created Roles w/ Cooldown-Limited Pings</summary>

### User Created Pingable Roles

Roles which may be voted into existence by anyone.

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
Admin command: set the cooldown between a `!pingme` role being pinged, and it being pingable again. All args should be given as keyword args as shown. All args are optional.
This does not update the cooldown for roles that are already on cooldown.

##### !pingme set-create-threshold {num votes}
Admin command: set the minimum number of votes required for users to create a role with `!pingme create`. This does not affect already running polls.

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
