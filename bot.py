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
USER1_ID = 1028310674318839878  # oooomph
USER2_ID = 534227493360762891   # harrrrash
USER3_ID = 661077262468382761   # twinnies / girly / etc

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
    "gnaw gnaw gnaw >:3", "hisssss 🐍", "I will destroy you (playfully)",
    "claw claw claw", "REEEEEEEEEEEEEEEE"
]

REACTION_EMOTES = ["🤭", "😏", "😢", "😊", "🙄", "💗", "🫶"]

USER3_LINES = [
    "twinnies!!!",
    "girly!",
    "we hate it here r-right girly?",
    "wen girlie wen?!?!"
]

# Track replies for baguette + peach trigger
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

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # Track reply count
    if message.reference and message.reference.resolved:
        replied_to = message.reference.resolved.author.id
        reply_count[replied_to] = reply_count.get(replied_to, 0) + 1
        if reply_count[replied_to] >= 2:
            await message.channel.send("🥖🍑")
            reply_count[replied_to] = 0

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

# ---- Commands ----
@bot.command(name="cafe", help="Send a random coffee GIF ☕")
async def cafe(ctx, *, term: str = "coffee"):
    query = term if term else "coffee"
    async with ctx.channel.typing():
        gif = await fetch_gif(query)
    await ctx.send(gif if gif else "☕")

# ---- Start ----
if __name__ == "__main__":
    if not TOKEN or not TENOR_KEY or not CHANNEL_ID:
        raise SystemExit("Please set DISCORD_TOKEN, TENOR_API_KEY, and CHANNEL_ID environment variables.")
    bot.run(TOKEN)
