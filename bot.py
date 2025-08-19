import os, random, aiohttp, discord, json, asyncio, time, math, ssl, re
from discord.ext import tasks, commands
from urllib.parse import quote_plus
from datetime import date, datetime, timedelta, time as dtime, timezone
from zoneinfo import ZoneInfo
from collections import defaultdict, Counter
from typing import List, Tuple

import asyncpg  # PostgreSQL (Railway/Supabase/Neon) persistence

# ===================== ENV & CONSTANTS =====================
TOKEN       = os.getenv("DISCORD_TOKEN")
TENOR_KEY   = os.getenv("TENOR_API_KEY")
CHANNEL_ID  = 1273436116699058290
BREAD_EMOJI = os.getenv("BREAD_EMOJI", "🍞")

# Postgres (Neon/Supabase/Railway)
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
# DB SSL behavior: "require" (default) or "insecure" to skip certificate verification
DB_SSL = os.getenv("DB_SSL", "require").strip().lower()

SEARCH_TERM  = "bread"
RESULT_LIMIT = 20
REPLY_CHANCE = 0.10

# Version/info (for !version)
BOT_VERSION = os.getenv("BOT_VERSION", "v1.2-allgames")
BUILD_TAG   = os.getenv("BUILD_TAG", "")

# Specific member IDs
USER1_ID = 1028310674318839878
USER2_ID = 534227493360762891
USER3_ID = 661077262468382761
LOBO_ID  = 919405253470871562

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

# ---------- Fit (Discord CDN images) ----------
FIT_IMAGE_URLS = [
    # original entries
    "https://cdn.discordapp.com/attachments/1405470635844435968/1405470866879414323/pinterest_681169512428877550.png?ex=689ef23f&is=689da0bf&hm=6333fbb250a112ecd271bf33cf4212687b8d01d8200a2e614af2851068a65f65&",
    "https://cdn.discordapp.com/attachments/1405470635844435968/1405470867483525140/pinterest_681169512428917172.jpg?ex=689ef23f&is=689da0bf&hm=9f7e993b0c4391b27262f6bab9e7eba41af434f27d386ea0e3f7af1a2dcf62ef&",
    "https://cdn.discordapp.com/attachments/1405470635844435968/1405470867810422854/pinterest_681169512428917179.jpg?ex=689ef23f&is=689da0bf&hm=738196039bf19fb99b72610d3a30641bb5a8cec28998919e92b3d7dc34c30c28&",
    "https://cdn.discordapp.com/attachments/1405470635844435968/1405470868087373895/pinterest_681169512428919577.jpg?ex=689ef23f&is=689da0bf&hm=f0921729a0c51ac94303ea123209689650e42ec6aebdf585b8609308a34ea7ec&",
    # appended new links
    "https://cdn.discordapp.com/attachments/1405470635844435968/1405608288053235845/Screenshot_14.png?ex=689f723a&is=689e20ba&hm=cdd8b626007dd4939c5337c58d194d2a9229d23ca15ac7a18492abafc5d913d8&",
    "https://cdn.discordapp.com/attachments/1405470635844435968/1405598819860873278/pinterest_681169512428877548.jpg?ex=689f6969&is=689e17e9&hm=820df44a59d2c99fb8e496aed88ccc681843f2d75de830d669bbe26357d0f979&",
    "https://cdn.discordapp.com/attachments/1405470635844435968/1405598819210756178/pinterest_681169512428836350.png?ex=689f6969&is=689e17e9&hm=43c908944d8f813a4b99f0aad4a672dc56e7f05854ee357630bbae8f633b1672&",
    "https://cdn.discordapp.com/attachments/1405470635844435968/1405598818728153148/pinterest_681169512428815368.jpg?ex=689f6969&is=689e17e9&hm=625f7aa45091f7deccd09185dd86d5db9682f0f149b40141112a3a9dc5ad292c&",
    "https://cdn.discordapp.com/attachments/1405470635844435968/1405598818464170195/pinterest_681169512428788228.jpg?ex=689f6969&is=689e17e9&hm=86b1b23a623b8dbbf9789a9a002c8589dec91f139c39caad0a5ee6f470f26d6e&",
]
FIT_CHANNEL_ID = int(os.getenv("FIT_CHANNEL_ID", "1273436116699058290"))
FIT_REPLY_TARGET_ID = 661077262468382761  # member who triggers follow-up if replies within 20s
FIT_FOLLOWUP_EMOTE = "<a:slap_peach:1227392416617730078>"
FIT_FOLLOWUP_TEXT  = "you know you'd look good in this girlie! you go girl! ✂️"

# ---------- Bonk Papo schedule (3 times/day random) ----------
BONK_PAPO_USER_ID = 1028310674318839878
BONK_PAPO_CHANNEL_ID = 1131644171455844455  # channel for bonk posts
BONK_PAPO_TEXT = "stop being horny papo! bad papo! <a:bonk_papo:1216928539413188788><a:bonk_papo:1216928539413188788><a:bonk_papo:1216928539413188788>"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
# Disable default help and replace with !halp
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ===================== Bread Economy Settings =====================
# Global hard cap on TOTAL currency in existence (bank + all users).
# You can override via env TOTAL_MAX_CURRENCY, but default is 1,000,000.
TOTAL_MAX_CURRENCY = int(os.getenv("TOTAL_MAX_CURRENCY", "1000000"))
TREASURY_MAX = int(os.getenv("TREASURY_MAX", str(TOTAL_MAX_CURRENCY)))
USER_WALLET_CAP = int(os.getenv("USER_WALLET_CAP", str(TREASURY_MAX // 10)))
CLAIM_AMOUNT = int(os.getenv("CLAIM_AMOUNT", "250"))
CLAIM_COOLDOWN_HOURS = int(os.getenv("CLAIM_COOLDOWN_HOURS", "24"))
CLAIM_REQUIREMENT = int(os.getenv("CLAIM_REQUIREMENT", "180"))
DAILY_GIFT_CAP = int(os.getenv("DAILY_GIFT_CAP", "2000"))
GIFT_TAX_TIERS = [(1000,0.05),(3000,0.10),(6000,0.15)]
GAMBLE_MAX_BET = int(os.getenv("GAMBLE_MAX_BET", "1500"))
BASE_ROLL_WIN_PROB = float(os.getenv("BASE_ROLL_WIN_PROB", "0.46"))
INACTIVE_WINDOW_DAYS = int(os.getenv("INACTIVE_WINDOW_DAYS", "7"))
PENALTY_IMAGE = "https://i.postimg.cc/9fkgRMC0/nailz.jpg"
JACKPOT_IMAGE = "https://i.postimg.cc/9fkgRMC0/nailz.jpg"
# ==================================================================

# ===== Casino Tuning (improvements) =====
from random import SystemRandom
_rng = SystemRandom()
def _rand() -> float: return _rng.random()

ROLL_COOLDOWN_SEC = int(os.getenv("ROLL_COOLDOWN_SEC", "8"))          # per-user roll spam guard
PUTASOS_COOLDOWN_SEC = int(os.getenv("PUTASOS_COOLDOWN_SEC", "300"))  # 5 minutes
MAX_BET_TREASURY_PCT = float(os.getenv("MAX_BET_TREASURY_PCT", "0.10"))  # max 10% of bank per bet

DAILY_ROLL_LOSS_CAP = int(os.getenv("DAILY_ROLL_LOSS_CAP", "6000"))   # max loss/day via !roll (set 0 to disable)

# Progressive jackpot: tiny % of roll/slots losses gets reserved; can be paid on jackpots
JP_PROGRESSIVE_PCT = float(os.getenv("JP_PROGRESSIVE_PCT", "0.04"))  # 4% of losses to pot
JP_MIN_POOL = int(os.getenv("JP_MIN_POOL", "2500"))                  # display threshold

# ===== Extra Games Tuning =====
DUEL_COOLDOWN_SEC = int(os.getenv("DUEL_COOLDOWN_SEC", "60"))
DUEL_EXPIRE_SEC   = int(os.getenv("DUEL_EXPIRE_SEC", "180"))  # challenge timeout
DUEL_RAKE_PCT     = float(os.getenv("DUEL_RAKE_PCT", "0.02"))  # 2% to bank (set 0.0 to disable)

SLOTS_COOLDOWN_SEC = int(os.getenv("SLOTS_COOLDOWN_SEC", "6"))
SLOTS_PAYTABLE = {
    "🍞🍞🍞": 8.0,
    "💗💗💗": 10.0,
    "⭐️⭐️⭐️": 14.0,
    "👑👑👑": 22.0,
    "PAIR_ANY": 1.6
}
SLOTS_REELS = [
    ["🍞","🍞","🍞","💗","💗","⭐️","👑"],
    ["🍞","🍞","💗","💗","⭐️","👑","🍞"],
    ["🍞","💗","💗","⭐️","👑","🍞","⭐️"],
]
SLOTS_JP_CUT = float(os.getenv("SLOTS_JP_CUT", "0.03"))  # 3% of losing spins into progressive pot

# ===== Raffle Game Tuning =====
RAFFLE_RAKE_PCT = float(os.getenv("RAFFLE_RAKE_PCT", "0.03"))  # 3% of pot to bank; set 0 to disable
RAFFLE_JOIN_DEADLINE_SEC = int(os.getenv("RAFFLE_JOIN_DEADLINE_SEC", "120"))  # join window after start
# Auto-draw behavior
RAFFLE_MIN_ENTRANTS = int(os.getenv("RAFFLE_MIN_ENTRANTS", "2"))  # need at least 2 to draw
RAFFLE_WATCH_INTERVAL_SEC = int(os.getenv("RAFFLE_WATCH_INTERVAL_SEC", "12"))  # how often to check deadlines

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

# ---- Chat lines ----
BREAD_PUNS = [
    "I loaf you more than words can say 🍞❤️","You’re the best thing since sliced bread!",
    "Life is what you bake it 🥖","Rye not have another slice?","All you knead is love (and maybe a little butter) 🧈",
    "You’re toast-ally awesome!","Bready or not, here I crumb! 🍞","Let’s get this bread 💪",
    "Some secrets are best kept on the loaf-down.","MMMMM"
]

BRATTY_LINES = [
    "very cheugi","cayuuuuuute","I hate it here!","SEND ME TO THE ER MF!!!","send me monies!!!",
    "*sigh*","*double sigh*","I'm having a horrible day.","oh my gaaaaawwwwww........d","HALP!","LISTEN!",
    "que triste","I've been dying","wen coffee colon cleansing?","skinnie winnie","labooobies",
    "I want a pumpkin cream cold brewwwww",
    "update I want it to be fall already . need cold breeze, sweaters and flared leggings and a cute beanie and Halloween decor",
    "JONATHAN!","UGH!","MMMMM","was it tasty?","LMFAO I CANT","AAAAAAAAAAAAAAAA",
    "no one pay's attention to me!!!!","I wanna take a trip so bad now"
]

FERAL_LINES = [
    "I’m about to throw bread crumbs EVERYWHERE","LET ME SCREAM INTO A LOAF","JONATHAN DILE!", "I'm so tired", "WHY are people so retarded!!!", "LISTEN", "I WANT BIG",
]

REACTION_EMOTES = ["🤭","😏","😢","😊","🙄","💗","🫶"]

USER3_LINES = [
    "twinnies!!!","girly!","we hate it here r-right girly?","wen girlie wen?!?!",
    "the parasites r-right girly?","girl so confusing","omg sancho is soooooo annoying","ATTACK GIRLIE!",
]

# ================== In-memory economy (backed by Postgres JSON) ==================
def _now() -> float: return time.time()
def _today_key() -> str: return date.today().isoformat()

economy_lock = asyncio.Lock()
economy = {
    "treasury": TREASURY_MAX,
    "users": {},  # str(user_id): {balance, last_claim, last_gift_day, gifted_today, last_active, _lobo_date}
    "jackpot_pool": JP_MIN_POOL,
    "stats": {"rolls": 0, "roll_wins": 0, "roll_losses": 0, "house_take": 0, "payouts": 0}
}

# ---------- Postgres KV (JSON) helpers ----------
db_pool: asyncpg.Pool | None = None

def _sanitize_dsn(raw: str | None) -> str | None:
    if not raw:
        return None
    dsn = raw.strip().strip('"').strip("'")
    dsn = dsn.replace("\n", "").replace("\r", "").strip()
    return dsn

async def _db_init():
    """Connect to Postgres (Neon), force schema=public, and ensure tables exist. Retries on cold starts."""
    global db_pool
    dsn = _sanitize_dsn(os.getenv("DATABASE_URL", ""))
    if not dsn:
        print("DB init: no DATABASE_URL set → running without persistence.")
        return

    last_err = None
    for attempt in range(1, 8):  # retry ~7 times over ~45s
        try:
            db_pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3, timeout=20, command_timeout=20)
            async with db_pool.acquire() as con:
                await con.execute("CREATE SCHEMA IF NOT EXISTS public;")
                await con.execute("SET search_path TO public;")
                await con.execute("""
                    CREATE TABLE IF NOT EXISTS public.kv (
                      key   TEXT PRIMARY KEY,
                      value JSONB NOT NULL
                    )
                """)
                # === corpus table for mimic feature ===
                await con.execute("""
                    CREATE TABLE IF NOT EXISTS public.mimic_msgs (
                      id SERIAL PRIMARY KEY,
                      user_id BIGINT NOT NULL,
                      channel_id BIGINT NOT NULL,
                      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                      content TEXT NOT NULL
                    )
                """)
                row = await con.fetchrow(
                    "SELECT current_database() AS db, current_schema() AS schema, "
                    "inet_server_addr()::text AS host, inet_server_port() AS port"
                )
                print(f"DB init: connected ✅ db={row['db']} schema={row['schema']} host={row['host']} port={row['port']}")
            return
        except Exception as e:
            last_err = e
            print(f"DB init attempt {attempt} failed: {type(e).__name__}: {e!s}")
            await asyncio.sleep(6)

    db_pool = None
    print(f"DB init failed ❌ after retries: {type(last_err).__name__}: {last_err!s}")
    print("Running without persistence.")

async def _db_get(key: str):
    """Fetch a key from public.kv and return a Python dict, even if DB gave us text."""
    if not db_pool:
        return None
    async with db_pool.acquire() as con:
        row = await con.fetchrow("SELECT value FROM public.kv WHERE key=$1", key)
        if not row:
            return None
        val = row["value"]
        if isinstance(val, str):
            try:
                val = json.loads(val)
            except Exception:
                pass
        return val

async def _db_set(key: str, value: dict):
    """Upsert a JSON document into public.kv as proper JSONB (not text)."""
    if not db_pool:
        return
    async with db_pool.acquire() as con:
        await con.execute("""
            INSERT INTO public.kv (key, value)
            VALUES ($1, $2::jsonb)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """, key, json.dumps(value))

# ---------- Load/Save economy to Postgres JSON ----------
async def _load_bank():
    """Load the whole economy JSON from Postgres; create default if missing."""
    global economy
    if not db_pool:
        return

    data = await _db_get("economy")

    # If the row is present but came back as text, parse it.
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            data = None

    if isinstance(data, dict) and data:
        data.setdefault("treasury", TREASURY_MAX)
        data.setdefault("users", {})
        data.setdefault("jackpot_pool", JP_MIN_POOL)
        data.setdefault("stats", {"rolls": 0, "roll_wins": 0, "roll_losses": 0, "house_take": 0, "payouts": 0})
        economy = data
    else:
        # First run (or corrupted/missing row)
        economy = {"treasury": TREASURY_MAX, "users": {}, "jackpot_pool": JP_MIN_POOL,
                   "stats": {"rolls": 0, "roll_wins": 0, "roll_losses": 0, "house_take": 0, "payouts": 0}}
        await _db_set("economy", economy)

async def _save_bank():
    if db_pool:
        await _db_set("economy", economy)

# ================== Supply helpers (global 1M cap) ==================
def _total_supply() -> int:
    """Total currency in existence: bank (treasury) + all user balances."""
    return int(economy.get("treasury", 0)) + sum(int(u.get("balance", 0)) for u in economy.get("users", {}).values())

def _remaining_mint_room() -> int:
    """How much new currency could be created without breaking the global cap."""
    rem = TOTAL_MAX_CURRENCY - _total_supply()
    return max(0, rem)

# ================== Common economy helpers ==================
def _user(uid: int):
    suid = str(uid)
    u = economy["users"].get(suid)
    if not u:
        u = {"balance": 0,"last_claim": 0,"last_gift_day": "","gifted_today": 0,"last_active": 0.0,
             "last_roll": 0.0, "roll_day": "", "roll_loss_today": 0, "last_putasos": 0.0}
        economy["users"][suid] = u
    return u

def _fmt_bread(n: int) -> str: return f"{n} {BREAD_EMOJI}"

def _cap_wallet(balance_after: int) -> tuple[int, int]:
    if balance_after <= USER_WALLET_CAP: return balance_after, 0
    skim = balance_after - USER_WALLET_CAP
    return USER_WALLET_CAP, skim

def _apply_gift_tax(amount: int) -> tuple[int, int]:
    tax = 0; remaining = amount; prev_threshold = 0
    for threshold, rate in GIFT_TAX_TIERS:
        if remaining <= 0: break
        portion = max(0, min(remaining, threshold - prev_threshold))
        tax += math.floor(portion * rate)
        remaining -= portion; prev_threshold = threshold
    if remaining > 0 and GIFT_TAX_TIERS:
        tax += math.floor(remaining * GIFT_TAX_TIERS[-1][1])
    net = amount - tax
    return max(0, net), max(0, tax)

def _mark_active(uid: int):
    _user(uid)["last_active"] = _now()

# ============== Casino helpers ==============
def _dynamic_max_bet(vault: int, user_bal: int) -> int:
    """Cap a bet by global GAMBLE_MAX_BET, user balance, vault %, and available vault."""
    pct_cap = int(max(1, vault) * MAX_BET_TREASURY_PCT)
    return max(1, min(GAMBLE_MAX_BET, user_bal, pct_cap, vault))

def _est_win_prob(bet: int) -> float:
    """Your current formula + mild bank-health nudging (±2%)."""
    frac = bet / max(1, USER_WALLET_CAP)
    win_prob = BASE_ROLL_WIN_PROB
    if frac <= 0.05: win_prob += 0.05
    elif frac >= 0.5: win_prob -= 0.06
    # Bank health nudge
    bank_health = economy["treasury"] / max(1, TREASURY_MAX)
    win_prob += (bank_health - 0.5) * 0.04
    return max(0.02, min(0.98, win_prob))

def _can_afford(user_obj: dict, amt: int) -> bool:
    return int(user_obj.get("balance", 0)) >= amt

# ================== Spotify helpers ==================
_spotify_token = {"access_token": None, "expires_at": 0}

async def _get_spotify_token():
    if _spotify_token["access_token"] and _now() < _spotify_token["expires_at"] - 30:
        return _spotify_token["access_token"]
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        return None
    data = {
        "grant_type": "client_credentials",
        "client_id": SPOTIFY_CLIENT_ID,
        "client_secret": SPOTIFY_CLIENT_SECRET,
    }
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post("https://accounts.spotify.com/api/token", data=data, timeout=15) as r:
                if r.status != 200: return None
                js = await r.json()
                _spotify_token["access_token"] = js.get("access_token")
                _spotify_token["expires_at"] = _now() + int(js.get("expires_in", 3600))
                return _spotify_token["access_token"]
    except Exception:
        return None

async def _fetch_playlist_tracks(playlist_id: str) -> list[str]:
    token = await _get_spotify_token()
    if not token: return []
    headers = {"Authorization": f"Bearer {token}"}
    params = {"market": SPOTIFY_MARKET, "limit": 100}
    url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
    tracks = []
    try:
        async with aiohttp.ClientSession() as s:
            while url:
                async with s.get(url, headers=headers, params=params, timeout=15) as r:
                    if r.status != 200: return tracks
                    data = await r.json()
                    for item in data.get("items", []):
                        t = item.get("track") or {}
                        if t and not t.get("is_local") and t.get("id"):
                            tracks.append(f"https://open.spotify.com/track/{t['id']}")
                    url = data.get("next"); params = None
    except Exception:
        pass
    return tracks

# ================== Mimic (USER3 style) ==================
# NOTE: This block is additive and does not modify any existing behavior.
TARGET_MIMIC_ID = USER3_ID  # 661077262468382761
MIMIC_REPLY_CHANCE = 0.28        # chance to reply when USER3 speaks
MIMIC_COOLDOWN_SEC = 75          # cooldown to prevent spam
MIMIC_CONTEXT_WINDOW_SEC = 120   # window to chime in after USER3 last spoke in channel

_mimic_model = {
    "ngrams": {},          # {(w1,w2): Counter({w3:count})}
    "starts": [],          # recent sentence starts for seeding
    "emoji_dist": Counter(),
    "avg_len": 18.0,
}

def _mimic_is_emoji(tok: str):
    return bool(re.match(r"(<a?:\w+:\d+>|[\U00010000-\U0010ffff])", tok))

def _mimic_tok(s: str):
    # keeps emojis/custom emotes and punctuation as tokens
    return re.findall(r"[A-Za-z0-9]+|[:;][)(DPp]|<a?:\w+:\d+>|[\U00010000-\U0010ffff]|[^\s\w]", s)

async def _mimic_store_message(msg: discord.Message):
    # save USER3's organic messages to DB (skip links/commands/very short/very long)
    if not db_pool: return
    txt = (msg.content or "").strip()
    if not (6 <= len(txt) <= 200): return
    if txt.startswith("!") or "http://" in txt or "https://" in txt: return
    try:
        async with db_pool.acquire() as con:
            await con.execute(
                "INSERT INTO public.mimic_msgs(user_id, channel_id, content) VALUES($1,$2,$3)",
                msg.author.id, msg.channel.id, txt
            )
    except Exception:
        pass

async def _mimic_load_corpus(limit=1200):
    if not db_pool: return []
    async with db_pool.acquire() as con:
        rows = await con.fetch(
            "SELECT content FROM public.mimic_msgs WHERE user_id=$1 ORDER BY id DESC LIMIT $2",
            TARGET_MIMIC_ID, limit
        )
    return [r["content"] for r in rows]

def _mimic_build_markov(corpus: list[str]):
    if not corpus: return
    ngrams = defaultdict(Counter)
    starts = []
    emojis = Counter()
    lengths = []

    for line in corpus:
        toks = _mimic_tok(line)
        if len(toks) < 4:
            continue
        lengths.append(len(toks))
        for t in toks:
            if _mimic_is_emoji(t): emojis[t] += 1
        starts.append(tuple(toks[:2]))
        for i in range(len(toks)-2):
            key = (toks[i], toks[i+1])
            ngrams[key][toks[i+2]] += 1

    _mimic_model["ngrams"] = dict(ngrams)
    _mimic_model["starts"] = starts[-200:]  # bias to fresher starts
    _mimic_model["emoji_dist"] = emojis
    _mimic_model["avg_len"] = (sum(lengths)/len(lengths)) if lengths else 18.0

def _mimic_sample_next(counter: Counter, temperature=0.9):
    if not counter: return None
    items = list(counter.items())
    toks, counts = zip(*items)
    weights = [c**(1.0/temperature) for c in counts]
    total = sum(weights)
    r = random.random() * total
    acc = 0.0
    for tok, w in zip(toks, weights):
        acc += w
        if acc >= r:
            return tok
    return toks[-1]

def _mimic_join_tokens(toks):
    out = []
    for i,t in enumerate(toks):
        if i>0 and re.match(r"[A-Za-z0-9<\U00010000-\U0010ffff]", t) and out[-1] not in ["(", "[", "{", "“", "\"", "'", "/"]:
            out.append(" ")
        out.append(t)
    return "".join(out).strip()

def _mimic_jaccard(a: str, b: str):
    A = set(_mimic_tok(a.lower())); B = set(_mimic_tok(b.lower()))
    if not A or not B: return 0.0
    return len(A & B) / len(A | B)

async def _mimic_generate():
    model = _mimic_model["ngrams"]
    starts = _mimic_model["starts"]
    if not model or not starts:
        return None

    target_len = max(6, min(40, int(random.gauss(_mimic_model["avg_len"], 4))))
    cur = list(random.choice(starts))
    # trigram walk
    while len(cur) < target_len:
        key = (cur[-2], cur[-1])
        nxt = _mimic_sample_next(model.get(key, Counter()))
        if not nxt: break
        cur.append(nxt)

    # occasional emoji from their distribution
    if _mimic_model["emoji_dist"] and random.random() < 0.25:
        emo, _ = _mimic_model["emoji_dist"].most_common(1)[0]
        cur.append(emo)

    if not any(str(cur[-1]).endswith(x) for x in [".","!","?","…"]):
        cur.append(random.choice([".", "!", "…"]))

    text = _mimic_join_tokens(cur)

    # novelty check vs last ~200 lines
    corpus = await _mimic_load_corpus(limit=200)
    for line in corpus[:80]:
        if _mimic_jaccard(text, line) > 0.6:
            return None
    return text

@tasks.loop(hours=1)
async def rebuild_mimic():
    corpus = await _mimic_load_corpus()
    _mimic_build_markov(corpus)

@rebuild_mimic.before_loop
async def _wait_mimic_ready():
    await bot.wait_until_ready()

# ================== Tenor helpers ==================
async def fetch_gif(query: str, limit: int = 20):
    if not TENOR_KEY: return None
    url = f"https://tenor.googleapis.com/v2/search?q={quote_plus(query)}&key={TENOR_KEY}&limit={limit}"
    async with aiohttp.ClientSession() as s:
        async with s.get(url) as r:
            if r.status != 200: return None
            data = await r.json(); items = data.get("results", [])
            if not items: return None
            return random.choice(items)["media_formats"]["gif"]["url"]

async def fetch_bread_gif(): return await fetch_gif(SEARCH_TERM, RESULT_LIMIT)

# ================== Schedulers helpers ==================
def _pick_two_random_times_today():
    tz = ZoneInfo("America/Los_Angeles")
    today = datetime.now(tz=tz).date()
    start = datetime.combine(today, dtime(hour=10, tzinfo=tz))
    end   = datetime.combine(today, dtime(hour=22, tzinfo=tz))
    def rand_dt():
        delta_minutes = int((end - start).total_seconds() // 60)
        offset = random.randint(0, delta_minutes)
        return (start + timedelta(minutes=offset)).astimezone(timezone.utc).replace(second=0, microsecond=0)
    t1 = rand_dt(); t2 = rand_dt()
    while abs((t2 - t1).total_seconds()) < 300:
        t2 = rand_dt()
    return sorted([t1, t2])

def _today_key_pt() -> str:
    return datetime.now(ZoneInfo("America/Los_Angeles")).date().isoformat()

def _pick_three_times_today_pt(n: int = 3):
    today_pt = datetime.now(ZoneInfo("America/Los_Angeles")).date()
    start_pt = datetime.combine(today_pt, dtime(hour=9), tzinfo=ZoneInfo("America/Los_Angeles"))
    end_pt   = datetime.combine(today_pt, dtime(hour=22), tzinfo=ZoneInfo("America/Los_Angeles"))
    total_minutes = int((end_pt - start_pt).total_seconds() // 60)

    def rand_dt_utc():
        offset = random.randint(0, total_minutes)
        when_pt = start_pt + timedelta(minutes=offset)
        return when_pt.astimezone(timezone.utc).replace(second=0, microsecond=0)

    times = {rand_dt_utc() for _ in range(n)}
    while len(times) < n:
        times.add(rand_dt_utc())
    return sorted(times)
    times = sorted({rand_dt() for _ in range(3)})
    while len(times) < 3:
        times.add(rand_dt())
    return list(times)

# ================== Events ==================
@bot.event
async def on_ready():

    # DB init & load economy
    await _db_init()
    await _load_bank()

    if not hasattr(bot, "_js_last"):
        bot._js_last = {}
    if not hasattr(bot, "_kewchie_times"):
        bot._kewchie_times = []
        bot._kewchie_posted = set()
    if not hasattr(bot, "_fit_waiting"):
        bot._fit_waiting = {}  # message_id -> expiry_ts
    if not hasattr(bot, "_duels"):
        bot._duels = {}  # channel_id -> duel state
    if not hasattr(bot, "_raffles"):
        bot._raffles = {}  # guild_id -> raffle state


    # --- ChatDrop: safe plug-in ---
    try:
        helpers = {
            "now": _now,
            "fmt_bread": _fmt_bread,
            "cap_wallet": _cap_wallet,
            "get_user": _user,
            "save_bank": _save_bank,
            "economy": economy,
            "economy_lock": economy_lock,
        }
        if not hasattr(bot, "_chatdrop_loaded"):
            bot.add_cog(ChatDropCog(bot, helpers))
            bot._chatdrop_loaded = True
    except Exception as e:
        print("ChatDropCog load error:", e)

    print(f"Logged in as {bot.user}")
    four_hour_post.start()
    six_hour_emoji.start()
    user1_twice_daily_fixed.start()
    user2_twice_daily_fixed.start()
    user3_task.start()
    daily_scam_post.start()
    daily_auto_allowance.start()  # 8am PT allowance + penalties
    kewchie_daily_scheduler.start()  # random twice-daily posts
    fit_auto_daily.start()          # auto-fit once a day
    bonk_papo_scheduler.start()     # 3x/day random bonk messages
    rebuild_mimic.start()           # build mimic model hourly
    raffle_watcher.start()
    daily_gym_reminder.start()          # raffle auto-draw watcher

@tasks.loop(minutes=1)
async def kewchie_daily_scheduler():
    now_utc = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    if (not bot._kewchie_times) or (bot._kewchie_times[0].date() != now_utc.date()):
        bot._kewchie_times = _pick_two_random_times_today()
        bot._kewchie_posted = set()

    for t in bot._kewchie_times:
        key = t.isoformat()
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

# ---- BONK PAPO random 3x/day ----
@tasks.loop(minutes=1)
async def bonk_papo_scheduler():
    if not hasattr(bot, "_bonk_times") or not bot._bonk_times:
        bot._bonk_times = _pick_three_times_today_pt()
        bot._bonked = set()
        bot._bonk_day = _today_key_pt()

    now_utc = datetime.now(timezone.utc).replace(second=0, microsecond=0)

    for t in bot._bonk_times:
        key = t.isoformat()
        if abs((now_utc - t).total_seconds()) <= 60 and key not in bot._bonked:
            ch = bot.get_channel(BONK_PAPO_CHANNEL_ID) or await bot.fetch_channel(BONK_PAPO_CHANNEL_ID)
            if ch:
                await ch.send(f"<@{BONK_PAPO_USER_ID}> {BONK_PAPO_TEXT}")
            bot._bonked.add(key)

    if _today_key_pt() != bot._bonk_day:
        bot._bonk_times = _pick_three_times_today_pt()
        bot._bonked = set()
        bot._bonk_day = _today_key_pt()

@bonk_papo_scheduler.before_loop
async def _bonk_wait():
    await bot.wait_until_ready()

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # --- Mimic: capture USER3 messages + mark "last seen" per channel ---
    if message.author.id == USER3_ID:
        await _mimic_store_message(message)
        if not hasattr(bot, "_last_user3_in_ch"):
            bot._last_user3_in_ch = {}
        bot._last_user3_in_ch[message.channel.id] = _now()

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
            await _save_bank()

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

    # Special: reply to USER3_ID with USER3_LINES (throttled to 35% of their msgs; 20% add emote)
    if message.author.id == USER3_ID:
        if random.random() < 0.35:
            phrase = random.choice(USER3_LINES)
            if random.random() < 0.20:
                phrase = f"{phrase} {random.choice(REACTION_EMOTES)}"
            await message.reply(phrase, mention_author=False)
            return

    # --- Natural mimic (non-invasive): only runs if the canned USER3 block didn't return above ---
    if not hasattr(bot, "_mimic_last_ts"):
        bot._mimic_last_ts = 0
    nowts = _now()

    # If USER3 speaks, maybe reply in their style
    if message.author.id == USER3_ID:
        if nowts - bot._mimic_last_ts >= MIMIC_COOLDOWN_SEC and random.random() < MIMIC_REPLY_CHANCE:
            gen = await _mimic_generate()
            if gen:
                await message.reply(gen, mention_author=False)
                bot._mimic_last_ts = nowts
                return

    # If someone else speaks shortly after USER3 in this channel, a small chance to chime in
    last_here = getattr(bot, "_last_user3_in_ch", {}).get(message.channel.id, 0)
    if last_here and 0 < (nowts - last_here) <= MIMIC_CONTEXT_WINDOW_SEC:
        if nowts - bot._mimic_last_ts >= MIMIC_COOLDOWN_SEC and random.random() < 0.12:
            gen = await _mimic_generate()
            if gen:
                await message.reply(gen, mention_author=False)
                bot._mimic_last_ts = nowts
                return

    # Mention → bratty only (existing behavior)
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

# ---- Reply watcher for FIT follow-up (20s window) ----
@bot.listen("on_message")
async def _fit_reply_watch(message: discord.Message):
    if message.author.bot: return
    if not message.reference or not message.reference.resolved: return
    replied_to = message.reference.resolved
    if replied_to.author.id != bot.user.id: return
    expiry = getattr(bot, "_fit_waiting", {}).get(replied_to.id)
    if not expiry: return
    if _now() > expiry:
        bot._fit_waiting.pop(replied_to.id, None)
        return
    if message.author.id == FIT_REPLY_TARGET_ID:
        ch = message.channel
        await ch.send(f"{FIT_FOLLOWUP_EMOTE} {FIT_FOLLOWUP_TEXT}")
        bot._fit_waiting.pop(replied_to.id, None)

# ================== Bread posts & schedules ==================
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


# ---- Gym Reminder ----
import random
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo
from discord.ext import tasks

GYM_CHANNEL_ID = 123456789012345678  # replace with your channel ID

GYM_EMOTES_1 = ["💪", "🏋️‍♂️", "🏋️‍♀️", "🏃‍♂️", "🏃‍♀️", "🤸‍♀️", "🚴‍♂️", "🔥", "💯", "🥇", "🧠", "🫀"]
GYM_EMOTES_2 = ["🏋️‍♀️", "🏋️‍♂️", "🚴‍♀️", "🏃‍♂️", "🏃‍♀️", "🥵", "🔥", "⚡️", "💥", "💢", "🗣️", "📣"]

def pick_emotes(pool, k=3):
    k = min(k, len(pool))
    return " ".join(random.sample(pool, k))

@tasks.loop(time=[
    dtime(hour=4, minute=30, tzinfo=ZoneInfo("America/Los_Angeles")),  # 4:30 AM PT
    dtime(hour=5, minute=10, tzinfo=ZoneInfo("America/Los_Angeles")),  # 5:10 AM PT
])
async def daily_gym_reminder():
    ch = bot.get_channel(GYM_CHANNEL_ID) or await bot.fetch_channel(GYM_CHANNEL_ID)
    if not ch:
        return

    now_pt = datetime.now(ZoneInfo("America/Los_Angeles")).time()

    if now_pt.hour == 4 and now_pt.minute == 30:
        emotes = pick_emotes(GYM_EMOTES_1, k=3)
        await ch.send(f"wake up gorditos it's time for gymmies!!! {emotes}")
    elif now_pt.hour == 5 and now_pt.minute == 10:
        emotes = pick_emotes(GYM_EMOTES_2, k=3)
        await ch.send(f"ÁNDALE! don't be lazy! {emotes}")

@daily_gym_reminder.before_loop
async def _wait_ready_gym():
    await bot.wait_until_ready()


# ======== Daily auto allowance + inactivity penalties (8am PT) ========
@tasks.loop(time=dtime(hour=8, tzinfo=ZoneInfo("America/Los_Angeles")))
async def daily_auto_allowance():
    channel = bot.get_channel(CHANNEL_ID)
    if not channel: return
    guild = channel.guild
    if not guild: return

    utc_now = _now()
    inactive_cutoff = utc_now - INACTIVE_WINDOW_DAYS * 86400
    changed = False

    async with economy_lock:
        for m in guild.members:
            if m.bot: continue
            u = _user(m.id)

            # 1) Daily allowance
            if economy["treasury"] > 0:
                pay = min(CLAIM_AMOUNT, economy["treasury"])
                new_bal = u["balance"] + pay
                final_bal, skim = _cap_wallet(new_bal)
                economy["treasury"] -= max(0, (pay - skim))
                u["balance"] = final_bal
                changed = True

            # 2) Inactivity penalty (no roll/putasos in last N days)
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
        if changed:
            await _save_bank()

# ================== Economy Commands ==================
def _cooldown_left(last_ts: float, hours: int) -> tuple[int, int]:
    remaining = int(hours * 3600 - (_now() - last_ts))
    if remaining < 0: remaining = 0
    hrs = remaining // 3600
    mins = (remaining % 3600) // 60
    return hrs, mins

@bot.command(name="bank", help="Show remaining bread in the bank")
async def bank(ctx):
    async with economy_lock:
        t = economy["treasury"]
    await ctx.send(f"Bank vault: **{_fmt_bread(t)}** remaining.")

@bot.command(name="balance", aliases=["bal","wallet"], help="See your bread balance (or someone else's)")
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
            await ctx.send(f"{ctx.author.mention} " + PHRASES["claim_gate"].format(need=_fmt_bread(CLAIM_REQUIREMENT))); return
        hrs_left, mins_left = _cooldown_left(u["last_claim"], CLAIM_COOLDOWN_HOURS)
        if hrs_left or mins_left:
            await ctx.send(f"{ctx.author.mention} " + PHRASES["claim_cooldown"].format(hrs=hrs_left, mins=mins_left)); return
        if economy["treasury"] <= 0:
            await ctx.send(PHRASES["bank_empty"]); return

        pay = min(CLAIM_AMOUNT, economy["treasury"])
        new_bal = u["balance"] + pay
        final_bal, skim = _cap_wallet(new_bal)

        economy["treasury"] -= (pay - skim)
        u["balance"] = final_bal
        u["last_claim"] = _now()
        vault = economy["treasury"]
        await _save_bank()

    msg = (f"{ctx.author.mention} {PHRASES['claim_success']} "
           f"(paid {_fmt_bread(pay)}) → **new balance: {_fmt_bread(final_bal)}** · "
           f"**bank: {_fmt_bread(vault)}**")
    if skim: msg += f" (cap skim {_fmt_bread(skim)} back to bank)"
    await ctx.send(msg)

@bot.command(name="gift", help="Gift bread: !gift @user 25")
async def gift(ctx, member: discord.Member, amount: int):
    if amount <= 0:
        await ctx.send("positive numbers only, banker bae. 🙄"); return
    if member.id == ctx.author.id:
        await ctx.send("gifting yourself? be serious 😏"); return

    today = _today_key()
    async with economy_lock:
        giver = _user(ctx.author.id)
        recv  = _user(member.id)
        if giver["last_gift_day"] != today:
            giver["last_gift_day"] = today
            giver["gifted_today"] = 0

        if giver["gifted_today"] + amount > DAILY_GIFT_CAP:
            left = max(0, DAILY_GIFT_CAP - giver["gifted_today"])
            await ctx.send(PHRASES["gift_cap_left"].format(cap=_fmt_bread(DAILY_GIFT_CAP), left=_fmt_bread(left))); return
        if giver["balance"] < amount:
            await ctx.send(f"{ctx.author.mention} " + PHRASES["gift_insufficient"].format(bal=_fmt_bread(giver["balance"]))); return

        net, tax = _apply_gift_tax(amount)
        giver["balance"] -= amount
        recv_after = recv["balance"] + net
        recv_final, skim = _cap_wallet(recv_after)

        economy["treasury"] = min(TREASURY_MAX, economy["treasury"] + tax + skim)
        recv["balance"] = recv_final
        giver["gifted_today"] += amount
        await _save_bank()

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
        await ctx.send("no bread yet. go touch some dough."); return
    lines = []
    for rank, (uid, bal) in enumerate(top, 1):
        user = ctx.guild.get_member(uid) if ctx.guild else None
        name = user.display_name if user else f"User {uid}"
        lines.append(f"{rank}. **{name}** — {_fmt_bread(bal)}")
    await ctx.send("**Bread Leaderboard**\n" + "\n".join(lines))

@bot.command(name="richlist", help="Alias of !lb")
async def richlist(ctx):
    await lb(ctx)

def _resolve_roll_amount(u_balance: int, arg: str | int) -> int:
    if isinstance(arg, int): return max(0, arg)
    s = str(arg).lower()
    if s == "all": return u_balance
    if s == "half": return u_balance // 2
    try: return max(0, int(s))
    except Exception: return 0

@bot.command(name="roll", help="Bet vs the bank: !roll 100 | !roll all | !roll half (jackpot on ALL)")
async def roll(ctx, amount: str):
    if not _is_gamble_channel(ctx.channel.id):
        await ctx.send(f"Casino floor is only open in <#{GAMBLE_CHANNEL_ID}>."); return

    async with economy_lock:
        u = _user(ctx.author.id)

        # Daily loss guard reset
        today = _today_key()
        if u.get("roll_day") != today:
            u["roll_day"] = today
            u["roll_loss_today"] = 0

        # Cooldown
        since = _now() - float(u.get("last_roll", 0.0))
        cd_left = int(ROLL_COOLDOWN_SEC - since)
        if cd_left > 0:
            await ctx.send(f"{ctx.author.mention} slow down, high roller — **{cd_left}s** cooldown."); return

        # Parse stake
        bet = _resolve_roll_amount(u["balance"], amount)
        if bet <= 0:
            await ctx.send("try a positive bet, casino clown. 🙄"); return
        if bet > u["balance"]:
            await ctx.send(f"{ctx.author.mention} you only have **{_fmt_bread(u['balance'])}**."); return

        # Max bet: treasury %, treasury itself, user balance, and daily loss cap room
        max_bet = _dynamic_max_bet(economy["treasury"], u["balance"])
        if DAILY_ROLL_LOSS_CAP > 0:
            loss_room = max(1, DAILY_ROLL_LOSS_CAP - int(u.get("roll_loss_today", 0)))
            max_bet = min(max_bet, loss_room)
        if bet > max_bet:
            await ctx.send(PHRASES["gamble_max"].format(maxb=_fmt_bread(max_bet))); return

        # Win probability (logic + small vault-health nudge)
        win_prob = _est_win_prob(bet)

        # Jackpot
        jackpot_hit = False; jackpot_mult = 1
        if isinstance(amount, str) and amount.lower() == "all":
            r = _rand()
            if r < 0.005: jackpot_hit = True; jackpot_mult = 15
            elif r < 0.025: jackpot_hit = True; jackpot_mult = 3

        if jackpot_hit:
            payout = bet * (jackpot_mult - 1)
            available_from_bank = min(economy["treasury"], payout)
            new_bal = u["balance"] + available_from_bank
            final_bal, skim = _cap_wallet(new_bal)
            paid_from_bank = (final_bal - u["balance"]) + skim
            economy["treasury"] -= max(0, paid_from_bank - skim)
            u["balance"] = final_bal

            # Progressive bonus
            pot = int(economy.get("jackpot_pool", 0))
            bonus_line = ""
            if pot >= JP_MIN_POOL:
                bonus = min(pot, bet * 5)
                if bonus > 0:
                    economy["jackpot_pool"] = pot - bonus
                    new2 = u["balance"] + bonus
                    final2, skim2 = _cap_wallet(new2)
                    bonus_paid = final2 - u["balance"]
                    u["balance"] = final2
                    economy["treasury"] = min(TREASURY_MAX, economy["treasury"] + skim2)
                    bonus_line = f"\n🎰 Progressive bonus **+{_fmt_bread(bonus_paid)}** (pot now **{_fmt_bread(economy['jackpot_pool'])}**)"

            _mark_active(ctx.author.id)
            economy["stats"]["rolls"] += 1
            economy["stats"]["payouts"] += available_from_bank
            u["last_roll"] = _now()
            await _save_bank()
            await ctx.send(
                f"💥 JACKPOT x{jackpot_mult}! {ctx.author.mention} just exploded the oven for **{_fmt_bread(min(payout, available_from_bank))}**!"
                f"\nnew: **{_fmt_bread(u['balance'])}**{bonus_line}\n{JACKPOT_IMAGE}"
            )
            return

        # Normal outcome
        win = (_rand() < win_prob)
        if win:
            new_bal = u["balance"] + bet
            final_bal, skim = _cap_wallet(new_bal)
            economy["treasury"] -= (bet - skim)
            u["balance"] = final_bal
            text = PHRASES["gamble_win"].format(amount=_fmt_bread(bet), bal=_fmt_bread(final_bal))
            if skim: text += f" (cap skim {_fmt_bread(skim)} back to bank)"
            economy["stats"]["roll_wins"] += 1
            economy["stats"]["payouts"] += (bet - skim)
        else:
            u["balance"] -= bet
            economy["treasury"] = min(TREASURY_MAX, economy["treasury"] + bet)
            # Progressive pot gets a slice of losses
            jp_add = int(bet * JP_PROGRESSIVE_PCT)
            if jp_add > 0:
                move = min(jp_add, economy["treasury"])
                economy["treasury"] -= move
                economy["jackpot_pool"] = economy.get("jackpot_pool", JP_MIN_POOL) + move
            u["roll_loss_today"] = int(u.get("roll_loss_today", 0)) + bet
            text = PHRASES["gamble_lose"].format(amount=_fmt_bread(bet), bal=_fmt_bread(u["balance"]))
            economy["stats"]["roll_losses"] += 1
            economy["stats"]["house_take"] += bet

        _mark_active(ctx.author.id)
        economy["stats"]["rolls"] += 1
        u["last_roll"] = _now()
        await _save_bank()
    await ctx.send(f"{ctx.author.mention} {text}")

@bot.command(name="putasos", help="Try and rob someone kombat klubz style")
async def putasos(ctx, member: discord.Member):
    if not _is_gamble_channel(ctx.channel.id):
        await ctx.send(f"Casino floor is only open in <#{GAMBLE_CHANNEL_ID}>."); return
    if member.id == ctx.author.id:
        await ctx.send("stealing from yourself? iconic, but no."); return
    if member.bot:
        await ctx.send("you can’t rob bots. they have no pockets."); return

    SUCCESS_CHANCE = 0.15
    STEAL_PCT_MIN, STEAL_PCT_MAX = 0.10, 0.25
    FAIL_LOSE_PCT = 0.12

    async with economy_lock:
        thief = _user(ctx.author.id)
        victim = _user(member.id)

        # Cooldown for robber
        since = _now() - float(thief.get("last_putasos", 0.0))
        cd_left = int(PUTASOS_COOLDOWN_SEC - since)
        if cd_left > 0:
            await ctx.send(f"{ctx.author.mention} take a breath — **{cd_left}s** cooldown on robberies."); return

        if thief["balance"] <= 0:
            await ctx.send("you’re broke. go touch some dough first."); return
        if victim["balance"] <= 0:
            await ctx.send("they’re broke. pick a richer target."); return

        if _rand() < SUCCESS_CHANCE:
            steal_pct = random.uniform(STEAL_PCT_MIN, STEAL_PCT_MAX)
            take = max(1, int(victim["balance"] * steal_pct))
            victim["balance"] -= take
            new_bal = thief["balance"] + take
            final_bal, skim = _cap_wallet(new_bal)
            thief["balance"] = final_bal
            economy["treasury"] = min(TREASURY_MAX, economy["treasury"] + skim)
            _mark_active(ctx.author.id)
            msg = f"successful heist 😈 you stole **{_fmt_bread(take)}** from {member.mention} → new: **{_fmt_bread(thief['balance'])}**"
            if skim: msg += f" (cap skim {_fmt_bread(skim)} back to bank)"
        else:
            loss = max(1, int(thief["balance"] * FAIL_LOSE_PCT))
            thief["balance"] -= loss
            economy["treasury"] = min(TREASURY_MAX, economy["treasury"] + loss)
            _mark_active(ctx.author.id)
            msg = f"got caught 💀 lost **{_fmt_bread(loss)}** to the bank. new: **{_fmt_bread(thief['balance'])}**"

        thief["last_putasos"] = _now()
        await _save_bank()
    await ctx.send(f"{ctx.author.mention} {msg}")

# ================== Extra Games ==================
# ---- PvP Dice Duel ----
@bot.command(name="duel", help="Challenge someone to a dice duel: !duel @user 500 (target must !accept or !decline)")
async def duel(ctx, member: discord.Member = None, amount: int = None):
    if not _is_gamble_channel(ctx.channel.id):
        await ctx.send(f"Casino floor is only open in <#{GAMBLE_CHANNEL_ID}>."); return
    if not member or amount is None or amount <= 0:
        await ctx.send("Usage: `!duel @user amount`"); return
    if member.id == ctx.author.id:
        await ctx.send("dueling yourself? iconic… but no."); return
    if member.bot:
        await ctx.send("you can’t duel bots. they roll 100 every time. 🙄"); return

    async with economy_lock:
        ch_id = ctx.channel.id
        if ch_id in bot._duels:
            d = bot._duels[ch_id]
            # auto-expire stale duel
            if _now() - d["created_ts"] > DUEL_EXPIRE_SEC:
                bot._duels.pop(ch_id, None)
            else:
                await ctx.send("There’s already a pending duel in this channel. Use `!accept` or `!decline` first."); return

        a = _user(ctx.author.id)
        t = _user(member.id)

        # cooldown check on challenger (reuse last_roll as general casino guard)
        since = _now() - float(a.get("last_roll", 0.0))
        if since < max(ROLL_COOLDOWN_SEC, DUEL_COOLDOWN_SEC):
            await ctx.send(f"{ctx.author.mention} slow down — try again in a few seconds."); return

        if not _can_afford(a, amount):
            await ctx.send(f"{ctx.author.mention} you only have **{_fmt_bread(a['balance'])}**."); return
        if not _can_afford(t, amount):
            await ctx.send(f"{member.mention} doesn’t have enough to cover **{_fmt_bread(amount)}**."); return

        bot._duels[ch_id] = {
            "challenger_id": ctx.author.id,
            "target_id": member.id,
            "amount": int(amount),
            "created_ts": _now()
        }

    await ctx.send(f"🎲 {ctx.author.mention} challenges {member.mention} to a duel for **{_fmt_bread(amount)}** each! "
                   f"{member.mention} type `!accept` or `!decline` (expires in {DUEL_EXPIRE_SEC}s).")

@bot.command(name="accept", help="Accept the current channel duel")
async def accept(ctx):
    ch_id = ctx.channel.id
    async with economy_lock:
        d = bot._duels.get(ch_id)
        if not d:
            await ctx.send("No pending duel here."); return
        if _now() - d["created_ts"] > DUEL_EXPIRE_SEC:
            bot._duels.pop(ch_id, None)
            await ctx.send("That duel expired."); return
        if ctx.author.id != d["target_id"]:
            await ctx.send("Only the challenged user can accept."); return

        c = _user(d["challenger_id"])
        t = _user(d["target_id"])
        amt = d["amount"]

        if not _can_afford(c, amt) or not _can_afford(t, amt):
            bot._duels.pop(ch_id, None)
            await ctx.send("One of you can’t cover the stake anymore. Duel canceled."); return

        # deduct stakes (escrow into bank)
        c["balance"] -= amt
        t["balance"] -= amt
        pot = amt * 2

        rake = int(pot * DUEL_RAKE_PCT) if DUEL_RAKE_PCT > 0 else 0
        pot_after_rake = pot - rake
        if rake > 0:
            economy["treasury"] = min(TREASURY_MAX, economy["treasury"] + rake)

        # roll 1-100 each
        roll_c = random.randint(1, 100)
        roll_t = random.randint(1, 100)
        rerolls = 0
        while roll_c == roll_t and rerolls < 5:
            roll_c = random.randint(1, 100)
            roll_t = random.randint(1, 100)
            rerolls += 1

        if roll_c > roll_t:
            winner_id = d["challenger_id"]
        else:
            winner_id = d["target_id"]

        w = _user(winner_id)
        new_bal = w["balance"] + pot_after_rake
        final_bal, skim = _cap_wallet(new_bal)
        w["balance"] = final_bal
        economy["treasury"] = min(TREASURY_MAX, economy["treasury"] + skim)

        bot._duels.pop(ch_id, None)
        await _save_bank()

    await ctx.send(
        f"🎲 Duel result!\n"
        f"<@{d['challenger_id']}> rolled **{roll_c}** · <@{d['target_id']}> rolled **{roll_t}**\n"
        f"Winner: <@{winner_id}> — took **{_fmt_bread(pot_after_rake)}**"
        + (f" (rake to bank **{_fmt_bread(rake)}**)" if DUEL_RAKE_PCT > 0 else "")
        + (f" (cap skim **{_fmt_bread(skim)}** back to bank)" if skim else "")
    )

@bot.command(name="decline", help="Decline the current channel duel")
async def decline(ctx):
    ch_id = ctx.channel.id
    async with economy_lock:
        d = bot._duels.get(ch_id)
        if not d:
            await ctx.send("No pending duel here."); return
        if ctx.author.id not in (d["target_id"], d["challenger_id"]):
            await ctx.send("Only the challenger or the challenged user can decline."); return
        bot._duels.pop(ch_id, None)
    await ctx.send("Duel canceled. Cowardice is a strategy 😏")

# ---- Slots ----
def _slots_spin():
    return (random.choice(SLOTS_REELS[0]),
            random.choice(SLOTS_REELS[1]),
            random.choice(SLOTS_REELS[2]))

def _slots_payout(multis: dict, r):
    s = "".join(r)
    if r[0] == r[1] == r[2]:
        key = s
        if key in multis:
            return multis[key]
        return 6.0
    if r[0] == r[1]:
        return multis.get("PAIR_ANY", 1.5)
    return 0.0

@bot.command(name="slots", help="Spin the slots: !slots 100  — 3-of-a-kind or pairs pay out")
async def slots(ctx, amount: int = None):
    if not _is_gamble_channel(ctx.channel.id):
        await ctx.send(f"Casino floor is only open in <#{GAMBLE_CHANNEL_ID}>."); return
    if amount is None or amount <= 0:
        await ctx.send("Usage: `!slots amount`"); return

    async with economy_lock:
        u = _user(ctx.author.id)

        since = _now() - float(u.get("last_roll", 0.0))
        if since < SLOTS_COOLDOWN_SEC:
            await ctx.send(f"{ctx.author.mention} hold up — {int(SLOTS_COOLDOWN_SEC - since)}s cooldown."); return

        max_bet = _dynamic_max_bet(economy["treasury"], u["balance"])
        if amount > max_bet:
            await ctx.send(PHRASES["gamble_max"].format(maxb=_fmt_bread(max_bet))); return
        if not _can_afford(u, amount):
            await ctx.send(f"{ctx.author.mention} you only have **{_fmt_bread(u['balance'])}**."); return

        u["balance"] -= amount
        economy["treasury"] = min(TREASURY_MAX, economy["treasury"] + amount)

        reels = _slots_spin()
        mult = _slots_payout(SLOTS_PAYTABLE, reels)
        gross_win = int(amount * mult) if mult > 0 else 0

        skim_line = ""
        if gross_win > 0:
            pay = min(economy["treasury"], gross_win)
            new_bal = u["balance"] + pay
            final_bal, skim = _cap_wallet(new_bal)
            u["balance"] = final_bal
            economy["treasury"] -= max(0, pay - skim)
            if skim:
                skim_line = f" (cap skim **{_fmt_bread(skim)}** back to bank)"
        else:
            if SLOTS_JP_CUT > 0:
                add = int(amount * SLOTS_JP_CUT)
                move = min(add, economy["treasury"])
                economy["treasury"] -= move
                economy["jackpot_pool"] = economy.get("jackpot_pool", JP_MIN_POOL) + move

        u["last_roll"] = _now()
        await _save_bank()

    sym = " ".join(reels)
    if gross_win > 0:
        await ctx.send(f"🎰 {sym} → You win **{_fmt_bread(gross_win)}**!{skim_line}  new: **{_fmt_bread(u['balance'])}**")
    else:
        await ctx.send(f"🎰 {sym} → no luck! new: **{_fmt_bread(u['balance'])}**  "
                       f"({'+ progressive pot' if SLOTS_JP_CUT>0 else 'better luck next time'})")

# ---- Raffle (start/join/draw with auto-draw watcher) ----
@bot.command(name="raffle", help="Start or join a server raffle: !raffle start 200 | !raffle join | !raffle draw")
async def raffle(ctx, action: str = None, amount: int = None):
    gid = ctx.guild.id
    now = _now()

    if action is None:
        await ctx.send("Usage: `!raffle start <amount>` | `!raffle join` | `!raffle draw`")
        return

    if action.lower() == "start":
        if not amount or amount <= 0:
            await ctx.send("Usage: `!raffle start <entry_amount>`"); return

        async with economy_lock:
            if gid in bot._raffles:
                await ctx.send("A raffle is already running. Use `!raffle join` or wait for it to end."); return
            u = _user(ctx.author.id)
            if not _can_afford(u, amount):
                await ctx.send(f"{ctx.author.mention} you only have **{_fmt_bread(u['balance'])}**."); return

            u["balance"] -= amount
            pot = amount
            bot._raffles[gid] = {
                "channel_id": ctx.channel.id,
                "amount": amount,
                "pot": pot,
                "entrants": {ctx.author.id},
                "host_id": ctx.author.id,
                "end_ts": now + RAFFLE_JOIN_DEADLINE_SEC
            }
            await _save_bank()

        await ctx.send(f"🎟️ {ctx.author.mention} started a raffle! Entry fee: **{_fmt_bread(amount)}**. "
                       f"Type `!raffle join` to enter! Drawing in {RAFFLE_JOIN_DEADLINE_SEC}s.")

    elif action.lower() == "join":
        async with economy_lock:
            r = bot._raffles.get(gid)
            if not r:
                await ctx.send("No active raffle to join."); return
            if now > r["end_ts"]:
                await ctx.send("Raffle entry period is over. Wait for the draw."); return
            if ctx.author.id in r["entrants"]:
                await ctx.send(f"{ctx.author.mention} you’re already entered."); return

            u = _user(ctx.author.id)
            if not _can_afford(u, r["amount"]):
                await ctx.send(f"{ctx.author.mention} you don’t have **{_fmt_bread(r['amount'])}**."); return

            u["balance"] -= r["amount"]
            r["pot"] += r["amount"]
            r["entrants"].add(ctx.author.id)
            await _save_bank()

        await ctx.send(f"{ctx.author.mention} joined the raffle! Pot is now **{_fmt_bread(r['pot'])}** with {len(r['entrants'])} entrants.")

    elif action.lower() == "draw":
        async with economy_lock:
            r = bot._raffles.get(gid)
            if not r:
                await ctx.send("No active raffle."); return
            if ctx.author.id != r["host_id"] and not ctx.author.guild_permissions.manage_guild:
                await ctx.send("Only the raffle host or a mod can draw."); return
            if len(r["entrants"]) < 2:
                await ctx.send("Not enough entrants to draw."); return

            winner_id = random.choice(list(r["entrants"]))
            rake = int(r["pot"] * RAFFLE_RAKE_PCT) if RAFFLE_RAKE_PCT > 0 else 0
            prize = r["pot"] - rake
            if rake > 0:
                economy["treasury"] = min(TREASURY_MAX, economy["treasury"] + rake)

            w = _user(winner_id)
            new_bal = w["balance"] + prize
            final_bal, skim = _cap_wallet(new_bal)
            w["balance"] = final_bal
            economy["treasury"] = min(TREASURY_MAX, economy["treasury"] + skim)

            bot._raffles.pop(gid, None)
            await _save_bank()

        await ctx.send(f"🎉 The raffle is over! Winner: <@{winner_id}> — prize **{_fmt_bread(prize)}** "
                       + (f"(rake to bank **{_fmt_bread(rake)}**)" if rake else "")
                       + (f"(cap skim **{_fmt_bread(skim)}** back to bank)" if skim else ""))

    else:
        await ctx.send("Invalid action. Use `start`, `join`, or `draw`.")

@tasks.loop(seconds=RAFFLE_WATCH_INTERVAL_SEC)
async def raffle_watcher():
    """
    Every few seconds:
      - If a raffle reached its deadline:
         * If entrants >= RAFFLE_MIN_ENTRANTS → auto-draw and pay winner
         * Else → auto-cancel and refund all entries
    """
    now = _now()
    to_draw: List[Tuple[int, dict]] = []   # (guild_id, raffle)
    to_cancel: List[Tuple[int, dict]] = [] # (guild_id, raffle)

    async with economy_lock:
        for gid, r in list(getattr(bot, "_raffles", {}).items()):
            if now >= r.get("end_ts", 0):
                if len(r.get("entrants", [])) >= RAFFLE_MIN_ENTRANTS:
                    to_draw.append((gid, r))
                else:
                    to_cancel.append((gid, r))

        announcements = []

        for gid, r in to_draw:
            winner_id = random.choice(list(r["entrants"]))
            rake = int(r["pot"] * RAFFLE_RAKE_PCT) if RAFFLE_RAKE_PCT > 0 else 0
            prize = r["pot"] - rake
            if rake > 0:
                economy["treasury"] = min(TREASURY_MAX, economy["treasury"] + rake)

            w = _user(winner_id)
            new_bal = w["balance"] + prize
            final_bal, skim = _cap_wallet(new_bal)
            w["balance"] = final_bal
            economy["treasury"] = min(TREASURY_MAX, economy["treasury"] + skim)

            bot._raffles.pop(gid, None)

            announcements.append((
                r["channel_id"],
                f"🎉 **Raffle auto-draw!** Winner: <@{winner_id}> — prize **{_fmt_bread(prize)}** "
                + (f"(rake to bank **{_fmt_bread(rake)}**)" if rake else "")
                + (f" (cap skim **{_fmt_bread(skim)}** back to bank)" if skim else "")
            ))

        for gid, r in to_cancel:
            refund_each = int(r["amount"])
            skim_total = 0
            for uid in list(r["entrants"]):
                u = _user(uid)
                new_bal = u["balance"] + refund_each
                final_bal, skim = _cap_wallet(new_bal)
                u["balance"] = final_bal
                skim_total += skim
            if skim_total:
                economy["treasury"] = min(TREASURY_MAX, economy["treasury"] + skim_total)

            bot._raffles.pop(gid, None)
            announcements.append((
                r["channel_id"],
                "⏰ Raffle expired (not enough entrants). All entries have been **refunded**."
                + (f" (cap skim total **{_fmt_bread(skim_total)}** back to bank)" if skim_total else "")
            ))

        if to_draw or to_cancel:
            await _save_bank()

    for ch_id, text in announcements:
        ch = bot.get_channel(ch_id)
        if ch:
            try:
                await ch.send(text)
            except Exception:
                pass

@raffle_watcher.before_loop
async def _wait_raffle_ready():
    await bot.wait_until_ready()

# ================== QoL Casino Commands ==================
@bot.command(name="odds", help="Show your current max bet and estimated win chance for that bet")
async def odds(ctx, bet: int | None = None):
    async with economy_lock:
        u = _user(ctx.author.id)
        max_b = _dynamic_max_bet(economy["treasury"], u["balance"])
        if DAILY_ROLL_LOSS_CAP > 0:
            loss_room = max(1, DAILY_ROLL_LOSS_CAP - int(u.get("roll_loss_today", 0)))
            max_b = min(max_b, loss_room)
        if not bet or bet <= 0: bet = max_b
        p = _est_win_prob(bet)
    await ctx.send(f"Max bet right now: **{_fmt_bread(max_b)}** · Estimated win chance for {bet} is **{p*100:.1f}%**")

@bot.command(name="jackpot", help="Show the progressive jackpot pot")
async def jackpot(ctx):
    async with economy_lock:
        pot = int(economy.get("jackpot_pool", 0))
    await ctx.send(f"🎰 Progressive pot: **{_fmt_bread(pot)}**")

# ================== Admin Commands ==================
from discord.ext import commands as _admin

AIR_DROP_ADMIN_ID = 939225086341296209

@bot.command(name="seed", help="ADMIN: Seed bread to the bank or a user. Usage: !seed @user 500  |  !seed bank 2000")
@_admin.has_permissions(manage_guild=True)
async def seed(ctx, target: str = None, amount: int = None):
    if target is None or amount is None or amount <= 0:
        await ctx.send("Usage: `!seed @user 500` or `!seed bank 2000`"); return

    if target.lower() == "bank":
        async with economy_lock:
            before_treasury = economy["treasury"]
            bank_room = max(0, TREASURY_MAX - economy["treasury"])
            mint_room = _remaining_mint_room()
            allow = min(amount, bank_room, mint_room)
            if allow <= 0:
                await ctx.send(f"❌ Cannot add to bank — global cap reached ({TOTAL_MAX_CURRENCY:,}).")
                return
            economy["treasury"] += allow
            added = economy["treasury"] - before_treasury
            await _save_bank()
        await ctx.send(PHRASES["seed_bank"].format(added=_fmt_bread(added), vault=_fmt_bread(economy['treasury'])))
        return

    member = ctx.message.mentions[0] if ctx.message.mentions else None
    if not member:
        try:
            member = await ctx.guild.fetch_member(int(target))
        except Exception:
            member = None
    if not member:
        await ctx.send("I couldn't find that user. Mention them or use their ID."); return

    async with economy_lock:
        if economy["treasury"] <= 0:
            await ctx.send(PHRASES["no_funds"]); return
        give = min(amount, economy["treasury"])
        u = _user(member.id)
        new_bal = u["balance"] + give
        final_bal, skim = _cap_wallet(new_bal)
        economy["treasury"] -= (give - skim)
        u["balance"] = final_bal
        await _save_bank()

    msg = PHRASES["seed_user"].format(user=member.mention, give=_fmt_bread(give), bal=_fmt_bread(final_bal))
    if skim: msg += f" (cap skim {_fmt_bread(skim)} back to bank)"
    await ctx.send(msg)

@seed.error
async def seed_error(ctx, error):
    if isinstance(error, _admin.MissingPermissions):
        await ctx.send("You need **Manage Server** to use this, babe. 💅")
    else:
        await ctx.send("Seed failed. Usage: `!seed @user 500` or `!seed bank 2000`")

@bot.command(name="take", help="ADMIN: Take bread from a user into the bank. Usage: !take @user 100")
@_admin.has_permissions(manage_guild=True)
async def take(ctx, target: str = None, amount: int = None):
    if target is None or amount is None or amount <= 0:
        await ctx.send("Usage: `!take @user 100`"); return

    # Removed '!take bank' burn path — burning disabled.
    member = ctx.message.mentions[0] if ctx.message.mentions else None
    if not member:
        try:
            member = await ctx.guild.fetch_member(int(target))
        except Exception:
            member = None
    if not member:
        await ctx.send("I couldn't find that user. Mention them or use their ID."); return

    async with economy_lock:
        u = _user(member.id)
        amt = min(amount, u["balance"])
        u["balance"] -= amt
        economy["treasury"] = min(TREASURY_MAX, economy["treasury"] + amt)
        await _save_bank()
    await ctx.send(PHRASES["take_user"].format(amt=_fmt_bread(amt), user=member.mention, bal=_fmt_bread(u['balance'])))

@take.error
async def take_error(ctx, error):
    if isinstance(error, _admin.MissingPermissions):
        await ctx.send("You need **Manage Server** to use this, babe. 💅")
    else:
        await ctx.send("Take failed. Usage: `!take @user 100`")

@bot.command(name="setbal", help="ADMIN: Set a user's exact balance. Usage: !setbal @user 5000")
@_admin.has_permissions(manage_guild=True)
async def setbal(ctx, member: discord.Member = None, amount: int = None):
    if member is None or amount is None or amount < 0:
        await ctx.send("Usage: `!setbal @user 5000`"); return

    async with economy_lock:
        u = _user(member.id)
        amount = min(amount, USER_WALLET_CAP)
        delta = amount - u["balance"]
        if delta > 0:
            take_amt = min(delta, economy["treasury"])
            u["balance"] += take_amt
            delta_applied = take_amt
            economy["treasury"] -= take_amt
        else:
            give_back = min(-delta, TREASURY_MAX - economy["treasury"])
            u["balance"] -= give_back
            delta_applied = -give_back
            economy["treasury"] += give_back
        await _save_bank()

    await ctx.send(PHRASES["setbal_user"].format(
        user=member.mention, bal=_fmt_bread(u["balance"]),
        delta=_fmt_bread(delta_applied), vault=_fmt_bread(economy["treasury"])
    ))

# ================== DB Debug Commands (admin) ==================
@bot.command(name="dbstatus", help="ADMIN: Show DB status + economy row info")
@_admin.has_permissions(manage_guild=True)
async def dbstatus(ctx):
    if not db_pool:
        await ctx.send("DB: not connected ❌"); return
    async with db_pool.acquire() as con:
        await con.execute("SET search_path TO public")
        row = await con.fetchrow("SELECT value FROM public.kv WHERE key='economy'")
        if not row:
            await ctx.send("DB: connected ✅ · economy row: (missing)"); return
        val = row["value"]
        if isinstance(val, str):
            try: val = json.loads(val)
            except Exception: val = {}
        users = val.get("users", {}) if isinstance(val, dict) else {}
        treasury = val.get("treasury") if isinstance(val, dict) else None
        await ctx.send(f"DB: connected ✅ · economy row: present · users={len(users)} · treasury={treasury}")

@bot.command(name="dbreload", help="ADMIN: Force reload economy from DB")
@_admin.has_permissions(manage_guild=True)
async def dbreload(ctx):
    await _load_bank()
    await ctx.send("Reloaded economy from DB.")

@bot.command(name="dbdump", help="ADMIN: Show first 600 chars of economy JSON")
@_admin.has_permissions(manage_guild=True)
async def dbdump(ctx):
    if not db_pool:
        await ctx.send("DB: not connected ❌"); return
    async with db_pool.acquire() as con:
        row = await con.fetchrow("SELECT value FROM public.kv WHERE key='economy'")
        if not row:
            await ctx.send("No 'economy' row in DB."); return
        val = row["value"]
        if isinstance(val, str):
            try: val = json.loads(val)
            except Exception: pass
        txt = json.dumps(val)[:600] if isinstance(val, (dict, list)) else str(val)[:600]
        await ctx.send(f"```json\n{txt}\n...```")

# ================== Fun / Media Commands ==================
@bot.command(name="cafe", help="owl y lark")
async def cafe(ctx, *, term: str = "coffee"):
    query = term if term else "coffee"
    async with ctx.channel.typing():
        gif = await fetch_gif(query)
    await ctx.send(gif if gif else "☕")

@bot.command(name="scam", help="Show current BTC & ETH prices (USD, bratty style)")
async def scam(ctx):
    async with ctx.channel.typing():
        url = ("https://api.coingecko.com/api/v3/simple/price"
           "?ids=bitcoin,ethereum&vs_currencies=usd&include_24hr_change=true")
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, timeout=15) as r:
                    data = await r.json() if r.status == 200 else None
        except Exception:
            data = None
    if not data or "bitcoin" not in data or "ethereum" not in data:
        await ctx.send("Ugh 🙄 can't even get the prices rn... this is SO scammy 💅"); return
    def _fmt_price(p: float) -> str: return f"${p:,.2f}"
    def _fmt_change(ch: float) -> str:
        return f"{ch:+.2f}%"
    btc = data["bitcoin"]["usd"]; btc_ch = data["bitcoin"].get("usd_24h_change", 0.0)
    eth = data["ethereum"]["usd"]; eth_ch = data["ethereum"].get("usd_24h_change", 0.0)
    msg = (
        f"✨ **SCAM ALERT** ✨\n"
        f"BTC is at {_fmt_price(btc)} ({_fmt_change(btc_ch)}) — like… are you KIDDING me?? 😤\n"
        f"ETH is {_fmt_price(eth)} ({_fmt_change(eth_ch)}) — ew… who’s buying this rn??? 🙄\n"
        f"Send me money instead 💗 $fergielicious"
    )
    await ctx.send(msg)

@bot.command(name="bbl", help="see fergies culo")
async def bbl(ctx):
    gif_url = "https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExM2dmMnE4Z2xjdmMwZnN4bmplamMxazFlZTF0Z255MndxZGpqNGdkNyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/PMwewC6fjVkje/giphy.gif"
    await ctx.send(gif_url)

@bot.command(name="hawaii", help="see vivvy's vacation pix")
async def hawaii(ctx):
    await ctx.send(random.choice(HAWAII_IMAGES))

# ---- Kewchie commands ----
@bot.command(name="kewchie", help="Post a random Kali Uchis song from the playlist (in the kewchie channel)")
async def kewchie(ctx):
    if ctx.channel.id != KEWCHIE_CHANNEL_ID:
        await ctx.send(f"Use this in <#{KEWCHIE_CHANNEL_ID}>"); return
    links = await _fetch_playlist_tracks(SPOTIFY_PLAYLIST_ID)
    if not links:
        await ctx.send("Playlist isn't available right now 😭"); return
    await ctx.send(random.choice(links))

@bot.command(name="kewchie-debug", help="Debug Spotify playlist setup")
async def kewchie_debug(ctx):
    cid_set = bool(SPOTIFY_CLIENT_ID); sec_set = bool(SPOTIFY_CLIENT_SECRET)
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

# ---- FIT command & auto daily ----
@bot.command(name="fit", help="fergie's fits")
async def fit(ctx):
    if ctx.channel.id != FIT_CHANNEL_ID:
        await ctx.send(f"Use this in <#{FIT_CHANNEL_ID}>"); return
    url = random.choice(FIT_IMAGE_URLS)
    msg = await ctx.send(f"OMFG look at this one girlie!!! we neeeeeeeeed! 💗\n{url}")
    bot._fit_waiting[msg.id] = _now() + 20

@tasks.loop(hours=24)
async def fit_auto_daily():
    ch = bot.get_channel(FIT_CHANNEL_ID)
    if not ch: return
    url = random.choice(FIT_IMAGE_URLS)
    msg = await ch.send(f"OMFG look at this one girlie!!! we neeeeeeeeed! 💗\n{url}")
    bot._fit_waiting[msg.id] = _now() + 20

@fit_auto_daily.before_loop
async def _fit_wait_ready():
    await bot.wait_until_ready()

# ================== Custom Help: !halp ==================
from discord import Embed, Colour

def _mention_channel(ch_id: int) -> str:
    return f"<#{ch_id}>" if ch_id else "`(not set)`"

@bot.command(name="halp", help="Shows an embedded help menu")
async def halp(ctx, *, command: str | None = None):
    if command:
        cmd = bot.get_command(command)
        if not cmd:
            await ctx.send(f"Couldn't find a command named `{command}`.")
            return

        aliases = ", ".join(cmd.aliases) if getattr(cmd, "aliases", None) else "None"
        usage = f"!{cmd.qualified_name} {cmd.signature}".strip()
        e = Embed(
            title=f"Command: !{cmd.qualified_name}",
            description=(cmd.help or "No details provided."),
            colour=Colour.blurple()
        )
        e.add_field(name="Usage", value=f"`{usage}`", inline=False)
        e.add_field(name="Aliases", value=aliases, inline=False)
        await ctx.send(embed=e)
        return

    e = Embed(
        title="🍞 Bot Help",
        description="Here’s everything I can do. Use `!halp <command>` for details on one command.",
        colour=Colour.blurple()
    )

    e.add_field(
        name="Notes",
        value=(
            f"• Casino commands only work in {_mention_channel(GAMBLE_CHANNEL_ID)}\n"
            f"• `!fit` only works in {_mention_channel(FIT_CHANNEL_ID)}\n"
            f"• `!kewchie` only works in {_mention_channel(KEWCHIE_CHANNEL_ID)}"
        ),
        inline=False
    )

    e.add_field(
        name="💰 Economy",
        value=(
            "`!bank` — Show remaining bank vault\n"
            "`!balance` / `!bal` / `!wallet` — See your (or someone else’s) balance\n"
            "`!claim` — Claim daily allowance (24h cooldown, requires savings)\n"
            "`!gift @user amount` — Gift bread (daily cap + tax tiers)\n"
            "`!lb` / `!richlist` — Top 10 richest"
        ),
        inline=False
    )

    e.add_field(
        name="🎲 Casino (only in casino channel)",
        value=(
            "`!roll <amount|all|half>` — Bet vs bank (win prob scales; jackpot on `all`)\n"
            "`!putasos @user` — Try to rob someone (low success, fail hurts)\n"
            "`!duel @user <amount>` — PvP dice duel (escrowed stakes; winner takes pot)\n"
            "`!slots <amount>` — Spin 3 reels; 3-of-a-kind or pairs pay out\n"
            "`!raffle start <amt>` / `!raffle join` / `!raffle draw` — Server raffle (auto-draw at deadline)\n"
            "`!odds [bet]` — Show max bet & estimated win chance\n"
            "`!jackpot` — Show progressive jackpot pot"
        ),
        inline=False
    )

    e.add_field(
        name="🎉 Fun & Media",
        value=(
            "`!cafe [term]` — owl y lark\n"
            "`!scam` — BTC/ETH prices (bratty style)\n"
            "`!bbl` — see fergies culo\n"
            "`!hawaii` — see vivvy's vacation pix"
        ),
        inline=False
    )

    e.add_field(
        name="👗 Fit (fashion)",
        value=(
            "`!fit` — fergie's fits (fit channel only). If a specific user replies within 20s, "
            "I send a cheeky follow-up."
        ),
        inline=False
    )

    e.add_field(
        name="🎵 Kewchie (Kali Uchis)",
        value=(
            "`!kewchie` — Post a random playlist track (kewchie channel only)\n"
            "`!kewchie-debug` — Debug Spotify playlist setup"
        ),
        inline=False
    )

    e.add_field(
        name="🛠️ Admin (Manage Server required)",
        value=(
            "`!seed bank <amt>` — Refill bank (respects global cap)\n"
            "`!seed @user <amt>` — Give bread (respects wallet cap)\n"
            "`!take @user <amt>` — Take from user to bank (no burning)\n"
            "`!setbal @user <amt>` — Set a user’s exact balance (capped to wallet)"
        ),
        inline=False
    )

    e.add_field(
        name="⏱️ Automated Behaviors (FYI)",
        value=(
            "• Bread GIF every 4h; bread emoji every 6h\n"
            "• Daily scam post (70% chance)\n"
            "• 8am PT: auto allowance for all members + inactivity penalties\n"
            "• `USER1_ID`: pings twice daily; reacts to “pinche fergie”; random 3x/day “bonk papo”\n"
            "• `USER2_ID`: pings twice daily with “shooo cornman!”\n"
            "• `USER3_ID`: random replies (35% of their msgs) + ping every 8h\n"
            "• `LOBO_ID`: once/day “send me money lobo.” when they post\n"
            "• `!fit`: 20s follow-up if the target user replies to the fit post"
        ),
        inline=False
    )

    e.set_footer(text="Tip: try `!halp roll` or `!halp gift` for specific usage.")
    await ctx.send(embed=e)

# ================== Version Command ==================
@bot.command(name="version", help="Show bot version and runtime status")
async def version(ctx):
    from discord import Embed, Colour
    db_status = "connected ✅" if (DATABASE_URL and db_pool) else ("no DATABASE_URL ❌" if not DATABASE_URL else "not connected ❌")
    fields = [
        ("Version", BOT_VERSION + (f" ({BUILD_TAG})" if BUILD_TAG else "")),
        ("DB", db_status),
        ("Casino Channel", f"<#{GAMBLE_CHANNEL_ID}>"),
        ("Fit Channel", f"<#{FIT_CHANNEL_ID}>"),
        ("Kewchie Channel", f"<#{KEWCHIE_CHANNEL_ID}>"),
    ]
    e = Embed(title="Bot Version", colour=Colour.blurple())
    for n, v in fields:
        e.add_field(name=n, value=v, inline=False)
    await ctx.send(embed=e)

# ================== Start ==================
if __name__ == "__main__":
    if not TOKEN or not TENOR_KEY or not CHANNEL_ID:
        raise SystemExit("Please set DISCORD_TOKEN, TENOR_API_KEY, and CHANNEL_ID environment variables.")
    # Final tiny typo fix for earlier block (safe at runtime)
    if 'REACTION_EMOETS' in globals():
        pass
    bot.run(TOKEN)
