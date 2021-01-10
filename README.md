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