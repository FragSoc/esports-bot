
# UoY Esports Bot Rewrite  
<div align=left>  
    <a href="https://github.com/FragSoc/esports-bot/actions"><img src="https://img.shields.io/github/workflow/status/FragSoc/esports-bot/docker_push/develop?style=flat-square" /></a>  
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
4. Change into the bot directory:
```bash
$ cd src
```
5. Install all the requirements for python:  
```bash  
pip install -r requirements.txt  
```  
6. Run the bot:  
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
    
#### !members 
* List the current number of members in the server.

#### !remove-cog \<cog name>
* Unloads the given cog.
* *This command requires your user ID to be defined in the env file under `DEV_IDS`*

#### !add-cog \<cog name>
* Loads the given cog.
* *This command requires your user ID to be defined in the env file under `DEV_IDS`*

#### !reload-cog \<cog name>
* Reloads the given cog.
* *This command requires your user ID to be defined in the env file under `DEV_IDS`*
</details>  
  
<details>  
<summary>Twitter Integration</summary>  
  
### Twitter Integration  
Enables forwarding tweets when they are tweeted to a discord channel for specific Twitter accounts.  
  
Requires the `ENABLE_TWITTER` variable to be set to `TRUE` in order to function.  
#### !twitter add \<twitter handle>  
* Add a Twitter handle to notify when they tweet or quote retweet.  
  
#### !twitter remove \<twitter handle>  
* Remove the given Twitter handle from notifications.  
  
#### !twitter hook [optional: channel mention] [optional: hook name]  
* Aliases:  `addtwitterhook, create-hook`  
* Creates a Discord Webhook bound to the channel the command was executed in, unless a channel is given, and with a default name unless a name is given.  
  
#### !twitter remove-hook \<hook name>  
* Aliases: `deltwitterhook, delete-hook`  
* Deletes the Discord Webhook so that updates are no longer sent to that channel  
  
#### !twitter list  
* Aliases: `accounts, get-all`.  
* Returns a list of the currently tracked Twitter accounts for the server.  
</details>
  
<details>  
<summary>Event Channel Management</summary>  
  
### Event Category Management  
Each server can have any number of named event categories, where each category creates a sign-in channel, a general chat, a voice chat and a role for the event. All commands in this cog required the `administrator` permission in Discord.  
  
#### !events create-event \<event name> \<role mention | role ID>  
* Creates the text channels, and voice channel for the event. The role given is used to later expose the sign-in channel to members. Upon creation the event is set to `closed`.
* See the `open-event` and `close-event` for more information regarding which members can see which channels.
* The role created for this event will have the same as the event name, it is not the role given in the command.

#### !events open-event \<event name>  
* Allows the role given in the `create-event` command to see the sign-in channel, and add reactions to the sign-in message.
* The sign-in message grants the role created by the bot for the event. 
  
#### !events close-event \<event name>
* Stops any member who is not an administrator from being able to see any of the event channels. 
  
#### !events delete-event \<event name>  
* Deletes all the channels in the category for the event and deletes the role created by the bot for the event.
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
  
#### !twitch createhook \<channel mention> \<hook name>
* Aliases: `newhook, makehook, addhook`
* Creates a new Discord Webhook bound to the mentioned channel. 
  The name will be prefixed with the Twitch Cog Webhook prefix to distinguish Twitch hooks from other Webhooks.
  The Webhooks created with the Twitch Cog do not need the prefix used in the name in order to reference them.
* *Requires `administrator` permission in Discord*
  
#### !twitch deletehook \<hook name>  
* Deletes the given Discord Webhook.  
* *Requires `administrator` permission in Discord*
  
#### !twitch add \<twitch handle | twitch url> \<webhook name> [optional: custom message]  
* Adds a Twitch channel to be tracked in the given Webhook.
  This means when the channel goes live, its notification will be posted to the given Webhook.
  A channel can be tied to more than one Webhook.
  The custom message can be left empty, but when not, it will be used in the live notification.
  A preview of what a notification looks like can be seen with the `!twitch preview <twitch handle> <webhook name>` command.
* *__If a custom message is given, it must be surrounded by double quotes__*: `!twitch add <twitch_handle> <webhook name> "custom_message"`  
* *Requires `administrator` permission in Discord*
  
#### !twitch remove \<twitch handle>  \<webhook name>
* Removes a Twitch channel from being tracked in the given Webhook.
* *Requires `administrator` permission in Discord*
  
#### !twitch list [optional: webhook name] 
* Shows a list of all the currently tracked Twitch accounts and their custom messages for the given Webhook.
If no Webhook name is given, it shows the information for all Twitch Webhooks.
* *Requires `administrator` permission in Discord*
  
#### !twitch webhooks
* Shows a list of the current Webhooks for the Twitch Cog.
* *Requires `administrator` permission in Discord*

#### !twitch setmessage \<twitch handle> \<webhook name> [optional: custom message]  
* Sets the custom message of a Twitch channel for the given Webhook. 
  Can be left empty if the custom message is to be removed. 
* *__If a custom message is given, it must be surrounded by double quotes__*: `!twitch setmessage <twitch_handle> <webhook name> "custom_message"` 
* *Requires `administrator` permission in Discord*
  
#### !twitch getmessage \<twitch handle>  [optional: webhook name]
* Gets the currently set custom message for a Twitch channel for the given Webhook.
If no Webhook name is given, it shows a list of all the custom messages for the Webhooks the channel is tracked in.
* *Requires `administrator` permission in Discord*

#### !twitch preview \<twitch handle> \<webhook name>
* Shows a preview of the live notification for a given channel for the given Webhook.
  
</details>  
  
<details>    
<summary>Role Reaction Menus</summary>    
    
### Role Reaction Menus.    

Role reaction menus allow admins to create reactable menus that when reacted to grant defined roles to the user.

For devs:    
* To enable this function in the bot use the `ENABLE_ROLEREACTIONS` env var and set it to `TRUE`.
* Making new types of reaction menus is easy - simply extend `DiscordReactableMenus.ReactableMenu` or one of the example menus in `DiscordReactableMenus.ExampleMenus`.
    
#### !roles make-menu \<title> \<description> [\<mentioned role> \<emoji>]
* Creates a new role reaction menu with the given roles and their emojis.
* Each option must be a mentioned role followed by the emoji to use as its reaction. There can be up to 25 roles in a single reaction menu.
* The `title` is displayed at the top of the menu, and the `description` just below. To have either blank leave the quotes empty.
* If the `DELETE_ROLE_CREATION` env var is set to `TRUE` the command message will be deleted.
* *Requires `administrator` permission in Discord*
* An example usage of this command is as such: `!roles make-menu "{title}" "{description}" {@option1 role} {option1 emoji} ... ...`

#### !roles add-option [optional: menu id] [\<mentioned role> \<emoji>]
* Adds more role reaction options to the given menu. If there is no menu id given, the latest role reaction menu will be used.
* There can be one or many options added at the same time with this command.
* Each option must be a mentioned role followed by the emoji to use as its reaction. There can be up to 25 roles in a single reaction menu.
* *Requires `administrator` permission in Discord*
* An example usage of this command is as such: `!roles add-option {menu id} {@option role} {option emoji} ... ...`

#### !roles remove-option \<emoji> [optional: menu id]
* Removes the role associated with the emoji from the given menu. If there is no menu id given, the latest role reaction menu will be used.
* *Requires `administrator` permission in Discord*

#### !roles disable-menu [optional: menu id]
* Disables a reaction menu. This means that roles will not be given to users when they react to the message. If there is no menu id given, the latest role reaction menu will be used.
* *Requires `administrator` permission in Discord*

#### !roles enable-menu [optional: menu id]
* Enables a reaction menu. This means that users will be able to receive roles from the reaction menu when they react. If there is no menu id given, the latest role reaction menu will be used.
* *Requires `administrator` permission in Discord*

#### !roles delete-menu \<menu id>
* Deletes the given role reaction menu. __Does not__ delete any of the roles in the menu, just the message.
* *Requires `administrator` permission in Discord*

#### !roles toggle-ids
* Shows or Hides all role reaction menu footers, which contain the ID of the role reaction menu for ease of identification.
* *Requires `administrator` permission in Discord*

</details>   

<details>    
<summary>Poll Reaction Menus</summary>    
    
### Poll Reaction menus.    

Poll reaction menus allow users to create polls with up to 25 different options for other users, and themselves, to vote on.

The poll start and end is not time based, but instead controlled by the user that created the poll or administrators.

For devs:    
* To enable this function in the bot use the `ENABLE_VOTINGMENUS` env var and set it to `TRUE`.
* Making new types of reaction menus is easy - simply extend `DiscordReactableMenus.ReactableMenu` or one of the example menus in `DiscordReactableMenus.ExampleMenus`.
    
#### !votes make-poll \<title> [\<emoji> \<description>]
* Creates a new poll with each emoji having a description.
* Each option must be an emoji and a description, with each one on a new line. There can be up to 25 roles in a single reaction menu.
* If the `DELETE_VOTING_CREATION` env var is set to `TRUE` the command message will be deleted.
* An example usage of this command is as such: 
  ```
  !votes make-poll {title} 
  {option1 emoji} {option1 description}
  {option2 emoji} {option2 description}
  ... ...
  [up to option 25] 
  ```

#### !votes add-option \<menu id> \<emoji> \<description>
* Aliases: `add, aoption`
* Adds another option to the poll with the menu id given.
* Only one option can be added at a time with this command.
* Each option must be an emoji and a description, with each one on a new line. There can be up to 25 roles in a single reaction menu.
* *You must be the owner of the poll or be an administrator*
* An example usage of this command is as such: `!votes add-option {menu id} {option emoji} {option description}`

#### !votes remove-option \<menu id> \<emoji>
* Aliases: `remove, roption`
* Removes the option from the poll with the menu id given.
* *You must be the owner of the poll or be an administrator*

#### !votes delete-poll \<menu id>
* Aliases: `delete, del`
* Deletes the poll with the menu id given.
* *You must be the owner of the poll or be an administrator*

#### !votes end-poll \<menu id>
* Aliases: `finish, complete, end`
* Deletes the actual poll message and sends a new message with the results of the poll.
* *You must be the owner of the poll or be an administrator*

#### !votes reset-poll \<menu id>
* Aliases: `reset, clear, restart`
* Removes all the current user-added reactions from the poll with the menu id given.
* *You must be the owner of the poll or be an administrator*

</details>

<details>  
<summary>Music Bot</summary>  
  
### Music Bot  
  
A basic music bot that functions similarly to the popular 'Hydra Bot'.  

Commands that use the prefix of `!music` are commands that must be sent in the defined music channel for the server.
The rest of the commands in this cog can be sent anywhere.
Most `!music` commands require you to be in the same voice channel as the bot, or if it is not in a channel, for you to be in a voice channel.
Some `!music` commands can have this requirement ignored if the user performing the command is an administrator and uses the `force` or `-f` flag in the command. 
  
To add new songs to the queue, just put the name, YouTube link, or a YouTube playlist into the music channel once set.  
Also requires you to be in the voice channel with the bot, or if the bot is inactive, in any voice channel.  
  
To enable this cog, use the `ENABLE_MUSIC` env var in your `secrets.env` file, and set it to `TRUE`.
For this cog to work, the `GOOGLE_API` env var must also be set, and instructions on how to get an API credential is below:

### To create your Google API credentials:  
1. Go to the [Google Cloud API]("https://console.cloud.google.com/apis/") site.  
2. Create a new project and name it whatever you want.  
3. In the [dashboard](https://console.cloud.google.com/apis/dashboard), click the `Enable APIs and Services` and search for `YouTube Data API v3`.  
4. Click `Enable` to enable the use of the YouTube API.  
5. Keep going back until at your [dashboard](https://console.cloud.google.com/apis/dashboard), and go to the [credentials](https://console.cloud.google.com/apis/credentials) section on the left.  
6. Click on `Create Credentials` and then `API key`.  
7. Copy the key given. For security, it is recommended that you "restrict key" and only enable `YouTube Data API v3`.  
  
#### !music channel set \<channel mention> [optional: [args]] 
* This sets the channel mentioned to be used as the music channel. All messages into this channel will be considered music requests, and any music commands must be sent in this channel.
* Optional args:
  * Using `-c` will clear the entire channel before setting it up as the music channel.
* *Requires `administrator` permission in Discord*
  
#### !music channel get
* Sends the currently set music channel for the server. 
* *Requires `administrator` permission in Discord* 
  
#### !music channel reset
* This clears the current music channel and resets the preview and queue messages.  
* *Requires `administrator` permission in Discord*  

#### !music channel remove
* Unlinks the currently linked music channel from being the music channel. This will not delete the channel or its contents.
* *Requires `administrator` permission in Discord*  

#### !music fix
* If the bot has broken and thinks it is still in a Voice Channel, use this command to force it to reset.
* *Requires `administrator` permission in Discord*

#### !music queue
* Aliases: `songqueue, songs, songlist, songslist`
* Gets the current list of songs in the queue.
  
#### !music join [optional: -f | force]
* Aliases: `connect`  
* Make the bot join the channel. 
* If you are an admin you can force it join your voice channel using the `-f` or `force` option.
  
#### !music kick [optional: -f | force]
* Aliases: `leave`  
* Kicks the bot from the channel.
* If you are an admin you can force it to leave a voice channel with the `-f` or `force` option. 
  
#### !music play [optional: song request]  
* Aliases: `resume`  
* Resumes playback of the current song. 
* If a song is requested and there is no current song, it is played, otherwise it is added to the queue.

#### !music pause
* Pauses the current song.

#### !music shuffle
* Shuffles the current queue of songs.

#### !music volume \<volume level>
* Sets the volume of the bot for everyone to the level given.
           
#### !music clear
* Clears the queue entirely, does not stop the current song from playing.

#### !music skip [optional: skip to position]
* Skips the current song. 
* If a number is given it will also skip to the song at the position given.
* For example, if 'songs to skip' is 4, the next song to play would be song 4 in the queue.

#### !music remove \<song position>
* Removes the song at the given position from the queue.

#### !music move \<from position> \<to position>
* Moves the song at position `from position` to position `to position` in the queue.

</details>  
  
<details>  
<summary>Pingable Roles</summary>  
  
### Pingable Roles  
  
Pingable roles are roles that can be voted in to be created by any user, and that once created have a cooldown tied to how often that role can be pinged.

A user can create a poll where if there are enough votes by the time the poll ends, a role will be created. The length of the poll and the number of votes required are customisable by server admins.

After the poll finishes, a reaction menu gets created, allowing *any* user to react and receive the role. Initially the role will have the default cooldown of the server, but can be overridden.  
  
#### !pingme settings get-settings
* Returns an embed of the current default settings for the server.
* *Requires `administrator` permission in Discord*
  
#### !pingme settings default-settings
* Resets all settings for this guild to the bot-defined defaults defined in the `.env` file.
* *Requires `administrator` permission in Discord*

#### !pingme settings poll-length \<poll length in seconds>
* Sets the default poll length to the given time in seconds.
* Polls can have a custom length by specifying it when using the [`!pingme create-role`](#pingme-create-role-role-name-optional-poll-length-in-seconds) command. 
* *Requires `administrator` permission in Discord*

#### !pingme settings poll-threshold \<number of votes threshold>
* Sets the number of votes required in a poll for the role to be created.
* *Requires `administrator` permission in Discord*

#### !pingme settings ping-cooldown \<cooldown in seconds>
* Sets the default ping cooldown for any pingable role created with this cog.
* Roles can have their cooldown altered individually with the [`!pingme role-cooldown`](#pingme-role-cooldown-role-mention--role-id-cooldown-in-seconds) command.
* *Requires `administrator` permission in Discord*

#### !pingme settings poll-emoji \<emoji>
* Sets the emoji to be used when creating a poll to vote in.
* *Requires `administrator` permission in Discord*

#### !pingme settings role-emoji \<emoji>
* Sets the default emoji to be used in the role reaction menu for the pingable role once it has been created.
* Roles can have their reactable emoji altered individually with the [`!pingme role-emoji`](#pingme-role-emoji-role-mention--role-id-emoji) command.
* *Requires `administrator` permission in Discord*

#### !pingme disable-role \<one or many role mentions>
* Disables the roles mentioned from being mentioned by non-administrators and disables their reaction menus.
* The roles provided __must__ be pingable roles created with this cog.
* *Requires `administrator` permission in Discord*

#### !pingme enable-role \<one or many role mentions>
* Enabled the roles mentioned to be mentioned by non-administrators and allows their reaction menus to be reacted to.
* The roles provided __must__ be pingable roles created with this cog.
* *Requires `administrator` permission in Discord*

#### !pingme create-role \<role name> [optional: poll length in seconds]
* Creates a new poll to create a role if the number of votes has surpassed the server's threshold after the poll length has passed.

#### !pingme delete-role \<one or many role mentions>
* Deletes the mentioned roles from the server.
* The roles provided __must__ be pingable roles created with this cog.
* *Requires `administrator` permission in Discord*

#### !pingme convert-role \<one or many role mentions>
* Converts the mentioned roles into pingable roles and creates their reaction menus.
* The roles provided __cannot__ be roles that are already pingable roles.
* *Requires `administrator` permission in Discord*

#### !pingme convert-pingable \<one or many role mentions>
* Converts the mentioned roles from pingable roles into normal roles and deletes their reaction menus.
* The roles provided __must__ be pingable roles created with this cog.
* *Requires `administrator` permission in Discord*

#### !pingme role-cooldown \<role mention | role ID> <cooldown in seconds>
* Sets the ping cooldown for a specific role which overrides the server default for that role.
* The role provided __must__ be a pingable role created with this cog.
* *Requires `administrator` permission in Discord*

#### !pingme role-emoji \<role mention | role ID> <emoji>
* Sets the emoji to use in the reaction menu for the given role.
* The role provided __must__ be a pingable role created with this cog.
* *Requires `administrator` permission in Discord*

</details>
