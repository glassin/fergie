import os, random, aiohttp, discord
from discord.ext import tasks, commands

# ----- Env -----
TOKEN       = os.getenv("DISCORD_TOKEN")
TENOR_KEY   = os.getenv("TENOR_API_KEY")
CHANNEL_ID  = int(os.getenv("CHANNEL_ID", "0"))
BREAD_EMOJI = os.getenv("BREAD_EMOJI", "🍞")

SEARCH_TERM  = "bread"
RESULT_LIMIT = 20
REPLY_CHANCE = 0.10  # random replies to regular messages (non-mentions)

# ----- Discord Setup -----
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ----- Tenor fetch -----
async def fetch_bread_gif():
    if not TENOR_KEY:
        return None
    url = f"https://tenor.googleapis.com/v2/search?q={SEARCH_TERM}&key={TENOR_KEY}&limit={RESULT_LIMIT}"
    async with aiohttp.ClientSession() as s:
        async with s.get(url) as r:
            if r.status != 200:
                return None
            data = await r.json()
            items = data.get("results", [])
            if not items:
                return None
            return random.choice(items)["media_formats"]["gif"]["url"]

# ----- Content -----
BREAD_PUNS = [
    "I loaf you more than words can say 🍞❤️",
    "You’re the best thing since sliced bread!",
    "Life is what you bake it 🥖",
    "Rye not have another slice?",
    "All you knead is love (and maybe a little butter) 🧈",
    "You’re toast-ally awesome!",
    "Bready or not, here I crumb! 🍞",
    "Let’s get this bread 💪",
    "Some secrets are best kept on the loaf-down.",
]

MENTION_RESPONSES = [
    "very cheugi",
    "cayuuuuuute",
    "I hate it here!",
    "SEND ME TO THE ER MF!!!",
    "send me monies!!!",
    "*sigh*",
    "*double sigh*",
    "I'm having a horrible day.",
    "oh my gaaaaawwwwww........d"
]

# ----- Commands -----
@bot.command()
async def ping(ctx):
    """Test command to check bot responsiveness"""
    print("[LOG] !ping command received")
    await ctx.send("Pong! 🏓 I'm alive and can send messages.")

# ----- Events -----
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    four_hour_post.start()
    six_hour_emoji.start()

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # ===== Mention detection =====
    mentioned = False
    if bot.user and bot.user in message.mentions:
        mentioned = True
    elif bot.user:
        bot_id = bot.user.id
        content = message.content or ""
        if f"<@{bot_id}>" in content or f"<@!{bot_id}>" in content:
            mentioned = True

    if mentioned:
        print(f"[LOG] Mention detected from {message.author} in #{message.channel}")
        try:
            await message.reply(random.choice(MENTION_RESPONSES), mention_author=False)
        except Exception as e:
            print(f"[ERROR] Mention reply failed: {e}")
        return

    # ===== Random bread reply =====
    if random.random() < REPLY_CHANCE:
        print(f"[LOG] Random bread reply triggered for {message.author}")
        gif = await fetch_bread_gif()
        choice = random.choice([
            random.choice(BREAD_PUNS),
            gif if gif else random.choice(BREAD_PUNS),
            (random.choice(BREAD_PUNS) + (f"\n{gif}" if gif else "")),
        ])
        try:
            await message.reply(choice, mention_author=False)
        except Exception as e:
            print(f"[ERROR] Random reply failed: {e}")

    await bot.process_commands(message)

# ----- Scheduled tasks -----
@tasks.loop(hours=4)
async def four_hour_post():
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print("[ERROR] Could not find channel for 4-hour post")
        return
    gif = await fetch_bread_gif()
    text = random.choice([
        random.choice(BREAD_PUNS),
        f"Fresh bread drop! 🥖\n{gif}" if gif else random.choice(BREAD_PUNS),
        f"{random.choice(BREAD_PUNS)}\n{gif}" if gif else random.choice(BREAD_PUNS),
    ])
    print(f"[LOG] Sending 4-hour bread post to #{channel}")
    await channel.send(text)

@tasks.loop(hours=6)
async def six_hour_emoji():
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        print(f"[LOG] Sending bread emoji to #{channel}")
        await channel.send(BREAD_EMOJI)

# ----- Entrypoint -----
if __name__ == "__main__":
    if not TOKEN or not TENOR_KEY or not CHANNEL_ID:
        raise SystemExit("Please set DISCORD_TOKEN, TENOR_API_KEY and CHANNEL_ID environment variables.")
    bot.run(TOKEN)
