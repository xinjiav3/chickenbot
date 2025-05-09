import discord
from discord.ext import commands
from collections import defaultdict, deque
import time
import datetime
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import asyncio
from dotenv import load_dotenv
import os

load_dotenv()
TOKEN = os.getenv("CHICKEN_BOT_TOKEN")

analyzer = SentimentIntensityAnalyzer()

user_daily_offenses = defaultdict(list)
# Tracks the number of warnings each user has in the last 24 hours

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Store recent messages per user
user_message_log = defaultdict(lambda: deque(maxlen=5))
warning_counts = defaultdict(int)

SPAM_THRESHOLD = 7  # messages in 10 seconds
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

    # Spam Detection: 7 messages in 10 seconds
    if len(user_message_log[user_id]) == 7:
        timestamps = [msg.created_at.timestamp() for msg in user_message_log[user_id]]
        if timestamps[-1] - timestamps[0] < 10:
            await warn_user(message, "spamming")

        # Harassment message detection
        sentiment = analyzer.polarity_scores(message.content)
        if sentiment["compound"] <= -0.5:  # Adjust threshold as needed
            await warn_user(message, "toxic/harassing language")

    await bot.process_commands(message)

UNMUTE_DELAY = 5 * 60  # 10 minutes in seconds

async def warn_user(message, reason):
    user = message.author
    guild = message.guild
    warning_counts[user.id] += 1

    # Warn in public
    await message.channel.send(f"⚠️ {user.mention}, you are being warned for {reason}.")

    # Format timestamp
    timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    # Logging to #logs
    log_channel = discord.utils.get(guild.text_channels, name="bot-logs")
    if log_channel:
        await log_channel.send(
            f"📝 [{timestamp}] Warning issued to {user.mention} for **{reason}**.\n"
            f"Total warnings: `{warning_counts[user.id]}`"
        )

    # Punishment on limit
    if warning_counts[user.id] >= WARNING_LIMIT:
        muted_role = discord.utils.get(guild.roles, name="Muted")
        now = datetime.datetime.utcnow()
        user_daily_offenses[user.id].append(now)

        # Filter to just today's offenses
        today = now.date()
        recent_offenses = [dt for dt in user_daily_offenses[user.id] if dt.date() == today]

        # Kick if 5 or more offenses in a single day
        if len(recent_offenses) >= 5:
            try:
                await user.kick(reason="5 warnings in one day")
                await message.channel.send(f"👢 {user.mention} has been kicked for repeated infractions.")
                if log_channel:
                    await log_channel.send(
                        f"👢 [{timestamp}] {user.mention} was kicked for reaching 5 warnings in a single day."
                    )
                return  # Stop here so it doesn’t continue to mute after kicking
            except discord.Forbidden:
                await message.channel.send(f"❌ I don't have permission to kick {user.mention}.")
                if log_channel:
                    await log_channel.send(
                        f"❌ [{timestamp}] Tried to kick {user.mention} but lacked permissions."
                    )

        if muted_role:
            # Remove all roles except @everyone
            roles_to_remove = [role for role in user.roles if role.name != "@everyone"]
            await user.remove_roles(*roles_to_remove, reason="Muted for exceeding warning limit")

            # Add the Muted role
            await user.add_roles(muted_role, reason="Exceeded warning limit")
            await message.channel.send(f"🔇 {user.mention} has been muted for repeated offenses.")
            if log_channel:
                await log_channel.send(
                    f"🔇 [{timestamp}] {user.mention} was auto-muted for reaching {WARNING_LIMIT} warnings. Will unmute in 10 minutes."
                )

            # AUTO UNMUTE AFTER DELAY
            await asyncio.sleep(UNMUTE_DELAY)
            await user.remove_roles(muted_role, reason="Auto-unmute after timeout")

            unmute_time = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
            if log_channel:
                await log_channel.send(
                    f"🔊 [{unmute_time}] {user.mention} has been auto-unmuted after 10 minutes."
                )
        else:
            await message.channel.send(f"⚠️ 'Muted' role not found. Cannot auto-mute {user.mention}.")
            if log_channel:
                await log_channel.send(
                    f"⚠️ [{timestamp}] Tried to mute {user.mention} but 'Muted' role was missing."
                )

bot.run(TOKEN)  # Use bot.run to start the bot
