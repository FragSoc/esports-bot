from discord import Client

def init(client: Client):
    if not isinstance(client, Client):
        raise TypeError("Expected type discord.Client, received " + type(client).__name__)
    from . import botState
    botState.client = client
