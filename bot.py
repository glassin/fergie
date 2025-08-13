import os, random, aiohttp, discord, asyncio, time
from collections import defaultdict
from discord.ext import tasks, commands

# ===== ENV =====
TOKEN       = os.getenv("DISCORD_TOKEN")
TENOR_KEY   = os.getenv("TENOR_API_KEY")
CHANNEL_ID  = int(os.getenv("CHANNEL_ID", "0"))
BREAD_EMOJI = os.getenv("BREAD_EMOJI", "🍞")

SEARCH_TERM    = "bread"
RESULT_LIMIT   = 20
REPLY_CHANCE   = 0.10  # 10% chance to reply to non-mention messages
BAGUETTE_PEACH = "🥖🍑"

# ===== DISCORD SETUP =====
intents = discord.Intents.default()
intents.message_content = True  # also enable in Discord Developer Portal → Bot
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

# Extra feral lines (bite line removed earlier)
FERAL_LINES = [
    "I’m about to throw bread crumbs EVERYWHERE",
    "LET ME SCREAM INTO A LOAF"
]

# Reaction emojis (only these)
BRATTY_REACTIONS = ["🤭", "😏", "😢", "😊", "🙄", "💗", "🫶"]

# Double-reply trigger tracking (🥖🍑)
recent_replies = defaultdict(lambda: {"count": 0, "last": 0})
REPLY_WINDOW_SECONDS = 60  # two replies within 60s → 🥖🍑

# ===== SPECIAL MEMBERS (scheduled posts) =====
USER1_ID = 1028310674318839878  # "callate!" twice a day
USER2_ID = 534227493360762891   # "why don't you leave already?!?" twice a day
USER3_ID = 661077262468382761   # 3x/day random from list below

USER3_LINES = [
    "twinnies!!!",
    "girly!",
    "we hate it here r-right girly?",
    "wen girlie wen?!?!"
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
    twice_daily_specific_messages.start()
    thrice_daily_user3.start()

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    replied = False
    mentioned = False

    # --- Robust mention detection ---
    if bot.user and bot.user in message.mentions:
        mentioned = True
    elif bot.user:
        bot_id = bot.user.id
        content = message.content or ""
        if f"<@{bot_id}>" in content or f"<@!{bot_id}>" in content:
            mentioned = True

    # --- Detect if user replied directly to the bot's message (🥖🍑) ---
    if message.reference and message.reference.resolved:
        ref_msg = message.reference.resolved
        if getattr(ref_msg.author, "id", None) == (bot.user.id if bot.user else None):
            now = time.time()
            user_id = message.author.id
            if now - recent_replies[user_id]["last"] > REPLY_WINDOW_SECONDS:
                recent_replies[user_id]["count"] = 0
            recent_replies[user_id]["count"] += 1
            recent_replies[user_id]["last"] = now
            if recent_replies[user_id]["count"] == 2:
                await message.channel.send(BAGUETTE_PEACH)
                recent_replies[user_id]["count"] = 0

    # --- Replies ---
    if mentioned:
        pool = MENTION_RESPONSES + FERAL_LINES
        response = random.choice(pool)
        await message.reply(response, mention_author=False)
        replied = True
    else:
        if random.random() < REPLY_CHANCE:
            gif = await fetch_bread_gif()
            choice = gif if gif else random.choice(BREAD_PUNS)
            await message.reply(choice, mention_author=False)
            replied = True

    # --- Add a random reaction after any reply ---
    if replied:
        try:
            if random.random() < 0.35:
                await message.add_reaction(random.choice(BRATTY_REACTIONS))
        except Exception:
            pass

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
        await asyncio.sleep(24 * 3600 - delay_seconds)

# Twice a day: user1 (oooomph) and user2 (harrrrash)
@tasks.loop(hours=12)
async def twice_daily_specific_messages():
    await bot.wait_until_ready()
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        return
    await channel.send(f"<@{USER1_ID}> oooomph")
    await channel.send(f"<@{USER2_ID}> harrrrash")

# Three times a day: user3 random line
@tasks.loop(hours=8)
async def thrice_daily_user3():
    await bot.wait_until_ready()
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        return
    await channel.send(f"<@{USER3_ID}> {random.choice(USER3_LINES)}")

# ===== ENTRYPOINT =====
if __name__ == "__main__":
    if not TOKEN or not TENOR_KEY or not CHANNEL_ID:
        raise SystemExit("Please set DISCORD_TOKEN, TENOR_API_KEY and CHANNEL_ID environment variables.")
    bot.run(TOKEN)
