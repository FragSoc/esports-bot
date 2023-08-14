# UoY Esports Bot Rewrite

<div align=left>
    <a href="https://travis-ci.com/FragSoc/esports-bot"><img src="https://img.shields.io/travis/com/fragsoc/esports-bot?style=flat-square" /></a>
    <a href="https://hub.docker.com/r/fragsoc/esports-bot"><img src="https://img.shields.io/docker/pulls/fragsoc/esports-bot?style=flat-square" /></a>
    <a href="https://github.com/FragSoc/esports-bot"><img src="https://img.shields.io/github/license/fragsoc/esports-bot?style=flat-square" /></a>
</div>

Dependency Versions:

<div align=left>
    <img src="https://img.shields.io/badge/min%20python%20version-3.9.0-green?style=flat-square" />
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

#### /admin member-count

- Get the current member count of the server.

#### /admin clear-messages [optional: message-count]

- Delete a specific number of messages in the given channel.
  Defaults to 5 messages, with a maximum of 100 messages.

#### /admin get-version

- Get the current version of the Bot.

</details>

<details>
<summary>RoleReact</summary>

## RoleReact

RoleReact cog is used to allow users to self-assign roles from a defined list of roles set by admins.
All commands in this cog require the user to have the administrator permissions in a given guild/server.

### Current Commands:

#### /reactroles create [optional: color]

- Creates a new menu to add roles to.

#### /reactroles delete \<menu ID\>

- Deletes a given menu and it's message.

#### /reactroles add-role \<menu ID\> \<role\> [optional: emoji] [optional: description]

- Add a role to a given menu. Optionally give the role an emoji and/or description.

#### /reactroles remove-role \<menu ID\> \<role\>

- Remove a role from a given menu.

</details>

<details>
<summary>LogChannel</summary>

LogChannel is a cog used to send log messages to a specified discord channel per-guild. A standard logging message can be forwarded by prefixing the message with the `LOGGING_PREFIX` and the guild, eg. `"LOGGING_PREFIX[guild_id] Message...".` This will send the log message to the specified log channel for the given guild if it has been configured to do so.

#### /logging set-channel \<Text Channel\>

- Configures the given channel to be the logging channel.

#### /logging get-channel

- Gets the currently assigned logging channel.

#### /logging remove-channel

- Removes the currently configured logging channel.

</details>

<details>
<summary>VoiceAdmin</summary>

## VoiceAdmin

### Environment Variable: `ENABLE_VOICEADMIN`

VoiceAdmin cog is used to dynamically create and manage Voice Channels, by assigning specific channels to act as parent channels.
When users join parent Voice Channels, a new chil Voice Channel is created, and the user moved to it.
The user has control over the child Voice Channel name, and can limit how many/who can join.

### Current Commands:

#### /voice-admin set-parent \<voice-channel\>

- Set a Voice Channel to be a parent Voice Channel.

#### /voice-admin remove-parent \<voice-channel\>

- Remove a Voice Channel from being a parent Voice Channel.

#### /voice get-parents

- Get the list of current parent Voice Channels.

#### /voice rename \<new-name\>

- Rename your current Voice Channel

#### /voice lock

- Only allow current members to (re)join your Voice Channel.

#### /voice unlock

- Allow anyone to join your Voice Channel again.

#### /voice limit

- Set the member count limit of your Voice Channel.

#### /voice remove-limit

- Remove the member count limit of your Voice Channel.

</details>

<details>
<summary>AutoRoles</summary>

## AutoRoles

### Environment Variable: `ENABLE_AUTOROLES`

#### /autoroles set-list \<One or many roles mentioned\>

- Sets the roles to be given to new users when they join the guild/server.
  - If one or more the of the roles are valid, any roles previously configured will be removed.

#### /autoroles add-role \<role\>

- Adds a role to the list of roles without overriding the currently configured roles.

#### /autoroles remove-role \<role\>

- Removes a role from the list of currently configured roles.

#### /autoroles get-list

- Gets the list of currently configured AutoRoles.

#### /autoroles clear-list

- Clears all roles from the list of configured AutoRoles.

</details>

<details>
<summary>EventTools</summary>

## EventTools

### Environment Variable: `ENABLE_EVENTTOOLS`

#### /events create-event \<name\> \<physical location\> \<start time\> \<end time\> \<timezone\> \<common member role\> \<role color\>

- Creates a new event.

#### /events open-event \<event name or ID\>

- Opens the given event. This will show the sign-in menu to members.

#### /events close-event \<event name or ID\> [optional: keep-event?] [optional: clear-messages?]

- Ends the given event. This will hide all the channels from members.
- If keep-event is set to True, the event will be archived, otherwise it's channels and roles will be deleted.
- If clear-messages is set to True, when the event is archived, messages in all channels will be deleted.

#### /events reschedule-event \<physical location\> \<start time\> \<end time\> \<timezone\>

- If an event has been archived, it can be reused and rescheduled for a new date using this command.

#### /events remove-event \<event name or ID\>

- Entirely deletes either an active or archived event.
</details>

<details>
<summary>VCMusic</summary>

## VCMusic

### Environment Variable: `ENABLE_VCMUSIC`

In order to function, a google API key with access to YouTube Data API v3 must be set to the `GOOGLE_API` environment variable.

### To create your Google API credentials:

1. Go to the [Google Cloud API]("https://console.cloud.google.com/apis/") site.
1. Create a new project and name it whatever you want.
1. In the [dashboard](https://console.cloud.google.com/apis/dashboard), click the `Enable APIs and Services` and search for `YouTube Data API v3`.
1. Click `Enable` to enable the use of the YouTube API.
1. Keep going back until at your [dashboard](https://console.cloud.google.com/apis/dashboard), and go to the [credentials](https://console.cloud.google.com/apis/credentials) section on the left.
1. Click on `Create Credentials` and then `API key`.
1. Copy the key given. For security, it is recommended that you "restrict key" and only enable `YouTube Data API v3`.

#### /music-admin set-channel \<channel\> [optional: color] [optional: clear-channel] [optional: read-only]

- Sets the channel to define as the music channel.

#### /music play

- Resumes or starts playback.

#### /music pause

- Pauses playback.

#### /music skip-song

- Skips the current song. Stops playback if the last song in the queue.

#### /music shuffle-queue

- Shuffles the current queue.

#### /music add-music

- Opens the dialogue to add one or many songs to the queue.

#### /music view-queue

- Shows the current queue.

#### /music stop

- Stop the current playback.

#### /music volume \<volume\>

- Sets the volume percentage between 0-100

</details>

<details>
<summary>UserRoles</summary>

## UserRoles

### Environment Variable: `ENABLE_USERROLES`

#### /pingable-admin get-config [optional: setting]

- Get the current settings for UserRoles or a specific setting by providing the name.

#### /pingable-admin set-config \<setting\> \<value\>

- Set a specific UserRoles setting to a given value.

#### /pingable create-role \<role-name\>

- Start a poll to create a new user role.

</details>

# TODO

- ~~Implement unimplemented commands in VoiceAdmin and AdminTools cogs.~~
- ~~Implement EventTools cog~~
- ~~Implement AutoRoles cog~~
- ~~Add back functionality of previous bot (eg. Music, PingableRoles, etc.)~~
- Add game deal tracker (DealTracker(?) cog)
- ~~Add proper support for SQLite auto increment primary keys~~
- ~~Add proper use of command groups~~

## Previous extensions to implement

<pre>
✅ Extension implemented either partially or fully.

⏳ Extension currently being implemented not yet ready.

❌ High priority extension not yet implemented.

⚠️ Low priority extension not yet implemented.
</pre>

- [x] AdminCog ✅ Implemented as AdminTools
- [x] DefaultRoleCog ✅ Implemented as AutoRoles
- [x] EventCategoriesCog ✅ Implemented as EventTools
- [x] LogChannelCog ✅ Implementation as LogChannel
- [x] MusicCog ✅ Implemented as VCMusic
- [x] PingableRolesCog ✅ Implementation as UserRoles
- [x] RoleReactCog ✅ Implemented as RoleReact
- [ ] TwitchCog ❌ Announcements precede most livestreams
- [ ] TwitterCog ❌ Needs Twitter API v2 Bearer Token
- [x] VoicemasterCog ✅ Implemented as VoiceAdmin
- [ ] VotingCog ⚠️

# Quick Setup Guide

Requirements needed to run:

- Python 3.8
- Pip
- [A postgres 11 database](https://www.postgresql.org/docs/current/admin.html)
  - If using the `DB_OVERRIDE` environment variable, any valid DB schema for SQLAlchemy can be used by providing the correct schema URI. These can be [found here](https://docs.sqlalchemy.org/en/14/dialects/).

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

# Contributing Guide

If you wish to contribute to this bot please use the following paradigms:

- Ensure that yapf is configured with the configuration defined in `setup.cfg`
  - Optionally also configure flake8 to help with linting
  - This project uses match/case statements, consider using [char101's fork](https://github.com/char101/yapf/releases/tag/v0.31.0) of YAPF until the official fork addresses [the issue](https://github.com/google/yapf/issues/983)
- When adding a new extension consider the following:
  - Create user-facing strings inside of `src/locale/` using the same name as the extension of the filename (eg. for VoiceAdmin.py extension, there exists VoiceAdmin.toml). The strings can then be loaded with `load_cog_strings(__name__)` from `common.io`
  - If your extension should always be enabled, it should be in `extensions/default/`, otherwise it should have an environment variable to toggle it and it should be in `extensions/dynamic/`.
  - Extensions should be modular, meaning that they should be able to be enabled/disabled with hindering the function of other extensions
- Any file loading or IO operations should be defined in `src/common/io.py`
