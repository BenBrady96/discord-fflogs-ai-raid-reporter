import os
import discord
from dotenv import load_dotenv
from discord.ext import commands

# Load environment variables
load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')

# Define bot intents
intents = discord.Intents.default()
intents.message_content = True

# Initialise the bot
bot = commands.Bot(command_prefix='!', intents=intents)


@bot.event
async def on_ready():
    """Event triggered when the bot has successfully connected to Discord."""
    print(f'Logged in as {bot.user.name} (ID: {bot.user.id})', flush=True)

    # Load the Raid Reporter cog
    try:
        await bot.load_extension('cogs.raid_reporter')
        print("Loaded extension: raid_reporter", flush=True)
    except Exception as e:
        print(f"Failed to load extension raid_reporter: {e}", flush=True)

    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)", flush=True)
    except Exception as e:
        print(f"Error syncing commands: {e}", flush=True)

    print('------', flush=True)


@bot.hybrid_command(name="ping", description="Check the bot's latency")
async def ping(ctx):
    """Simple health check command."""
    await ctx.send(f'Pong! Latency: {round(bot.latency * 1000)}ms')


if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("Error: DISCORD_TOKEN not found. Check your .env file.")
