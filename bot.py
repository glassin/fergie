import os, random, aiohttp, discord, asyncio
from discord.ext import tasks, commands

# ===== ENV =====
TOKEN       = os.getenv("DISCORD_TOKEN")
TENOR_KEY   = os.getenv("TENOR_API_KEY")
CHANNEL_ID  = int(os.getenv("CHANNEL_ID", "0"))
BREAD_EMOJI = os.getenv("BREAD_EMOJI", "🍞")

SEARCH_TERM  = "bread"
RESULT_LIMIT = 20
REPLY_CHANCE = 0.10  # 10% chance to reply to non-mention messages

# ===== DISCORD SETUP =====
intents = discord.Intents.default()
intents.message_content = True  # make sure Message Content Intent is enabled in the Developer Portal
bot = commands.Bot(command_prefix="!", intents=intents)

# ===== CONTENT =====
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

# Mention replies (your custom lines)
MENTION_RESPONSES = [
    "very cheugi",
    "cayuuuuuute",
    "I hate it here!",
    "SEND ME TO THE ER MF!!!",
    "send me monies!!!",
    "*sigh*",
    "*double sigh*",
    "I'm having a horrible day.",
    "oh my gaaaaawwwwww........d",
    "HALP!",
    "LISTEN!",
    "que triste",
    "I've been dying",
    "wen coffee colon cleansing?",
    "skinnie winnie",
    "labooobies",
    "I want a pumpkin cream cold brewwwww",
    "update I want it to be fall already . need cold breeze, sweaters and flared leggings and a cute beanie",
    "and Halloween decor",
    "JONATHAN!",
    "HEAR ME!!!!",
    "UGH!"
]

# ===== UTIL =====
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

# ===== COMMANDS (optional test) =====
@bot.command()
async def ping(ctx):
    await ctx.send("Pong! 🏓")

# ===== EVENTS =====
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    four_hour_post.start()
    six_hour_emoji.start()
    asyncio.create_task(random_daily_money_post())

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # Robust mention detection
    mentioned = False
    if bot.user and bot.user in message.mentions:
        mentioned = True
    elif bot.user:
        bot_id = bot.user.id
        content = message.content or ""
        if f"<@{bot_id}>" in content or f"<@!{bot_id}>" in content:
            mentioned = True

    if mentioned:
        # Random response from your list
        await message.reply(random.choice(MENTION_RESPONSES), mention_author=False)
        return  # don't also do random bread reply

    # Random reply to regular messages
    if random.random() < REPLY_CHANCE:
        gif = await fetch_bread_gif()
        choice = gif if gif else random.choice(BREAD_PUNS)
        await message.reply(choice, mention_author=False)

    await bot.process_commands(message)

# ===== SCHEDULED TASKS =====
@tasks.loop(hours=4)
async def four_hour_post():
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        return
    gif = await fetch_bread_gif()
    text = random.choice([
        random.choice(BREAD_PUNS),
        f"Fresh bread drop! 🥖\n{gif}" if gif else random.choice(BREAD_PUNS),
        f"{random.choice(BREAD_PUNS)}\n{gif}" if gif else random.choice(BREAD_PUNS),
    ])
    await channel.send(text)

@tasks.loop(hours=6)
async def six_hour_emoji():
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await channel.send(BREAD_EMOJI)

# Once per day at a random time
async def random_daily_money_post():
    await bot.wait_until_ready()
    while not bot.is_closed():
        hours_delay = random.randint(0, 23)
        minutes_delay = random.randint(0, 59)
        delay_seconds = hours_delay * 3600 + minutes_delay * 60
        print(f"[MoneyPost] Next post in {hours_delay}h {minutes_delay}m.")
        await asyncio.sleep(delay_seconds)

        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            await channel.send("Someone send me money.  $Sfergielicious for $180")

        # wait to the end of the day and schedule again
        await asyncio.sleep(24 * 3600 - delay_seconds)

# ===== ENTRYPOINT =====
if __name__ == "__main__":
    if not TOKEN or not TENOR_KEY or not CHANNEL_ID:
        raise SystemExit("Please set DISCORD_TOKEN, TENOR_API_KEY and CHANNEL_ID environment variables.")
    bot.run(TOKEN)
