import os, random, aiohttp, discord, json, asyncio, time, math
from discord.ext import tasks, commands
from urllib.parse import quote_plus
from datetime import date, datetime, timedelta, time as dtime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

TOKEN       = os.getenv("DISCORD_TOKEN")
TENOR_KEY   = os.getenv("TENOR_API_KEY")
CHANNEL_ID  = int(os.getenv("CHANNEL_ID", "0"))
BREAD_EMOJI = os.getenv("BREAD_EMOJI", "🍞")

SEARCH_TERM  = "bread"
RESULT_LIMIT = 20
REPLY_CHANCE = 0.10

# Specific member IDs
USER1_ID = 1028310674318839878
USER2_ID = 534227493360762891
USER3_ID = 661077262468382761
LOBO_ID  = 919405253470871562

# Airdrop manager (manual trigger)
AIRDROP_MANAGER_ID = 939225086341296209

# ---------- Casino channel restriction ----------
GAMBLE_CHANNEL_ID = 1405320084028784753
def _is_gamble_channel(ch_id: int) -> bool:
    return ch_id == GAMBLE_CHANNEL_ID
# -----------------------------------------------

# ---------- Jump scare (global) ----------
JUMPSCARE_TRIGGER = "concha"
JUMPSCARE_IMAGE_URL = "https://preview.redd.it/66wjyydtpwe01.jpg?width=640&crop=smart&auto=webp&s=d20129184b19b41e455ba9c66715e2ab496b9b49"
JUMPSCARE_COOLDOWN_SECONDS = 90  # per-user cooldown
JUMPSCARE_EMOTE_TEXT = "<:monkagiga:1131711987794063511>"
# ---------------------------------------

# ---------- Kewchie (Kali Uchis) ----------
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_PLAYLIST_ID = os.getenv("SPOTIFY_PLAYLIST_ID", "6l190qy5x9xY8Uk3bb2FYl")
SPOTIFY_MARKET = os.getenv("SPOTIFY_MARKET", "US")
KEWCHIE_CHANNEL_ID = int(os.getenv("KEWCHIE_CHANNEL_ID", "1131573379577675826"))
# -----------------------------------------

# ---------- Fit (random Pinterest-like pics) ----------
FIT_CHANNEL_ID = int(os.getenv("FIT_CHANNEL_ID", "1273436116699058290"))
SLAP_PEACH_EMOTE = "<a:slap_peach:1227392416617730078>"
SCISSORS_EMOJI = "✂️"
FIT_IMAGE_URLS = [
    "https://cdn.discordapp.com/attachments/1405470635844435968/1405470866879414323/pinterest_681169512428877550.png",
    "https://cdn.discordapp.com/attachments/1405470635844435968/1405470867483525140/pinterest_681169512428917172.jpg",
    "https://cdn.discordapp.com/attachments/1405470635844435968/1405470867810422854/pinterest_681169512428917179.jpg",
    "https://cdn.discordapp.com/attachments/1405470635844435968/1405470868087373895/pinterest_681169512428919577.jpg",
]
# -----------------------------------------------

# ---------- Bonk Papo (3 random times/day at USER1) ----------
BONK_MESSAGE = (
    "stop being horny papo! bad papo! "
    "<a:bonk_papo:1216928539413188788><a:bonk_papo:1216928539413188788><a:bonk_papo:1216928539413188788>"
)
# -------------------------------------------------------------

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # needed for daily member sweep
bot = commands.Bot(command_prefix="!", intents=intents)

# ===================== Bread Economy Settings =====================
BANK_FILE = Path(os.getenv("BREAD_BANK_FILE", "bread_bank.json"))
TREASURY_MAX = int(os.getenv("TREASURY_MAX", "500000"))              # total supply cap
USER_WALLET_CAP = int(os.getenv("USER_WALLET_CAP", str(TREASURY_MAX // 10)))  # wallet cap = 10% of treasury
CLAIM_AMOUNT = int(os.getenv("CLAIM_AMOUNT", "250"))                 # daily payout
CLAIM_COOLDOWN_HOURS = int(os.getenv("CLAIM_COOLDOWN_HOURS", "24"))
CLAIM_REQUIREMENT = int(os.getenv("CLAIM_REQUIREMENT", "180"))       # for manual !claim
DAILY_GIFT_CAP = int(os.getenv("DAILY_GIFT_CAP", "2000"))
GIFT_TAX_TIERS = [(1000,0.05),(3000,0.10),(6000,0.15)]
GAMBLE_MAX_BET = int(os.getenv("GAMBLE_MAX_BET", "1500"))
# Base coin win chance is not 50/50 anymore; we vary by bet size and jackpot path
BASE_ROLL_WIN_PROB = float(os.getenv("BASE_ROLL_WIN_PROB", "0.46"))
INACTIVE_WINDOW_DAYS = int(os.getenv("INACTIVE_WINDOW_DAYS", "7"))   # penalty window (days, default 7)
PENALTY_IMAGE = "https://i.postimg.cc/9fkgRMC0/nailz.jpg"
JACKPOT_IMAGE = "https://i.postimg.cc/9fkgRMC0/nailz.jpg"
# ==================================================================

# ---- Phrase pack ----
PHRASES = {
    "claim_success": "here's your 250 nikka",
    "claim_gate": "save at least **{need}** first. no savings, no allowance. send me money 💗 $fergielicious",
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
    "seed_bank": "Bank refilled by **{added}**. Vault: **{vault}**",
    "seed_user": "Seeded {user} **{give}** → new: **{bal}**",
    "take_bank": "Removed **{amt}** from bank. Vault: **{vault}**",
    "take_user": "Took **{amt}** from {user} → new: **{bal}** (to bank)",
    "setbal_user": "Set {user} to **{bal}** (Δ {delta}; treasury now **{vault}**)",
    "no_funds": "The bank is empty. 💀",
    "penalty": "got my nailz done girlies. ty for the monies!!! hahaha"
}

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

# ---- Chat lines ----
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
    "MMMMM"
]

BRATTY_LINES = [
    "very cheugi", "cayuuuuuute", "I hate it here!",
    "SEND ME TO THE ER MF!!!", "send me monies!!!", "*sigh*", "*double sigh*",
    "I'm having a horrible day.", "oh my gaaaaawwwwww........d",
    "HALP!", "LISTEN!", "que triste", "I've been dying",
    "wen coffee colon cleansing?", "skinnie winnie", "labooobies",
    "I want a pumpkin cream cold brewwwww",
    "update I want it to be fall already . need cold breeze, sweaters and flared leggings and a cute beanie and Halloween decor",
    "JONATHAN!", "UGH!", "MMMMM", "was it tasty?", "LMFAO I CANT", "AAAAAAAAAAAAAAAA",
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
    "the parasites r-right girly?",
    "girl so confusing",
    "omg sancho is soooooo annoying",
    "ATTACK GIRLIE!",
]

# ===== Economy storage & helpers =====
def _now() -> float:
    return time.time()

def _today_key() -> str:
    return date.today().isoformat()

economy_lock = asyncio.Lock()
economy = {
    "treasury": TREASURY_MAX,
    "users": {},  # str(user_id): {balance, last_claim, last_gift_day, gifted_today, last_active, _lobo_date}
    "_last_airdrop_date": ""
}

def _load_bank():
    global economy
    if BANK_FILE.exists():
        try:
            economy = json.loads(BANK_FILE.read_text())
            economy.setdefault("treasury", TREASURY_MAX)
            economy.setdefault("users", {})
            economy.setdefault("_last_airdrop_date", "")
        except Exception:
            economy = {"treasury": TREASURY_MAX, "users": {}, "_last_airdrop_date": ""}
    else:
        economy = {"treasury": TREASURY_MAX, "users": {}, "_last_airdrop_date": ""}

def _save_bank():
    try:
        BANK_FILE.write_text(json.dumps(economy, indent=2))
    except Exception:
        pass

def _user(uid: int):
    suid = str(uid)
    u = economy["users"].get(suid)
    if not u:
        u = {
            "balance": 0,
            "last_claim": 0,
            "last_gift_day": "",
            "gifted_today": 0,
            "last_active": 0.0
        }
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

def _mark_active(uid: int):
    _user(uid)["last_active"] = _now()

# ---- Spotify helpers ----
_spotify_token = {"access_token": None, "expires_at": 0}

async def _get_spotify_token():
    # cached token
    if _spotify_token["access_token"] and _now() < _spotify_token["expires_at"] - 30:
        return _spotify_token["access_token"]

    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        return None

    data = {
        "grant_type": "client_credentials",
        "client_id": SPOTIFY_CLIENT_ID,
        "client_secret": SPOTIFY_CLIENT_SECRET
    }
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post("https://accounts.spotify.com/api/token", data=data, timeout=15) as r:
                if r.status != 200:
                    return None
                js = await r.json()
                _spotify_token["access_token"] = js.get("access_token")
                _spotify_token["expires_at"] = _now() + int(js.get("expires_in", 3600))
                return _spotify_token["access_token"]
    except Exception:
        return None

async def _fetch_playlist_tracks(playlist_id: str) -> list[str]:
    token = await _get_spotify_token()
    if not token:
        return []
    headers = {"Authorization": f"Bearer {token}"}
    params = {"market": SPOTIFY_MARKET, "limit": 100}
    url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
    tracks = []
    try:
        async with aiohttp.ClientSession() as s:
            while url:
                async with s.get(url, headers=headers, params=params, timeout=15) as r:
                    if r.status != 200:
                        return tracks
                    data = await r.json()
                    for item in data.get("items", []):
                        t = item.get("track") or {}
                        if t and not t.get("is_local") and t.get("id"):
                            tracks.append(f"https://open.spotify.com/track/{t['id']}")
                    # pagination
                    url = data.get("next")
                    params = None  # next already includes query
    except Exception:
        pass
    return tracks

# ============ Daily Allowance Helper (used by task + manual cmd) ============
async def _run_daily_allowance(channel: discord.TextChannel) -> bool:
    """Runs the daily allowance + inactivity penalties, saves, and stamps today's date."""
    if not channel or not channel.guild:
        return False

    guild = channel.guild
    utc_now = _now()
    inactive_cutoff = utc_now - INACTIVE_WINDOW_DAYS * 86400
    changed = False

    async with economy_lock:
        for m in guild.members:
            if m.bot:
                continue
            u = _user(m.id)

            # 1) Daily allowance
            if economy["treasury"] > 0:
                pay = min(CLAIM_AMOUNT, economy["treasury"])
                new_bal = u["balance"] + pay
                final_bal, skim = _cap_wallet(new_bal)
                economy["treasury"] -= max(0, (pay - skim))
                u["balance"] = final_bal
                changed = True

            # 2) Inactivity penalty (no roll/putasos in the last N days)
            last_active = u.get("last_active", 0.0)
            if last_active == 0.0 or last_active < inactive_cutoff:
                if u["balance"] > 0:
                    taken = u["balance"] // 2
                    if taken > 0:
                        u["balance"] -= taken
                        economy["treasury"] = min(TREASURY_MAX, economy["treasury"] + taken)
                        changed = True
                        try:
                            await channel.send(f"{m.mention} {PHRASES['penalty']}\n{PENALTY_IMAGE}")
                        except Exception:
                            pass

        economy["_last_airdrop_date"] = _today_key()
        if changed:
            _save_bank()

    return True

# ---- Random times helpers (PT-based) ----
def _pick_two_random_times_today_10_to_22_PT():
    tz = ZoneInfo("America/Los_Angeles")
    today = datetime.now(tz=tz).date()
    start = datetime.combine(today, dtime(hour=10, tzinfo=tz))
    end   = datetime.combine(today, dtime(hour=22, tzinfo=tz))
    def rand_dt():
        delta_minutes = int((end - start).total_seconds() // 60)
        offset = random.randint(0, delta_minutes)
        return (start + timedelta(minutes=offset)).astimezone(timezone.utc).replace(second=0, microsecond=0)
    t1 = rand_dt()
    t2 = rand_dt()
    while abs((t2 - t1).total_seconds()) < 300:  # ensure at least 5 min apart
        t2 = rand_dt()
    return sorted([t1, t2])

def _pick_three_random_times_today_10_to_22_PT():
    tz = ZoneInfo("America/Los_Angeles")
    today = datetime.now(tz=tz).date()
    start = datetime.combine(today, dtime(hour=10, tzinfo=tz))
    end   = datetime.combine(today, dtime(hour=22, tzinfo=tz))
    def rand_dt():
        delta_minutes = int((end - start).total_seconds() // 60)
        offset = random.randint(0, delta_minutes)
        return (start + timedelta(minutes=offset)).astimezone(timezone.utc).replace(second=0, microsecond=0)
    picks = sorted({rand_dt() for _ in range(3)})
    while len(picks) < 3:
        picks.add(rand_dt())
        picks = sorted(picks)
    # Make sure they aren't too close to each other
    ok = False
    while not ok:
        ok = True
        for i in range(1, len(picks)):
            if abs((picks[i] - picks[i-1]).total_seconds()) < 600:
                ok = False
                picks[i] = rand_dt()
        picks = sorted(picks)
    return picks

# ---- Events ----
@bot.event
async def on_ready():
    _load_bank()
    if not hasattr(bot, "_js_last"):
        bot._js_last = {}  # user_id -> last jumpscare trigger time (seconds)

    # Kewchie scheduling state
    if not hasattr(bot, "_kewchie_times"):
        bot._kewchie_times = []
        bot._kewchie_posted = set()

    # Fit daily scheduling state
    if not hasattr(bot, "_fit_time"):
        bot._fit_time = None
        bot._fit_posted = False

    # Bonk Papo scheduling state
    if not hasattr(bot, "_bonk_times"):
        bot._bonk_times = []
        bot._bonk_posted = set()

    print(f"Logged in as {bot.user}")
    four_hour_post.start()
    six_hour_emoji.start()
    user1_twice_daily_fixed.start()
    user2_twice_daily_fixed.start()
    user3_task.start()
    daily_scam_post.start()
    daily_auto_allowance.start()  # 8am PT allowance + penalties
    kewchie_daily_scheduler.start()  # random twice-daily songs
    fit_daily_scheduler.start()      # one random fit pic daily
    bonk_papo_scheduler.start()      # three random bonk posts daily

# ---- Kewchie random twice daily scheduler ----
@tasks.loop(minutes=1)
async def kewchie_daily_scheduler():
    now_utc = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    if (not bot._kewchie_times) or (bot._kewchie_times[0].date() != now_utc.date()):
        bot._kewchie_times = _pick_two_random_times_today_10_to_22_PT()
        bot._kewchie_posted = set()

    for t in bot._kewchie_times:
        key = ("kewchie", t.isoformat())
        if now_utc == t and key not in bot._kewchie_posted:
            channel = bot.get_channel(KEWCHIE_CHANNEL_ID)
            if channel:
                links = await _fetch_playlist_tracks(SPOTIFY_PLAYLIST_ID)
                if links:
                    await channel.send(random.choice(links))
                else:
                    await channel.send("Playlist isn't available right now 😭")
            bot._kewchie_posted.add(key)

@kewchie_daily_scheduler.before_loop
async def _wait_bot_ready_kewchie():
    await bot.wait_until_ready()

# ---- Fit daily one-time scheduler ----
@tasks.loop(minutes=1)
async def fit_daily_scheduler():
    now_utc = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    # pick a random time once per day (between 10:00 and 22:00 PT)
    tz = ZoneInfo("America/Los_Angeles")
    today_pt = datetime.now(tz=tz).date()
    if (bot._fit_time is None) or (bot._fit_time.astimezone(tz).date() != today_pt):
        # pick a random time
        start = datetime.combine(today_pt, dtime(hour=10, tzinfo=tz))
        end   = datetime.combine(today_pt, dtime(hour=22, tzinfo=tz))
        delta_minutes = int((end - start).total_seconds() // 60)
        offset = random.randint(0, delta_minutes)
        bot._fit_time = (start + timedelta(minutes=offset)).astimezone(timezone.utc).replace(second=0, microsecond=0)
        bot._fit_posted = False

    if not bot._fit_posted and now_utc == bot._fit_time:
        channel = bot.get_channel(FIT_CHANNEL_ID)
        if channel and FIT_IMAGE_URLS:
            url = random.choice(FIT_IMAGE_URLS)
            msg = f"OMFG look at this one girlie!!! we neeeeeeeeed! 💗"
            sent = await channel.send(url)
            await channel.send(msg)

            # listen for USER3 within 20s
            def check(m: discord.Message):
                return (
                    m.author.id == USER3_ID and
                    m.channel.id == channel.id and
                    m.created_at > sent.created_at
                )
            try:
                reply = await bot.wait_for("message", timeout=20, check=check)
                # respond with slap peach + follow-up line
                await channel.send(
                    f"{SLAP_PEACH_EMOTE} you know you'd look good in this girlie! you go girl! {SCISSORS_EMOJI}"
                )
            except asyncio.TimeoutError:
                pass

        bot._fit_posted = True

@fit_daily_scheduler.before_loop
async def _wait_bot_ready_fit():
    await bot.wait_until_ready()

# ---- Bonk Papo 3× daily scheduler ----
@tasks.loop(minutes=1)
async def bonk_papo_scheduler():
    now_utc = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    tz = ZoneInfo("America/Los_Angeles")
    today_pt = datetime.now(tz=tz).date()
    if (not bot._bonk_times) or (bot._bonk_times[0].astimezone(tz).date() != today_pt):
        bot._bonk_times = _pick_three_random_times_today_10_to_22_PT()
        bot._bonk_posted = set()

    for t in bot._bonk_times:
        key = ("bonk", t.isoformat())
        if now_utc == t and key not in bot._bonk_posted:
            channel = bot.get_channel(CHANNEL_ID)
            if channel:
                await channel.send(f"<@{USER1_ID}> {BONK_MESSAGE}")
            bot._bonk_posted.add(key)

@bonk_papo_scheduler.before_loop
async def _wait_bot_ready_bonk():
    await bot.wait_until_ready()

# ---- Messages ----
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    content = (message.content or "")
    lower = content.lower().strip()

    # Process commands first
    if content.strip().startswith("!"):
        await bot.process_commands(message)
        return

    # Global jump scare trigger (image only, then creepy line), per-user cooldown
    if JUMPSCARE_TRIGGER in lower:
        now = _now()
        last = getattr(bot, "_js_last", {}).get(message.author.id, 0)
        if now - last >= JUMPSCARE_COOLDOWN_SECONDS:
            await message.channel.send(JUMPSCARE_IMAGE_URL)
            await message.channel.send(f"the parasites!!! {JUMPSCARE_EMOTE_TEXT}")
            bot._js_last[message.author.id] = now
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

    # Special: always reply to USER3_ID with a USER3_LINES phrase (100%),
    # with a 20% chance to append one of the REACTION_EMOTES
    if message.author.id == USER3_ID:
        phrase = random.choice(USER3_LINES)
        if random.random() < 0.20:
            phrase = f"{phrase} {random.choice(REACTION_EMOTES)}"
        await message.reply(phrase, mention_author=False)
        return

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

    # Random chat sass (global)
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

# ======== Daily auto allowance + inactivity penalties (8am PT) ========
@tasks.loop(time=dtime(hour=8, tzinfo=ZoneInfo("America/Los_Angeles")))
async def daily_auto_allowance():
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        return
    # avoid double-run if already processed today (manually or via task)
    today = _today_key()
    if economy.get("_last_airdrop_date") == today:
        return
    await _run_daily_allowance(channel)

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

@bot.command(name="claim", help=f"Claim daily bread allowance manually ({CLAIM_AMOUNT} {BREAD_EMOJI}, 24h cd)")
async def claim(ctx):
    uid = ctx.author.id
    async with economy_lock:
        u = _user(uid)
        if u["balance"] < CLAIM_REQUIREMENT:
            await ctx.send(f"{ctx.author.mention} " + PHRASES["claim_gate"].format(need=_fmt_bread(CLAIM_REQUIREMENT)))
            return
        hrs_left, mins_left = _cooldown_left(u["last_claim"], CLAIM_COOLDOWN_HOURS)
        if hrs_left or mins_left:
            await ctx.send(f"{ctx.author.mention} " + PHRASES["claim_cooldown"].format(hrs=hrs_left, mins=mins_left))
            return
        if economy["treasury"] <= 0:
            await ctx.send(PHRASES["bank_empty"])
            return

        pay = min(CLAIM_AMOUNT, economy["treasury"])
        new_bal = u["balance"] + pay
        final_bal, skim = _cap_wallet(new_bal)

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
        # NOTE: gifting no longer updates last_active (only roll/putasos do)

        _save_bank()

    parts = [PHRASES["gift_sent"].format(giver=ctx.author.mention, recv=member.mention, amount=_fmt_bread(net))]
    if tax: parts.append(PHRASES["gift_tax"].format(tax=_fmt_bread(tax)))
    if skim: parts.append(PHRASES["gift_skim"].format(skim=_fmt_bread(skim)))
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

@bot.command(name="richlist", help="Alias of !lb")
async def richlist(ctx):
    await lb(ctx)

# ---------- Smarter roll (spicy odds) ----------
def _resolve_roll_amount(u_balance: int, arg: str | int) -> int:
    if isinstance(arg, int):
        return max(0, arg)
    s = str(arg).lower()
    if s == "all":
        return u_balance
    if s == "half":
        return u_balance // 2
    try:
        return max(0, int(s))
    except Exception:
        return 0

@bot.command(name="roll", help="Bet vs the bank: !roll 100 | !roll all | !roll half (jackpot on ALL)")
async def roll(ctx, amount: str):
    if not _is_gamble_channel(ctx.channel.id):
        await ctx.send(f"Casino floor is only open in <#{GAMBLE_CHANNEL_ID}>.")
        return

    async with economy_lock:
        u = _user(ctx.author.id)
        bet = _resolve_roll_amount(u["balance"], amount)
        if bet <= 0:
            await ctx.send("try a positive bet, casino clown. 🙄")
            return
        if bet > u["balance"]:
            await ctx.send(f"{ctx.author.mention} you only have **{_fmt_bread(u['balance'])}**.")
            return
        # cap and bank constraint
        max_affordable = min(GAMBLE_MAX_BET, u["balance"])
        if economy["treasury"] < bet:
            max_affordable = min(max_affordable, economy["treasury"])
        if bet > max_affordable:
            await ctx.send(PHRASES["gamble_max"].format(maxb=_fmt_bread(max_affordable)))
            return

        # Win probabilities by size (spicy but fair-ish)
        frac = bet / max(1, USER_WALLET_CAP)
        win_prob = BASE_ROLL_WIN_PROB
        if frac <= 0.05:      # tiny bet
            win_prob += 0.05   # ~51%
        elif frac >= 0.5:     # very large bet
            win_prob -= 0.06   # ~40%

        jackpot_hit = False
        jackpot_mult = 1

        # JACKPOT path only on "all"
        if isinstance(amount, str) and amount.lower() == "all":
            # ~0.5% giga jackpot (x15), else ~2% mini (x3)
            r = random.random()
            if r < 0.005:
                jackpot_hit = True
                jackpot_mult = 15
            elif r < 0.025:
                jackpot_hit = True
                jackpot_mult = 3

        if jackpot_hit:
            payout = bet * (jackpot_mult - 1)  # additional gain
            available_from_bank = min(economy["treasury"], payout)
            new_bal = u["balance"] + available_from_bank
            final_bal, skim = _cap_wallet(new_bal)
            paid_from_bank = (final_bal - u["balance"]) + skim
            economy["treasury"] -= max(0, paid_from_bank - skim)
            u["balance"] = final_bal
            _mark_active(ctx.author.id)
            _save_bank()
            await ctx.send(
                f"💥 JACKPOT x{jackpot_mult}! {ctx.author.mention} just exploded the oven for **{_fmt_bread(min(payout, available_from_bank))}**!\n"
                f"new: **{_fmt_bread(u['balance'])}**\n{JACKPOT_IMAGE}"
            )
            return

        # normal outcome
        win = (random.random() < win_prob)
        if win:
            new_bal = u["balance"] + bet
            final_bal, skim = _cap_wallet(new_bal)
            economy["treasury"] -= (bet - skim)
            u["balance"] = final_bal
            text = PHRASES["gamble_win"].format(amount=_fmt_bread(bet), bal=_fmt_bread(final_bal))
            if skim:
                text += f" (cap skim {_fmt_bread(skim)} back to bank)"
        else:
            u["balance"] -= bet
            economy["treasury"] = min(TREASURY_MAX, economy["treasury"] + bet)
            text = PHRASES["gamble_lose"].format(amount=_fmt_bread(bet), bal=_fmt_bread(u["balance"]))
        _mark_active(ctx.author.id)
        _save_bank()
    await ctx.send(f"{ctx.author.mention} {text}")

@bot.command(name="putasos", help="Try to rob someone: !putasos @user (low success, big fail penalty)")
async def putasos(ctx, member: discord.Member):
    if not _is_gamble_channel(ctx.channel.id):
        await ctx.send(f"Casino floor is only open in <#{GAMBLE_CHANNEL_ID}>.")
        return

    if member.id == ctx.author.id:
        await ctx.send("stealing from yourself? iconic, but no.")
        return
    if member.bot:
        await ctx.send("you can’t rob bots. they have no pockets.")
        return

    SUCCESS_CHANCE = 0.15
    STEAL_PCT_MIN, STEAL_PCT_MAX = 0.10, 0.25   # 10–25% of victim on success
    FAIL_LOSE_PCT = 0.12                        # thief loses 12% of own balance to bank

    async with economy_lock:
        thief = _user(ctx.author.id)
        victim = _user(member.id)

        if thief["balance"] <= 0:
            await ctx.send("you’re broke. go touch some dough first.")
            return
        if victim["balance"] <= 0:
            await ctx.send("they’re broke. pick a richer target.")
            return

        if random.random() < SUCCESS_CHANCE:
            steal_pct = random.uniform(STEAL_PCT_MIN, STEAL_PCT_MAX)
            take = max(1, int(victim["balance"] * steal_pct))
            victim["balance"] -= take
            new_bal = thief["balance"] + take
            final_bal, skim = _cap_wallet(new_bal)
            thief["balance"] = final_bal
            economy["treasury"] = min(TREASURY_MAX, economy["treasury"] + skim)
            _mark_active(ctx.author.id)
            _save_bank()
            msg = f"successful heist 😈 you stole **{_fmt_bread(take)}** from {member.mention} → new: **{_fmt_bread(thief['balance'])}**"
            if skim:
                msg += f" (cap skim {_fmt_bread(skim)} back to bank)"
            await ctx.send(f"{ctx.author.mention} {msg}")
        else:
            loss = max(1, int(thief["balance"] * FAIL_LOSE_PCT))
            thief["balance"] -= loss
            economy["treasury"] = min(TREASURY_MAX, economy["treasury"] + loss)
            _mark_active(ctx.author.id)
            _save_bank()
            await ctx.send(f"{ctx.author.mention} got caught 💀 lost **{_fmt_bread(loss)}** to the bank. new: **{_fmt_bread(thief['balance'])}**")

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
        economy["treasury"] = min(TREASURY_MAX, economy["treasury"] + amt)
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
        amount = min(amount, USER_WALLET_CAP)
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
        f"Send me money instead 💗 $fergielicious"
    )
    await ctx.send(msg)

@bot.command(name="bbl", help="Send the ultimate BBL GIF 💃")
async def bbl(ctx):
    gif_url = "https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExM2dmMnE4Z2xjdmMwZnN4bmplamMxazFlZTF0Z255MndxZGpqNGdkNyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/PMwewC6fjVkje/giphy.gif"
    await ctx.send(gif_url)

@bot.command(name="hawaii", help="Send a random Hawaii pic or Eddie Murphy GIF 🌺")
async def hawaii(ctx):
    await ctx.send(random.choice(HAWAII_IMAGES))

# ---- Fit command ----
@bot.command(name="fit", help="Post a random fit pic in the fit channel")
async def fit(ctx):
    if ctx.channel.id != FIT_CHANNEL_ID:
        await ctx.send(f"Use this in <#{FIT_CHANNEL_ID}>")
        return
    if not FIT_IMAGE_URLS:
        await ctx.send("No pics yet 😭")
        return
    url = random.choice(FIT_IMAGE_URLS)
    msg1 = await ctx.send(url)
    await ctx.send("OMFG look at this one girlie!!! we neeeeeeeeed! 💗")

    # listen for USER3 within 20s
    def check(m: discord.Message):
        return (
            m.author.id == USER3_ID and
            m.channel.id == ctx.channel.id and
            m.created_at > msg1.created_at
        )
    try:
        await bot.wait_for("message", timeout=20, check=check)
        await ctx.send(f"{SLAP_PEACH_EMOTE} you know you'd look good in this girlie! you go girl! {SCISSORS_EMOJI}")
    except asyncio.TimeoutError:
        pass

# ---- Kewchie commands ----
@bot.command(name="kewchie", help="Post a random Kali Uchis song from the playlist (in the kewchie channel)")
async def kewchie(ctx):
    if ctx.channel.id != KEWCHIE_CHANNEL_ID:
        await ctx.send(f"Use this in <#{KEWCHIE_CHANNEL_ID}>")
        return
    links = await _fetch_playlist_tracks(SPOTIFY_PLAYLIST_ID)
    if not links:
        await ctx.send("Playlist isn't available right now 😭")
        return
    await ctx.send(random.choice(links))

@bot.command(name="kewchie-debug", help="Debug Spotify playlist setup")
async def kewchie_debug(ctx):
    cid_set = bool(SPOTIFY_CLIENT_ID)
    sec_set = bool(SPOTIFY_CLIENT_SECRET)
    pid_set = bool(SPOTIFY_PLAYLIST_ID)
    ch_ok = (bot.get_channel(KEWCHIE_CHANNEL_ID) is not None)

    token = await _get_spotify_token()
    token_ok = bool(token)
    tracks = await _fetch_playlist_tracks(SPOTIFY_PLAYLIST_ID) if token_ok else []
    msg = (
        f"CID set: {cid_set}\n"
        f"SECRET set: {sec_set}\n"
        f"PLAYLIST set: {pid_set}\n"
        f"Token: {'ok' if token_ok else 'failed'}\n"
        f"Tracks fetched: {len(tracks)}\n"
        f"Channel OK: {ch_ok} (<#{KEWCHIE_CHANNEL_ID}>)"
    )
    await ctx.send(f"```{msg}```")

# ---- Manual AIRDROP (restricted + once per day) ----
@bot.command(name="airdrop", help="OWNER: Trigger the daily allowance manually (once per day)", hidden=True)
async def airdrop(ctx):
    if ctx.author.id != AIRDROP_MANAGER_ID:
        await ctx.send("Only my sugar manager can do that. 💅")
        return

    today = _today_key()
    if economy.get("_last_airdrop_date") == today:
        await ctx.send("Today's airdrop already processed. 🍞")
        return

    channel = bot.get_channel(CHANNEL_ID) or ctx.channel
    ok = await _run_daily_allowance(channel)
    if ok:
        await ctx.send("Manual daily airdrop processed. 🍞✨")
    else:
        await ctx.send("Couldn't process the airdrop (no channel/guild?).")

# ---- Start ----
if __name__ == "__main__":
    if not TOKEN or not TENOR_KEY or not CHANNEL_ID:
        raise SystemExit("Please set DISCORD_TOKEN, TENOR_API_KEY, and CHANNEL_ID environment variables.")
    bot.run(TOKEN)
