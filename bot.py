import os, random, aiohttp, discord
from discord.ext import tasks, commands
from urllib.parse import quote_plus

TOKEN       = os.getenv("DISCORD_TOKEN")
TENOR_KEY   = os.getenv("TENOR_API_KEY")
CHANNEL_ID  = int(os.getenv("CHANNEL_ID", "0"))
BREAD_EMOJI = os.getenv("BREAD_EMOJI", "🍞")

SEARCH_TERM  = "bread"
RESULT_LIMIT = 20
REPLY_CHANCE = 0.10

# Specific member IDs
USER1_ID = 1028310674318839878  # callate! (twice/day)
USER2_ID = 534227493360762891   # why don't you leave already? (twice/day)
USER3_ID = 661077262468382761   # 3x/day random lines

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ---- Helper Functions ----
async def fetch_gif(query: str, limit: int = 20):
    """Fetch a random GIF for a given search query from Tenor."""
    if not TENOR_KEY:
        return None
    url = f"https://tenor.googleapis.com/v2/search?q={quote_plus(query)}&key={TENOR_KEY}&limit={limit}"
    async with aiohttp.ClientSession() as s:
        async with s.get(url) as r:
            if r.status != 200:
                return None
            data = await r.json()
            items = data.get("results", [])
            if not items:
                return None
            return random.choice(items)["media_formats"]["gif"]["url"]

async def fetch_bread_gif():
    return await fetch_gif(SEARCH_TERM, RESULT_LIMIT)

# ---- Crypto helpers (for !scam) ----
def _fmt_price(p: float) -> str:
    return f"${p:,.2f}"

def _fmt_change(ch: float) -> str:
    arrow = "📈" if ch >= 0 else "📉"
    return f"{arrow} {ch:+.2f}%"

async def fetch_crypto_prices():
    """BTC & ETH (USD) with 24h change via CoinGecko."""
    url = ("https://api.coingecko.com/api/v3/simple/price"
           "?ids=bitcoin,ethereum&vs_currencies=usd&include_24hr_change=true")
    async with aiohttp.ClientSession() as s:
        async with s.get(url, timeout=15) as r:
            if r.status != 200:
                return None
            return await r.json()

# ---- Responses ----
BREAD_PUNS = [
    "I loaf you more than words can say 🍞❤️",
    "You’re the best thing since sliced bread!",
    "Life is what you bake it 🥖",
    "Rye not have another slice?",
    "All you knead is love (and maybe a little butter) 🧈",
    "You’re toast-ally awesome!",
    "Bready or not, here I crumb! 🍞",
    "Let’s get this bread 💪",
    "Some secrets are best kept on the loaf-down."
]

BRATTY_LINES = [
    "very cheugi", "cayuuuuuute", "I hate it here!",
    "SEND ME TO THE ER MF!!!", "send me monies!!!", "*sigh*", "*double sigh*",
    "I'm having a horrible day.", "oh my gaaaaawwwwww........d",
    "HALP!", "LISTEN!", "que triste", "I've been dying",
    "wen coffee colon cleansing?", "skinnie winnie", "labooobies",
    "I want a pumpkin cream cold brewwwww",
    "update I want it to be fall already . need cold breeze, sweaters and flared leggings and a cute beanie and Halloween decor",
    "JONATHAN!", "HEAR ME!!!!", "UGH!"
]

FERAL_LINES = [
    "I’m about to throw bread crumbs EVERYWHERE",
    "LET ME SCREAM INTO A LOAF"
]

REACTION_EMOTES = ["🤭", "😏", "😢", "😊", "🙄", "💗", "🫶"]

USER3_LINES = [
    "twinnies!!!",
    "girly!",
    "we hate it here r-right girly?",
    "wen girlie wen?!?!"
    "the parasites r-right girlie?"
]

# Track replies for baguette + peach trigger (only when replying to the bot)
reply_count = {}

# ---- Events ----
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    four_hour_post.start()
    six_hour_emoji.start()
    user1_task.start()
    user2_task.start()
    user3_task.start()
    daily_scam_post.start()  # daily random "SCAM!!!"

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # 🥖🍑 trigger: only when the user replies to the BOT's message
    if message.reference and message.reference.resolved:
        replied_to_msg = message.reference.resolved
        if replied_to_msg.author.id == bot.user.id:
            uid = message.author.id
            reply_count[uid] = reply_count.get(uid, 0) + 1
            if reply_count[uid] >= 2:
                await message.channel.send("🥖🍑")
                reply_count[uid] = 0

    # Robust mention detection → immediate bratty/feral reply
    mentioned = False
    if bot.user and (bot.user in message.mentions):
        mentioned = True
    elif bot.user:
        bid = bot.user.id
        c = message.content or ""
        if f"<@{bid}>" in c or f"<@!{bid}>" in c:
            mentioned = True

    if mentioned:
        choice = random.choice(BRATTY_LINES + FERAL_LINES)
        await message.reply(choice, mention_author=False)
        await bot.process_commands(message)
        return

    # Random reply with bratty/feral lines or emotes
    if random.random() < REPLY_CHANCE:
        choice = random.choice([
            random.choice(BRATTY_LINES),
            random.choice(FERAL_LINES),
            random.choice(REACTION_EMOTES)
        ])
        await message.reply(choice, mention_author=False)

    await bot.process_commands(message)

# ---- Scheduled Tasks ----
@tasks.loop(hours=4)
async def four_hour_post():
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
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

@tasks.loop(hours=12)
async def user1_task():
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await channel.send(f"<@{USER1_ID}> oooomph")

@tasks.loop(hours=12)
async def user2_task():
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await channel.send(f"<@{USER2_ID}> harrrrash")

@tasks.loop(hours=8)
async def user3_task():
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        phrase = random.choice(USER3_LINES)
        await channel.send(f"<@{USER3_ID}> {phrase}")

# --- Daily Random SCAM Post ---
@tasks.loop(hours=24)
async def daily_scam_post():
    channel = bot.get_channel(CHANNEL_ID)
    if channel and random.random() < 0.7:  # ~70% chance per day
        await channel.send("SCAM!!! 🚨🙄💅")

# ---- Commands ----
@bot.command(name="cafe", help="Send a random coffee GIF ☕")
async def cafe(ctx, *, term: str = "coffee"):
    query = term if term else "coffee"
    async with ctx.channel.typing():
        gif = await fetch_gif(query)
    await ctx.send(gif if gif else "☕")

@bot.command(name="scam", help="Show current BTC & ETH prices (USD, bratty style)")
async def scam(ctx):
    async with ctx.channel.typing():
        data = await fetch_crypto_prices()
    if not data or "bitcoin" not in data or "ethereum" not in data:
        await ctx.send("Ugh 🙄 can't even get the prices rn... this is SO scammy 💅")
        return

    btc = data["bitcoin"]["usd"]
    btc_ch = data["bitcoin"].get("usd_24h_change", 0.0)
    eth = data["ethereum"]["usd"]
    eth_ch = data["ethereum"].get("usd_24h_change", 0.0)

    msg = (
        f"✨ **SCAM ALERT** ✨\n"
        f"BTC is at {_fmt_price(btc)} ({_fmt_change(btc_ch)}) — like… are you KIDDING me?? 😤\n"
        f"ETH is {_fmt_price(eth)} ({_fmt_change(eth_ch)}) — ew… who’s buying this rn??? 🙄\n"
        f"Send me money instead 💗 $Sfergielicious"
    )
    await ctx.send(msg)

# ---- Start ----
if __name__ == "__main__":
    if not TOKEN or not TENOR_KEY or not CHANNEL_ID:
        raise SystemExit("Please set DISCORD_TOKEN, TENOR_API_KEY, and CHANNEL_ID environment variables.")
    bot.run(TOKEN)
