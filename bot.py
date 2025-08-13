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
intents.message_content = True  # make sure this is enabled in the Developer Portal too
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

# Only your mention lines:
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

    # ===== Robust mention detection =====
    # (1) Standard parsed mentions list
    mentioned = bot.user in message.mentions if bot.user else False

    # (2) Raw fallback: <@ID> and <@!ID> formats
    if not mentioned and bot.user:
        bot_id = bot.user.id
        content = message.content or ""
        if f"<@{bot_id}>" in content or f"<@!{bot_id}>" in content:
            mentioned = True

    if mentioned:
        # Only your custom lines when the bot is @mentioned
        await message.reply(random.choice(MENTION_RESPONSES), mention_author=False)
        return  # don't also do the random reply below

    # ===== Ex
