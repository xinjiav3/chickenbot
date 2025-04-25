import discord
from discord.ext import commands
from collections import defaultdict, deque
import time

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Store recent messages per user
user_message_log = defaultdict(lambda: deque(maxlen=5))
warning_counts = defaultdict(int)

SPAM_THRESHOLD = 5  # messages in 10 seconds
WARNING_LIMIT = 3

@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")

@bot.event
async def on_message(message):
    if message.author == bot.user or message.author.bot:
        return

    user_id = message.author.id
    user_message_log[user_id].append(message)

    # Spam Detection: 5 messages in 10 seconds
    if len(user_message_log[user_id]) == 5:
        timestamps = [msg.created_at.timestamp() for msg in user_message_log[user_id]]
        if timestamps[-1] - timestamps[0] < 10:
            await warn_user(message, "spamming")

        # Repetitive message detection
        contents = [msg.content.lower() for msg in user_message_log[user_id]]
        if len(set(contents)) == 1 and contents[0] != "":
            await warn_user(message, "repetitive/harassing behavior")

    await bot.process_commands(message)

async def warn_user(message, reason):
    user = message.author
    warning_counts[user.id] += 1
    await message.channel.send(f"⚠️ {user.mention}, you are being warned for {reason}.")

    if warning_counts[user.id] >= WARNING_LIMIT:
        await message.channel.send(f"🚫 {user.mention} has exceeded the warning limit and may be muted/kicked (not implemented).")

bot.run("CHICKEN_BOT_TOKEN")
