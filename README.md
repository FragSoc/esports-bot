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

# Current Functions

The list below describes the different "Cogs" of the bot, their associated commands, and any additional information required to set them up.

<details>
<summary>AdminTools</summary>

## AdminTools

AdminTools cog is used to manage basic Administrator/Moderation tools.
All commands in this cog require the user to have the administrator permission in a given guild/server.

### Current Commands:

#### /admin-member-count

- Get the current member count of the server.

#### /admin-clear-messages [optional: message-count]

- Delete a specific number of messages in the given channel.
  Defaults to 5 messages, with a maximum of 100 messages.

#### /admin-get-version

- Get the current version of the Bot.

</details>

<details>
<summary>VoiceAdmin</summary>

## VoiceAdmin

### Environment Variable: `ENABLE_VOICEADMIN`

VoiceAdmin cog is used to dynamically create and manage Voice Channels, by assigning specific channels to act as parent channels.
When users join parent Voice Channels, a new chil Voice Channel is created, and the user moved to it.
The user has control over the child Voice Channel name, and can limit how many/who can join.

### Current Commands:

#### /vc-set-parent \<voice-channel\>

- Set a Voice Channel to be a parent Voice Channel.

#### /vc-remove-parent \<voice-channel\>

- Remove a Voice Channel from being a parent Voice Channel.

#### /vc-get-parents

- Get the list of current parent Voice Channels.

#### /vc-rename \<new-name\>

- Rename your current Voice Channel

#### /vc-lock

- Only allow current members to (re)join your Voice Channel.

#### /vc-unlock

- Allow anyone to join your Voice Channel again.

#### /vc-limit

- Set the member count limit of your Voice Channel.

#### /vc-unlimit

- Remove the member count limit of your Voice Channel.

</details>

<details>
<summary>AutoRoles</summary>

## AutoRoles

### Environment Variable: `ENABLE_AUTOROLES`

### _Not yet implemented!_

</details>

<details>
<summary>EventTools</summary>

## EventTools

### Environment Variable: `ENABLE_EVENTTOOLS`

### _Not yet implemented!_

</details>

# TODO:

- ~~Implement unimplemented commands in VoiceAdmin and AdminTools cogs.~~
- Implement EventTools cog.
- Implement AutoRoles cog.
- Add back functionality of previous bot (eg. Music, PingableRoles, etc.)
- Add game deal tracker (DealTracker(?) cog)

# Quick Setup Guide

Requirements needed to run:

- Python 3.8
- Pip
- [A postgres 11 database](https://www.postgresql.org/docs/current/admin.html)

1. Clone this repository:

```console
$ git clone https://github.com/FragSoc/esports-bot.git
```

2. Change into the repo directory:

```console
$ cd esports-bot
```

3. Rename the `secrets.template` to `secrets.env` and set all the variables.

```console
$ nano secrets.env
$ source secrets.env
```

4. Install all the requirements for python:

```bash
pip install -r requirements.txt
```

5. Run the bot:

```bash
python3 src/main.py
```
