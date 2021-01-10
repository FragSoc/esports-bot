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

##### !removevmmaster
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

##### !setdefaultrole
Set the default role to the @'ed role or given role ID

##### !getdefaultrole
Gets the current default role value

##### !removedefaultrole
Removes the current default role
</details>

<details>
<summary>Log Channel</summary>

### Log Channel

##### !setlogchannel
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