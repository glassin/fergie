import os, random, aiohttp, discord
from discord.ext import tasks, commands

TOKEN       = os.getenv("DISCORD_TOKEN")
TENOR_KEY   = os.getenv("TENOR_API_KEY")
CHANNEL_ID  = int(os.getenv("CHANNEL_ID", "0"))
BREAD_EMOJI = os.getenv("BREAD_EMOJI", "🍞")

SEARCH_TERM  = "bread"
RESULT_LIMIT = 20
REPLY_CHANCE = 0.10

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
    "and Halloween decor"
]

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

async def fetch_bread_gif():
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

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    four_hour_post.start()
    six_hour_emoji.start()
    daily_money_post.start()

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # Respond to mentions
    if bot.user in message.mentions:
        await message.reply(random.choice(MENTION_RESPONSES), mention_author=False)
        return

    # Random bread reply
    if random.random() < REPLY_CHANCE:
        gif = await fetch_bread_gif()
        choice = gif if gif else "🍞"
        await message.reply(choice, mention_author=False)

    await bot.process_commands(message)

@tasks.loop(hours=4)
async def four_hour_post():
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        return
    gif = await fetch_bread_gif()
    text = f"Fresh bread drop! 🥖\n{gif}" if gif else "🍞"
    await channel.send(text)

@tasks.loop(hours=6)
async def six_hour_emoji():
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await channel.send(BREAD_EMOJI)

@tasks.loop(hours=24)
async def daily_money_post():
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await channel.send("Someone send me money.  $Sfergielicious for $180")

if __name__ == "__main__":
    if not TOKEN or not TENOR_KEY or not CHANNEL_ID:
        raise SystemExit("Please set DISCORD_TOKEN, TENOR_API_KEY and CHANNEL_ID environment variables.")
    bot.run(TOKEN)
