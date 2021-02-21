# UoY Esport Bot Rewrite
## How to set up an instance of this bot

Clone this repository locally:<br/>
```console
$ git clone https://github.com/Ryth-cs/Esports-Bot-Rewrite.git
```

Go into the directory /src:
```console
$ cd Esports-Bot-Rewrite/src/
```

Create a .env file and edit it in Vim:
```console
$ vim .env
```

Edit the below environment variables:
```console
DISCORD_TOKEN = ''
PG_HOST = ''
PG_DATABASE = 'esportsbot' # Edit the startup script in /db_instance if you change this
PG_USER = 'postgres' # Edit the startup script in /db_instance if you change this
PG_PWD = ''
```

Move to the main directory and edit the docker-compose.yml in Vim:
```console
$ cd ..
$ vim docker-compose.yml
```

Change the POSTGRES_PASSWORD to your previous value:
```console
POSTGRES_PASSWORD = ''
```

Exit Vim and run docker-compose:
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
<summary>LAN Channel Management</summary>

### LAN Channel Management

##### !open-lan
Set the server's LAN signin channel as visible.

##### !close-lan
Set the server's LAN signin channel as invisible, remove the server's LAN role from all users, and reset the LAN signin menu.

##### !set-lan-signin-menu {menu_id}
Set the reaction menu to clear during `!close-menu`. This will also tell the bot which channel to set visibility for during `!open-lan`.

##### !set-shared-role {@role or role_id}
Set the role to deny signin channel visiblity to during `!close-menu`.

##### !set-lan-role {@role or role_id}
Set the role to remove from users during `!close-menu`.
</details>
