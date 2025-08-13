import os, random, aiohttp, discord, json, asyncio, time, math
from discord.ext import tasks, commands
from urllib.parse import quote_plus
from datetime import date, time as dtime, timezone
from pathlib import Path

TOKEN       = os.getenv("DISCORD_TOKEN")
TENOR_KEY   = os.getenv("TENOR_API_KEY")
CHANNEL_ID  = int(os.getenv("CHANNEL_ID", "0"))
BREAD_EMOJI = os.getenv("BREAD_EMOJI", "🍞")

SEARCH_TERM  = "bread"
RESULT_LIMIT = 20
REPLY_CHANCE = 0.10

# Specific member IDs
USER1_ID = 1028310674318839878  # callate! (twice/day)
USER2_ID = 534227493360762891   # shooo cornman! (twice/day)
USER3_ID = 661077262468382761   # 3x/day random lines
LOBO_ID  = 919405253470871562   # once/day when they post -> "send me money lobo."

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ===================== Bread Economy Settings =====================
BANK_FILE = Path(os.getenv("BREAD_BANK_FILE", "bread_bank.json"))    # storage
TREASURY_MAX = int(os.getenv("TREASURY_MAX", "100000"))              # total supply cap
USER_WALLET_CAP = int(os.getenv("USER_WALLET_CAP", str(TREASURY_MAX // 10)))  # 10% cap (10k)
CLAIM_AMOUNT = int(os.getenv("CLAIM_AMOUNT", "250"))                 # daily claim payout
CLAIM_COOLDOWN_HOURS = int(os.getenv("CLAIM_COOLDOWN_HOURS", "24"))
CLAIM_REQUIREMENT = int(os.getenv("CLAIM_REQUIREMENT", "180"))       # must have >= this saved
DAILY_GIFT_CAP = int(os.getenv("DAILY_GIFT_CAP", "2000"))            # max you can send/day
GIFT_TAX_TIERS = [                                                   # progressive tax
    (1000, 0.05),
    (3000, 0.10),
    (6000, 0.15),
]
GAMBLE_MAX_BET = int(os.getenv("GAMBLE_MAX_BET", "1500"))            # per-bet ceiling
GAMBLE_WIN_PROB = float(os.getenv("GAMBLE_WIN_PROB", "0.485"))       # tiny house edge
# ==================================================================

# ---- Phrase pack (safe; tweak freely) ----
PHRASES = {
    "claim_success": "here's your 250 nikka",
    "claim_gate": "save at least **{need}** first. no savings, no allowance. send me money 💗 $Sfergielicious",
    "claim_cooldown": "not yet. come back in **{hrs}h {mins}m**.",
    "bank_empty": "the bank is empty. tragic. 💀 come back later.",
    "gift_sent": "{giver} ➜ {recv}: **{amount}** sent. para las cariñosas, guey 💗🍆",
    "gift_tax": "({tax} tax to bank)",
    "gift_skim": "(cap skim {skim} back to bank)",
    "gift_cap_left": "daily gift cap is **{cap}**. you can still send **{left}** today.",
    "gift_insufficient": "you only have **{bal}**.",
    "gamble_win": "WOOOOOOO you WON {amount} 🎉 new: **{bal}**",
    "gamble_lose": "LMFAO you lost {amount} nikka 😭 new: **{bal}**",
    "gamble_max": "max you can bet rn is **{maxb}** (bank or cap limit).",
    "half_zero": "you have nothing to take. touch some dough first. 💀",
    "half_taken": "GIMME ALL YOUR MONIES! 😈 enjoy being brokies! took **{taken}** → new: **{bal}**",
    "seed_bank": "Bank refilled by **{added}**. Vault: **{vault}**",
    "seed_user": "Seeded {user} **{give}** → new: **{bal}**",
    "take_bank": "Removed **{amt}** from bank. Vault: **{vault}**",
    "take_user": "Took **{amt}** from {user} → new: **{bal}** (to bank)",
    "setbal_user": "Set {user} to **{bal}** (Δ {delta}; treasury now **{vault}**)",
    "no_funds": "The bank is empty. 💀",
}
# ================================================================

# ---- Hawaii images/GIFs ----
HAWAII_IMAGES = [
    "https://i.postimg.cc/bGdhZDfs/Screenshot-14.png",
    "https://i.postimg.cc/cKjNwxdT/Screenshot-15.png",
    "https://i.postimg.cc/gxgpcy5C/Screenshot-5.png",
    "https://tenor.com/view/eddie-murphy-raw-eddie-swing-eddie-raw-gif-16629597",
]

# ---- Tenor helpers ----
async def fetch_gif(query: str, limit: int = 20):
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
    "JONATHAN!", "UGH!"
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
    "wen girlie wen?!?!",
    "the parasites r-right girly?"
]

# ===== Economy storage & helpers =====
def _now() -> float:
    return time.time()

def _today_key() -> str:
    return date.today().isoformat()

economy_lock = asyncio.Lock()
economy = {
    "treasury": TREASURY_MAX,
    "users": {}  # str(user_id): {balance, last_claim, last_gift_day, gifted_today, _lobo_date}
}

def _load_bank():
    global economy
    if BANK_FILE.exists():
        try:
            economy = json.loads(BANK_FILE.read_text())
            economy.setdefault("treasury", TREASURY_MAX)
            economy.setdefault("users", {})
        except Exception:
            economy = {"treasury": TREASURY_MAX, "users": {}}
    else:
        economy = {"treasury": TREASURY_MAX, "users": {}}

def _save_bank():
    try:
        BANK_FILE.write_text(json.dumps(economy, indent=2))
    except Exception:
        pass

def _user(uid: int):
    suid = str(uid)
    u = economy["users"].get(suid)
    if not u:
        u = {"balance": 0, "last_claim": 0, "last_gift_day": "", "gifted_today": 0}
        economy["users"][suid] = u
    return u

def _fmt_bread(n: int) -> str:
    return f"{n} {BREAD_EMOJI}"

def _cap_wallet(balance_after: int) -> tuple[int, int]:
    if balance_after <= USER_WALLET_CAP:
        return balance_after, 0
    skim = balance_after - USER_WALLET_CAP
    return USER_WALLET_CAP, skim

def _apply_gift_tax(amount: int) -> tuple[int, int]:
    tax = 0
    remaining = amount
    prev_threshold = 0
    for threshold, rate in GIFT_TAX_TIERS:
        if remaining <= 0: break
        portion = max(0, min(remaining, threshold - prev_threshold))
        tax += math.floor(portion * rate)
        remaining -= portion
        prev_threshold = threshold
    if remaining > 0 and GIFT_TAX_TIERS:
        tax += math.floor(remaining * GIFT_TAX_TIERS[-1][1])
    net = amount - tax
    return max(0, net), max(0, tax)

# ---- Events ----
@bot.event
async def on_ready():
    _load_bank()
    print(f"Logged in as {bot.user}")
    four_hour_post.start()
    six_hour_emoji.start()
    user1_twice_daily_fixed.start()
    user2_twice_daily_fixed.start()
    user3_task.start()
    daily_scam_post.start()

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    content = (message.content or "")
    lower = content.lower().strip()

    # --- IMPORTANT: Process commands first (fixes !claim/!bal reliability)
    if content.strip().startswith("!"):
        await bot.process_commands(message)
        return

    # Auto BBL trigger
    if lower == "bbl":
        gif_url = "https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExM2dmMnE4Z2xjdmMwZnN4bmplamMxazFlZTF0Z255MndxZGpqNGdkNyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/PMwewC6fjVkje/giphy.gif"
        await message.channel.send(gif_url)
        return

    # Once/day when LOBO_ID posts
    if message.author.id == LOBO_ID:
        u = _user(LOBO_ID)
        today = _today_key()
        if u.get("_lobo_date") != today:
            await message.channel.send(f"<@{LOBO_ID}> send me money lobo.")
            u["_lobo_date"] = today
            _save_bank()

    # Phrase trigger → :ppeyeroll:
    if "pinche fergie" in lower:
        if message.author.id == USER1_ID:
            reply_options = ["pinche sancho", "wtf do you want now mfer!!!!"]
            await message.reply(random.choice(reply_options), mention_author=False)
        em = None
        if message.guild:
            em = discord.utils.get(message.guild.emojis, name="ppeyeroll")
        await message.channel.send(str(em) if em else "🙄")
        return

    # 🥖🍑 easter egg
    if message.reference and message.reference.resolved:
        replied_to_msg = message.reference.resolved
        if replied_to_msg.author.id == bot.user.id:
            if not hasattr(bot, "_reply_counts"):
                bot._reply_counts = {}
            uid = message.author.id
            bot._reply_counts[uid] = bot._reply_counts.get(uid, 0) + 1
            if bot._reply_counts[uid] >= 2:
                await message.channel.send("🥖🍑")
                bot._reply_counts[uid] = 0

    # Mention → bratty only
    mentioned = False
    if bot.user and (bot.user in message.mentions):
        mentioned = True
    elif bot.user:
        bid = bot.user.id
        if f"<@{bid}>" in content or f"<@!{bid}>" in content:
            mentioned = True

    if mentioned:
        await message.reply(random.choice(BRATTY_LINES), mention_author=False)
        return

    # Random chat sass
    if random.random() < REPLY_CHANCE:
        choice = random.choice([random.choice(BRATTY_LINES),
                                random.choice(FERAL_LINES),
                                random.choice(REACTION_EMOTES)])
        await message.reply(choice, mention_author=False)

# ---- Bread posts & schedules ----
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

@tasks.loop(time=(dtime(hour=10, tzinfo=timezone.utc), dtime(hour=22, tzinfo=timezone.utc)))
async def user1_twice_daily_fixed():
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await channel.send(f"<@{USER1_ID}> callate!")

@tasks.loop(time=(dtime(hour=11, tzinfo=timezone.utc), dtime(hour=23, tzinfo=timezone.utc)))
async def user2_twice_daily_fixed():
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await channel.send(f"<@{USER2_ID}> shooo cornman!")

@tasks.loop(hours=8)
async def user3_task():
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        phrase = random.choice(USER3_LINES)
        await channel.send(f"<@{USER3_ID}> {phrase}")

@tasks.loop(hours=24)
async def daily_scam_post():
    channel = bot.get_channel(CHANNEL_ID)
    if channel and random.random() < 0.7:
        await channel.send("SCAM!!! 🚨🙄💅")

# ================== Economy Commands ==================
def _cooldown_left(last_ts: float, hours: int) -> tuple[int, int]:
    remaining = int(hours * 3600 - (_now() - last_ts))
    if remaining < 0:
        remaining = 0
    hrs = remaining // 3600
    mins = (remaining % 3600) // 60
    return hrs, mins

@bot.command(name="bank", help="Show remaining bread in the bank")
async def bank(ctx):
    async with economy_lock:
        t = economy["treasury"]
    await ctx.send(f"Bank vault: **{_fmt_bread(t)}** remaining.")

@bot.command(name="balance", aliases=["bal", "wallet"], help="See your bread balance (or someone else's)")
async def balance(ctx, member: discord.Member | None = None):
    target = member or ctx.author
    async with economy_lock:
        u = _user(target.id)
    await ctx.send(f"{target.mention} has **{_fmt_bread(u['balance'])}** (cap {USER_WALLET_CAP} {BREAD_EMOJI}).")

@bot.command(name="claim", help=f"Claim daily bread allowance ({CLAIM_AMOUNT} {BREAD_EMOJI}, 24h cd)")
async def claim(ctx):
    uid = ctx.author.id
    async with economy_lock:
        u = _user(uid)
        # require savings floor
        if u["balance"] < CLAIM_REQUIREMENT:
            await ctx.send(f"{ctx.author.mention} " + PHRASES["claim_gate"].format(need=_fmt_bread(CLAIM_REQUIREMENT)))
            return
        # cooldown
        hrs_left, mins_left = _cooldown_left(u["last_claim"], CLAIM_COOLDOWN_HOURS)
        if hrs_left or mins_left:
            await ctx.send(f"{ctx.author.mention} " + PHRASES["claim_cooldown"].format(hrs=hrs_left, mins=mins_left))
            return
        # bank funds
        if economy["treasury"] <= 0:
            await ctx.send(PHRASES["bank_empty"])
            return

        pay = min(CLAIM_AMOUNT, economy["treasury"])
        before = u["balance"]
        new_bal = before + pay
        final_bal, skim = _cap_wallet(new_bal)

        # reduce treasury only by net leaving the bank
        economy["treasury"] -= (pay - skim)
        u["balance"] = final_bal
        u["last_claim"] = _now()
        vault = economy["treasury"]
        _save_bank()

    msg = (
        f"{ctx.author.mention} {PHRASES['claim_success']} "
        f"(paid {_fmt_bread(pay)}) → **new balance: {_fmt_bread(final_bal)}** · "
        f"**bank: {_fmt_bread(vault)}**"
    )
    if skim:
        msg += f" (cap skim {_fmt_bread(skim)} back to bank)"
    await ctx.send(msg)

@bot.command(name="gift", help="Gift bread: !gift @user 25")
async def gift(ctx, member: discord.Member, amount: int):
    if amount <= 0:
        await ctx.send("positive numbers only, banker bae. 🙄")
        return
    if member.id == ctx.author.id:
        await ctx.send("gifting yourself? be serious 😏")
        return

    today = _today_key()
    async with economy_lock:
        giver = _user(ctx.author.id)
        recv  = _user(member.id)
        if giver["last_gift_day"] != today:
            giver["last_gift_day"] = today
            giver["gifted_today"] = 0

        if giver["gifted_today"] + amount > DAILY_GIFT_CAP:
            left = max(0, DAILY_GIFT_CAP - giver["gifted_today"])
            await ctx.send(PHRASES["gift_cap_left"].format(cap=_fmt_bread(DAILY_GIFT_CAP), left=_fmt_bread(left)))
            return
        if giver["balance"] < amount:
            await ctx.send(f"{ctx.author.mention} " + PHRASES["gift_insufficient"].format(bal=_fmt_bread(giver["balance"])))
            return

        net, tax = _apply_gift_tax(amount)
        giver["balance"] -= amount
        recv_after = recv["balance"] + net
        recv_final, skim = _cap_wallet(recv_after)

        economy["treasury"] = min(TREASURY_MAX, economy["treasury"] + tax + skim)
        recv["balance"] = recv_final
        giver["gifted_today"] += amount

        _save_bank()

    parts = [
        PHRASES["gift_sent"].format(giver=ctx.author.mention, recv=member.mention, amount=_fmt_bread(net))
    ]
    if tax:
        parts.append(PHRASES["gift_tax"].format(tax=_fmt_bread(tax)))
    if skim:
        parts.append(PHRASES["gift_skim"].format(skim=_fmt_bread(skim)))
    await ctx.send(" ".join(parts))

@bot.command(name="lb", help="Top 10 richest bread hoarders")
async def lb(ctx):
    async with economy_lock:
        items = [(int(uid), data["balance"]) for uid, data in economy["users"].items()]
    items.sort(key=lambda x: x[1], reverse=True)
    top = items[:10]
    if not top:
        await ctx.send("no bread yet. go touch some dough.")
        return
    lines = []
    for rank, (uid, bal) in enumerate(top, 1):
        user = ctx.guild.get_member(uid) if ctx.guild else None
        name = user.display_name if user else f"User {uid}"
        lines.append(f"{rank}. **{name}** — {_fmt_bread(bal)}")
    await ctx.send("**Bread Leaderboard**\n" + "\n".join(lines))

@bot.command(name="gamble", help="Flip a coin vs the bank: !gamble 100")
async def gamble(ctx, amount: int):
    if amount <= 0:
        await ctx.send("try a positive bet, casino clown. 🙄")
        return

    async with economy_lock:
        u = _user(ctx.author.id)
        if amount > u["balance"]:
            await ctx.send(f"{ctx.author.mention} you only have **{_fmt_bread(u['balance'])}**.")
            return
        max_affordable = min(GAMBLE_MAX_BET, u["balance"])
        if economy["treasury"] < amount:
            max_affordable = min(max_affordable, economy["treasury"])
        if amount > max_affordable:
            await ctx.send(PHRASES["gamble_max"].format(maxb=_fmt_bread(max_affordable)))
            return

        win = (random.random() < GAMBLE_WIN_PROB)
        if win:
            new_bal = u["balance"] + amount
            final_bal, skim = _cap_wallet(new_bal)
            economy["treasury"] -= (amount - skim)
            u["balance"] = final_bal
            text = PHRASES["gamble_win"].format(amount=_fmt_bread(amount), bal=_fmt_bread(final_bal))
            if skim:
                text += f" (cap skim {_fmt_bread(skim)} back to bank)"
        else:
            u["balance"] -= amount
            economy["treasury"] = min(TREASURY_MAX, economy["treasury"] + amount)
            text = PHRASES["gamble_lose"].format(amount=_fmt_bread(amount), bal=_fmt_bread(u["balance"]))

        _save_bank()

    await ctx.send(f"{ctx.author.mention} {text}")

@bot.command(name="half", help="Give the bank half your bread 😈")
async def half(ctx):
    async with economy_lock:
        u = _user(ctx.author.id)
        if u["balance"] <= 0:
            await ctx.send(PHRASES["half_zero"])
            return
        taken = u["balance"] // 2
        u["balance"] -= taken
        economy["treasury"] = min(TREASURY_MAX, economy["treasury"] + taken)
        _save_bank()
        msg = PHRASES["half_taken"].format(taken=_fmt_bread(taken), bal=_fmt_bread(u["balance"]))
    await ctx.send(f"{ctx.author.mention} {msg}")

# ================== Admin Commands ==================
from discord.ext import commands as _admin

@bot.command(name="seed", help="ADMIN: Seed bread to a user or the bank. Usage: !seed @user 500  |  !seed bank 2000")
@_admin.has_permissions(manage_guild=True)
async def seed(ctx, target: str = None, amount: int = None):
    if target is None or amount is None or amount <= 0:
        await ctx.send("Usage: `!seed @user 500` or `!seed bank 2000`")
        return

    if target.lower() == "bank":
        async with economy_lock:
            before = economy["treasury"]
            economy["treasury"] = min(TREASURY_MAX, economy["treasury"] + amount)
            added = economy["treasury"] - before
            _save_bank()
        await ctx.send(PHRASES["seed_bank"].format(added=_fmt_bread(added), vault=_fmt_bread(economy['treasury'])))
        return

    member = ctx.message.mentions[0] if ctx.message.mentions else None
    if not member:
        try:
            member = await ctx.guild.fetch_member(int(target))
        except Exception:
            member = None
    if not member:
        await ctx.send("I couldn't find that user. Mention them or use their ID.")
        return

    async with economy_lock:
        if economy["treasury"] <= 0:
            await ctx.send(PHRASES["no_funds"])
            return
        give = min(amount, economy["treasury"])
        u = _user(member.id)
        new_bal = u["balance"] + give
        final_bal, skim = _cap_wallet(new_bal)
        economy["treasury"] -= (give - skim)
        u["balance"] = final_bal
        _save_bank()

    msg = PHRASES["seed_user"].format(user=member.mention, give=_fmt_bread(give), bal=_fmt_bread(final_bal))
    if skim:
        msg += f" (cap skim {_fmt_bread(skim)} back to bank)"
    await ctx.send(msg)

@seed.error
async def seed_error(ctx, error):
    if isinstance(error, _admin.MissingPermissions):
        await ctx.send("You need **Manage Server** to use this, babe. 💅")
    else:
        await ctx.send("Seed failed. Usage: `!seed @user 500` or `!seed bank 2000`")

@bot.command(name="take", help="ADMIN: Take bread from a user or the bank. Usage: !take @user 100 | !take bank 1000")
@_admin.has_permissions(manage_guild=True)
async def take(ctx, target: str = None, amount: int = None):
    if target is None or amount is None or amount <= 0:
        await ctx.send("Usage: `!take @user 100` or `!take bank 1000`")
        return

    if target.lower() == "bank":
        async with economy_lock:
            amt = min(amount, economy["treasury"])
            economy["treasury"] -= amt  # burn from bank
            _save_bank()
        await ctx.send(PHRASES["take_bank"].format(amt=_fmt_bread(amt), vault=_fmt_bread(economy['treasury'])))
        return

    member = ctx.message.mentions[0] if ctx.message.mentions else None
    if not member:
        try:
            member = await ctx.guild.fetch_member(int(target))
        except Exception:
            member = None
    if not member:
        await ctx.send("I couldn't find that user. Mention them or use their ID.")
        return

    async with economy_lock:
        u = _user(member.id)
        amt = min(amount, u["balance"])
        u["balance"] -= amt
        economy["treasury"] = min(TREASURY_MAX, economy["treasury"] + amt)  # return to bank
        _save_bank()
    await ctx.send(PHRASES["take_user"].format(amt=_fmt_bread(amt), user=member.mention, bal=_fmt_bread(u["balance"])))

@take.error
async def take_error(ctx, error):
    if isinstance(error, _admin.MissingPermissions):
        await ctx.send("You need **Manage Server** to use this, babe. 💅")
    else:
        await ctx.send("Take failed. Usage: `!take @user 100` or `!take bank 1000`")

@bot.command(name="setbal", help="ADMIN: Set a user's exact balance. Usage: !setbal @user 5000")
@_admin.has_permissions(manage_guild=True)
async def setbal(ctx, member: discord.Member = None, amount: int = None):
    if member is None or amount is None or amount < 0:
        await ctx.send("Usage: `!setbal @user 5000`")
        return

    async with economy_lock:
        u = _user(member.id)
        amount = min(amount, USER_WALLET_CAP)  # enforce cap
        delta = amount - u["balance"]
        if delta > 0:
            take = min(delta, economy["treasury"])
            u["balance"] += take
            delta_applied = take
            economy["treasury"] -= take
        else:
            give_back = min(-delta, TREASURY_MAX - economy["treasury"])
            u["balance"] -= give_back
            delta_applied = -give_back
            economy["treasury"] += give_back
        _save_bank()

    await ctx.send(PHRASES["setbal_user"].format(
        user=member.mention,
        bal=_fmt_bread(u["balance"]),
        delta=_fmt_bread(delta_applied),
        vault=_fmt_bread(economy["treasury"])
    ))

# ---- Fun commands ----
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

@bot.command(name="bbl", help="Send the ultimate BBL GIF 💃")
async def bbl(ctx):
    gif_url = "https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExM2dmMnE4Z2xjdmMwZnN4bmplamMxazFlZTF0Z255MndxZGpqNGdkNyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/PMwewC6fjVkje/giphy.gif"
    await ctx.send(gif_url)

@bot.command(name="hawaii", help="Send a random Hawaii pic or Eddie Murphy GIF 🌺")
async def hawaii(ctx):
    await ctx.send(random.choice(HAWAII_IMAGES))

# ---- Start ----
if __name__ == "__main__":
    if not TOKEN or not TENOR_KEY or not CHANNEL_ID:
        raise SystemExit("Please set DISCORD_TOKEN, TENOR_API_KEY, and CHANNEL_ID environment variables.")
    bot.run(TOKEN)
