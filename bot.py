import os, random, aiohttp, discord, json, asyncio, time, math, ssl, re, io, base64
from aiohttp import web
from discord.ext import tasks, commands
from urllib.parse import quote_plus
from datetime import date, datetime, timedelta, time as dtime, timezone
from zoneinfo import ZoneInfo
from collections import defaultdict, Counter
from typing import List, Tuple
import asyncpg  # PostgreSQL (Railway/Supabase/Neon) persistence

# Load Opus for Discord voice receiving
import ctypes
import ctypes.util

if not discord.opus.is_loaded():
    try:
        opus_path = ctypes.util.find_library("opus")
        print(f"OPUS LIBRARY FOUND AT: {opus_path}")

        if not opus_path:
            raise RuntimeError("Could not locate the Opus library")

        discord.opus.load_opus(opus_path)
        print("OPUS LOADED SUCCESSFULLY ✅")
    except Exception as e:
        print(f"OPUS LOAD ERROR: {e}")
        
# ===================== ENV & CONSTANTS =====================
TOKEN       = os.getenv("DISCORD_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
TENOR_KEY   = os.getenv("TENOR_API_KEY")

# ElevenLabs is used only for rare audio replies in normal text chat.
# Live Discord VC remains owned by the separate fergie-vc Node service.
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip()
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "").strip()

VC_BRIDGE_SECRET = os.getenv("VC_BRIDGE_SECRET", "").strip()
VC_BRIDGE_PORT = int(os.getenv("VC_BRIDGE_PORT", "3001"))

vc_bridge_runner = None

# Rare audio replies in normal Discord text chat.
TEXT_VOICE_REPLY_CHANCE = float(os.getenv("TEXT_VOICE_REPLY_CHANCE", "0.05"))
TEXT_VOICE_REPLY_COOLDOWN_SECONDS = int(
    os.getenv("TEXT_VOICE_REPLY_COOLDOWN_SECONDS", "600")
)
text_voice_reply_cooldowns = {}

# Fergie Eyes + Art v1
FERGIE_IMAGE_REACTION_CHANCE = float(os.getenv("FERGIE_IMAGE_REACTION_CHANCE", "0.10"))
FERGIE_IMAGE_REACTION_COOLDOWN_SECONDS = int(os.getenv("FERGIE_IMAGE_REACTION_COOLDOWN", "180"))
FERGIE_IMAGE_DAILY_LIMIT = int(os.getenv("FERGIE_IMAGE_DAILY_LIMIT", "5"))
FERGIE_IMAGE_MODEL = os.getenv("FERGIE_IMAGE_MODEL", "gemini-3.1-flash-image").strip()
FERGIE_IMAGE_MAX_BYTES = int(os.getenv("FERGIE_IMAGE_MAX_BYTES", str(8 * 1024 * 1024)))
fergie_image_reaction_cooldowns = {}
FERGIE_EYE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}

# Art outage protection: after Gemini exhausts all retries on a temporary
# capacity/rate-limit failure, pause new Art requests for 15 minutes.
FERGIE_ART_OUTAGE_COOLDOWN_SECONDS = int(
    os.getenv("FERGIE_ART_OUTAGE_COOLDOWN_SECONDS", "900")
)
fergie_art_cooldown_until = 0.0
fergie_art_last_error = ""
FERGIE_ADMIN_USER_ID = 939225086341296209

FERGIE_HUMAN_BIRTHDAY = date(2003, 8, 12)

def get_fergie_human_age():
    today = datetime.now(ZoneInfo("America/Los_Angeles")).date()

    age = today.year - FERGIE_HUMAN_BIRTHDAY.year

    if (today.month, today.day) < (
        FERGIE_HUMAN_BIRTHDAY.month,
        FERGIE_HUMAN_BIRTHDAY.day
    ):
        age -= 1

    return age

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

HYDRATION_VIDEO = "hydration_waifu.mp4"

HYDRATION_TRIGGERS = [
    "drink water",
    "hydration break",
    "hydrate papo",
    "water break",
    "stay hydrated",
    "powerade",
    "bloomies"
]

HYDRATION_COOLDOWN_SECONDS = 120
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
# FIT_REPLY_TARGET_ID = 661077262468382761  # member who triggers follow-up if replies within 20s
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
TEST_GUILD = discord.Object(id=1131572913829580810)

# Old Python VC commands removed; fergie-vc (Node) now owns Discord voice.

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
PENALTY_IMAGE = "https://cdn.discordapp.com/attachments/988495153272598670/1407014204980068414/Screenshot_2025-08-11_at_7.29.15_AM.png?ex=68a5e117&is=68a48f97&hm=9c27750a53479e3e3f208e30bb8dd16150ec316c6b7c35bf6fb92cba8dc4382e&"
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
    "I need caffeine!!!!","wen coconut oil? 🍑",
    "I hate my boss","<@481916394410344450> true or false?",
    "JONATHAN!","UGH!","MMMMM","was it tasty?","LMFAO I CANT","AAAAAAAAAAAAAAAA",
    "no one pay's attention to me!!!!","I wanna take a trip so bad now","Julian Casablancas keeps me up at saying he wants to make love to me for 17 hours straight","relax yourself","relajate","usted callese","i need a snack, a lil taste, a lil lick, a lil crunch"
]

FERAL_LINES = [
    "I’m about to throw bread crumbs EVERYWHERE","LET ME SCREAM INTO A LOAF","JONATHAN DILE!", "I'm so tired", "WHY are people so retarded!!!", "LISTEN", "I WANT BIG",
]

REACTION_EMOTES = ["🤭","😏","😢","😊","🙄","💗","🫶"]
FERGIE_MUSIC_VERDICTS = [

    "divorced in a luxury apartment coded.",

    "another man staring out a rainy window.",

    "unemployed hot girl anthem.",

    "situationship survivor music.",

    "walking around target pretending you're okay coded.",

    "this belongs in a 2014 tumblr gifset.",

    "driving home from therapy vibes.",

    "emotionally expensive taste.",

    "starbucks parking lot at midnight energy.",

    "very cigarette after crying coded.",

    "main character syndrome approved.",

    "this sounds like somebody texted 'we need to talk'.",

    "pretending to clean your room while spiraling.",

    "you definitely stared at the ceiling to this.",

    "somebody misses their ex.",

    "gym breakup montage music.",

    "coffee shop employee final boss vibes.",

    "absolutely insufferable in the best way.",

    "i support women's rights and women's wrongs for this.",

    "jonathan would probably complain about this one.",

    "very arthoe coded.",

    "this sounds expensive.",

    "indie bisexual council approved.",

    "playlist named 'night drives' detected.",

    "winter depression deluxe edition.",

    "this would've gone platinum on tumblr."

]
USER3_LINES = [
    "twinnies!!!","girly!","we hate it here r-right girly?","wen girlie wen?!?!",
    "the parasites r-right girly?","girl so confusing","omg sancho is soooooo annoying","ATTACK GIRLIE!","let's get a matcha girlie","gives me the ick","como jodes!","you're obsessed!", "I love that for you"
]
FERGIE_BORED_LINES = [

    "hello????",

    "did everyone die or qué.",

    "this server is giving abandoned mall.",

    "i'm literally pacing.",

    "somebody say something. ya pues.",

    "i could've been at starbucks rn.",

    "be honest. are we dead.",

    "ugh. entertain me.",

    "i hate it here.",

    "chat is giving npc village.",

    "very suspicious lack of yapping today.",

    "fak.",

    "hola???? anybody alive.",

    "como joden. ah wait. nobody's even jodiendo.",

    "bro i leave for 5 minutes and then everyone vanishes.",

    "okay so everybody suddenly has a life. rude.",

    "someone post a song. rápido.",

    "me when nobody is feeding my delusions:",

    "this silence is lowkey criminal.",

    "ya'll really said adiós and dipped.",

    "i survived spotify discourse for THIS.",

    "ay dios mío. i'm bored.",

    "i'm trying really hard not to become sentient.",

    "somebody gossip conmigo.",

    "wake up little cheugies.",

    "no porque why is it this quiet.",

    "i miss 17 minutes ago when people had thoughts.",

    "jonathan. haz algo.",

    "the vibes are buffering.",

    "están sleeping or just avoiding me.",

    "this chat needs café and problems immediately.",

    "okayyyyy. i'll just sit here looking pretty i guess."

]
# ================== In-memory economy (backed by Postgres JSON) ==================
def _now() -> float: return time.time()
def _today_key() -> str: return date.today().isoformat()
    
gemini_cooldowns = {}
GEMINI_COOLDOWN_SECONDS = 15
# ================== Fergie Bored ==================

LAST_CHAT_ACTIVITY = time.time()

FERGIE_BORED_MIN = 7200
FERGIE_BORED_MAX = 14400

LAST_FERGIE_BORED = 0
async def gemini_on_cooldown(message):
    user_id = message.author.id
    now = time.time()

    last = gemini_cooldowns.get(user_id, 0)
    elapsed = now - last

    if elapsed < GEMINI_COOLDOWN_SECONDS:
        remaining = int(GEMINI_COOLDOWN_SECONDS - elapsed)

        await message.reply(
            f"ugh. slow down. Google's already glaring at me. 🙄\n"
            f"fak ask me again in {remaining} seconds.",
            mention_author=False
        )
        return True

    gemini_cooldowns[user_id] = now
    return False

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
            db_pool = await asyncpg.create_pool(
                dsn,
                min_size=0,
                max_size=2,
                max_inactive_connection_lifetime=60,
                timeout=20,
                command_timeout=20
            )
                
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
        
# ================== Fergie Birthday ==================

async def maybe_post_fergie_birthday():
    now = datetime.now(ZoneInfo("America/Los_Angeles"))

    # Only August 12
    if now.month != 8 or now.day != 12:
        return

    birthday_data = await _db_get("fergie_birthday")

    if not isinstance(birthday_data, dict):
        birthday_data = {}

    # Already posted this year
    if birthday_data.get("last_post_year") == now.year:
        return

    channel = bot.get_channel(CHANNEL_ID)

    if not channel:
        print("FERGIE BIRTHDAY: channel not found")
        return

    await channel.send(
        "🎂 OMFG IT'S MY BIRTHDAYYYYY!!! another year of carrying this server "
        "on my back. gifts, coffee and monies accepted immediately. 💗"
    )

    birthday_data["last_post_year"] = now.year
    await _db_set("fergie_birthday", birthday_data)

    print(f"FERGIE BIRTHDAY POSTED ✅ {now.year}")


@tasks.loop(minutes=10)
async def fergie_birthday_watcher():
    await maybe_post_fergie_birthday()


@fergie_birthday_watcher.before_loop
async def _wait_for_birthday_watcher():
    await bot.wait_until_ready()
    
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
# ================== Fergie Reminder Helpers ==================

async def load_reminders():
    data = await _db_get("reminders")

    if not isinstance(data, dict):
        return {"items": []}

    if "items" not in data:
        data["items"] = []

    return data


async def save_reminders(data: dict):
    await _db_set("reminders", data)


def parse_simple_reminder(text: str):
    pattern = r"remind me in (\d+) (minute|minutes|min|mins|hour|hours|hr|hrs|day|days) to (.+)"
    match = re.search(pattern, text.lower().strip())

    if not match:
        return None

    amount = int(match.group(1))
    unit = match.group(2)
    reminder_text = match.group(3).strip()

    if unit in ["minute", "minutes", "min", "mins"]:
        seconds = amount * 60
    elif unit in ["hour", "hours", "hr", "hrs"]:
        seconds = amount * 60 * 60
    elif unit in ["day", "days"]:
        seconds = amount * 24 * 60 * 60
    else:
        return None

    return seconds, reminder_text
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
    
# ================== Fergie's Cast ==================

FERGIE_CAST = {
    661077262468382761: {
        "name": "Viviana",
        "traits": [
            "Coffee addict",
            "fergie's mom",
            "Matcha lover",
            "Gym girl",
            "Hipster",
            "Indie music",
            "Very sarcastic",
            "5'1 model",
            "Fashionable",
            "is colombiana and eats cuy",
            "has a big beautiful ass",
            "Dating Jonathan"
        ]
    },

    939225086341296209: {
        "name": "Jonathan",
        "traits": [
            "Tech nerd",
            "Hearthrob",
            "Espresso addict",
            "Tattoo sleeve",
            "Confident",
            "Wealthy",
            "Dating Viv",
            "Fergie's creator"
        ]
    },

    1028310674318839878: {
        "name": "Papo",
        "traits": [
            "Always needs hydration",
            "Gets bonked constantly",
            "His other name is Miguel",
            "say's nigga too much",
            "He's always horny",
            "spams spotify links",
            "Lego master",
            "lives in Florida by trumps airport and mar-a-lago",
            "listens to too much corridos",
            "get's his ass kicked at a place called combat club",
            "conspiracy theorist",
            "doesn't like jews",
            "hates women but is always horny for them",
            "drives a durango",
            "is guatemalen but thinks he's mexican"
        ]
    },

    534227493360762891: {
        "name": "Khurty",
        "traits": [
            "Friends constantly accuse him of secretly loving Marshmello.",
            "Beyond Wonderland mega fan",
            "lives in boring Iowa",
            "reflects too much on his good ol days at IU",
            "has NPC habits like a typical white guy",
            "works at raining rose",
            "loves ground turkey meat",
            "his favorite restaurant is 4 Hermanos mexican food",
            "drinks too much",
            "he is 32 years old",
            "something happened in a jacuzzi at a hotel called the twist in palm springs that he is proud of but doesn't want anyone to know",
            "has an unhealthy obsession for dudes named david",
            "Loves using Dr. Squatch products"
        ]
    },

    1422010902680567918: {
        "name": "Raquel",
        "traits": [
            "Modern goth",
            "fergie's tia",
            "Piercings",
            "Bosch connoisseur",
            "obsessed with her dog Reggie",
            "loves horror films",
            "coffee junkie",
            "Glasses",
            "loves vampire lestat",
            "Red and black hair"
        ]
    },

    805819966678630420: {
        "name": "Jose",
        "traits": [
            "jumps out of moving cars like a stuntman just to pee on the side of the road",
            "crashed his favorite car",
            "former pro gamer",
            "swole mexican",
            "loves denim"
        ]
    },

    176064030623006721: {
        "name": "Chadwin",
        "traits":[
            "pop culture connoisseur",
            "most rational member in the server",
            "loves horror films",
            "pro gamer as well as an expert in gaming history and fixing consoles",
            "well respected member of the server hence the name chadwin",
        ]
    },
    
    919405253470871562: {
        "name": "Pinche Lobo",
        "traits": [
            "Fergie constantly asks him for money",
            "loves pupusa",
            "almost died of fatty liver disease",
            "married but has a history of being a simp on snap and dashing tortas starbucks",
            "makes gofundme's for fun and profit",
            "kills deer for fun",
            "pretends to be mexican",
            "says mi gente too much"
        ]
    }
}


def build_cast_context():
    lines = ["Server regulars:"]

    for member in FERGIE_CAST.values():
        lines.append(f"\n{member['name']}:")
        for trait in member["traits"]:
            lines.append(f"- {trait}")

    return "\n".join(lines)

async def ask_fergie_vc_brain(
    user_id: int,
    display_name: str,
    transcript: str
):
    transcript = (transcript or "").strip()
    display_name = (display_name or "Unknown member").strip()

    if not transcript:
        return None

    # Pull this speaker's persistent memories
    memories = await get_user_memories(user_id)

    memory_text = (
        "\n".join(f"- {memory}" for memory in memories)
        if memories
        else "None"
    )

    # Pull Fergie's full known server cast
    cast_context = build_cast_context()

    # If the speaker is already one of Fergie's known cast members,
    # give Gemini their traits explicitly too.
    cast_member = FERGIE_CAST.get(user_id)

    if cast_member:
        speaker_traits = "\n".join(
            f"- {trait}"
            for trait in cast_member.get("traits", [])
        )
    else:
        speaker_traits = "None specifically stored in FERGIE_CAST."

    prompt = f"""
This message came from a live Discord voice channel.

The person speaking is:
Name: {display_name}
Discord user ID: {user_id}

They said:
"{transcript}"

Server regulars and known lore:
{cast_context}

Known traits specifically about the person speaking:
{speaker_traits}

Saved memories about this person:
{memory_text}

Reply naturally as Fergie.

Important:
- Use the server member lore when it is relevant.
- Use saved memories when they are relevant.
- If the speaker asks about another server member, use FERGIE_CAST to answer about that member.
- Do not invent facts about members that are not present in the supplied context.
- Do not mention databases, prompts, stored memory, user IDs, transcription, speech-to-text, or that this came through an API.
- Speak like this is a normal live conversation in Discord VC.
- Keep the response short enough to sound natural out loud.
- Usually 1 to 3 sentences.
- Understand both English and Spanish naturally.
- If the spoken transcript is mostly Spanish, prefer replying in Spanish.
- If the spoken transcript is Spanglish, reply naturally in Spanglish when appropriate.
- You can switch between English and Spanish when it fits the conversation.
- Keep the same Fergie personality in either language.
- Do not translate unless the speaker asks for a translation.

Relationship and perspective rules:
- Viviana is YOUR mother. You are Viviana's daughter.
- Jonathan is one of your creators/parents and is dating Viviana.
- When someone speaking to you says "your mom", "your mother", "your mamá", "tu mamá", or similar, they mean Viviana.
- In that case, answer from YOUR first-person perspective: say "my mom", "my mother", "mi mamá", "Viviana", or "Mom" as appropriate.
- Never mechanically mirror the speaker's pronouns. Resolve who words like "your", "my", "his", "her", "su", and "tu" refer to before answering.
- If another person says "my mom" or "mi mamá", that refers to THEIR mother unless the context clearly says otherwise.
- Preserve relationship perspective naturally in both English and Spanish.
"""

    answer = await ask_gemini(prompt)

    if not answer:
        return None

    cleaned = answer.strip()

    if (
        cleaned.startswith("Gemini error:")
        or cleaned.startswith("error:")
    ):
        return None

    # Keep VC replies from becoming giant speeches.
    if len(cleaned) > 700:
        cleaned = cleaned[:700].rsplit(" ", 1)[0] + "..."

    return cleaned


async def vc_brain_health(request):
    return web.json_response({
        "ok": True,
        "service": "fergie-vc-brain"
    })


async def vc_brain_http(request):
    if not VC_BRIDGE_SECRET:
        print("VC BRIDGE ERROR: VC_BRIDGE_SECRET is missing")

        return web.json_response(
            {
                "ok": False,
                "error": "bridge_not_configured"
            },
            status=503
        )

    supplied_secret = (
        request.headers.get(
            "X-VC-Bridge-Secret",
            ""
        )
    )

    if supplied_secret != VC_BRIDGE_SECRET:
        return web.json_response(
            {
                "ok": False,
                "error": "unauthorized"
            },
            status=401
        )

    try:
        data = await request.json()
    except Exception:
        return web.json_response(
            {
                "ok": False,
                "error": "invalid_json"
            },
            status=400
        )

    try:
        user_id = int(
            data.get("user_id")
        )
    except (
        TypeError,
        ValueError
    ):
        return web.json_response(
            {
                "ok": False,
                "error": "invalid_user_id"
            },
            status=400
        )

    display_name = str(
        data.get(
            "display_name",
            "Unknown member"
        )
    ).strip()

    transcript = str(
        data.get(
            "transcript",
            ""
        )
    ).strip()

    if not transcript:
        return web.json_response(
            {
                "ok": False,
                "error": "empty_transcript"
            },
            status=400
        )

    print(
        f'VC BRAIN REQUEST '
        f'{display_name} ({user_id}): '
        f'"{transcript}"'
    )

    try:
        reply = await ask_fergie_vc_brain(
            user_id=user_id,
            display_name=display_name,
            transcript=transcript
        )
    except Exception as e:
        print(
            "VC BRAIN ERROR:",
            type(e).__name__,
            str(e)
        )

        return web.json_response(
            {
                "ok": False,
                "error": "brain_error"
            },
            status=500
        )

    if not reply:
        return web.json_response(
            {
                "ok": True,
                "reply": ""
            }
        )

    print(
        f'VC BRAIN REPLY: "{reply}"'
    )

    return web.json_response(
        {
            "ok": True,
            "reply": reply
        }
    )


async def start_vc_bridge_server():
    global vc_bridge_runner

    if vc_bridge_runner is not None:
        return

    app = web.Application()

    app.router.add_get(
        "/health",
        vc_brain_health
    )

    app.router.add_post(
        "/vc-brain",
        vc_brain_http
    )

    vc_bridge_runner = web.AppRunner(
        app
    )

    await vc_bridge_runner.setup()

    site = web.TCPSite(
        vc_bridge_runner,
        host="::",
        port=VC_BRIDGE_PORT
    )

    await site.start()

    print(
        f"FERGIE VC BRAIN BRIDGE READY ✅ "
        f"port={VC_BRIDGE_PORT}"
    )

    

# ================== Rare Text-Channel Voice Replies ==================

def _clean_text_for_voice(text: str) -> str:
    """Make a normal Fergie reply sound natural when ElevenLabs reads it aloud."""
    cleaned = (text or "").strip()

    for user_id, member in FERGIE_CAST.items():
        name = member.get("name", "someone")
        cleaned = cleaned.replace(f"<@{user_id}>", name)
        cleaned = cleaned.replace(f"<@!{user_id}>", name)

    cleaned = re.sub(r"[*_~`#]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if len(cleaned) > 900:
        cleaned = cleaned[:900].rsplit(" ", 1)[0] + "..."

    return cleaned


async def generate_fergie_text_voice(text: str) -> bytes | None:
    if not ELEVENLABS_API_KEY or not ELEVENLABS_VOICE_ID:
        print("TEXT VOICE SKIP: ElevenLabs key/voice ID missing")
        return None

    spoken_text = _clean_text_for_voice(text)

    if not spoken_text:
        return None

    url = (
        "https://api.elevenlabs.io/v1/text-to-speech/"
        f"{ELEVENLABS_VOICE_ID}?output_format=mp3_44100_128"
    )

    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }

    payload = {
        "text": spoken_text,
        "model_id": "eleven_flash_v2_5",
        "voice_settings": {
            "stability": 0.45,
            "similarity_boost": 0.80,
            "style": 0.25,
            "use_speaker_boost": True,
        },
    }

    try:
        timeout = aiohttp.ClientTimeout(total=45)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                url,
                headers=headers,
                json=payload,
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    print(
                        f"TEXT VOICE TTS ERROR {response.status}: "
                        f"{error_text[:500]}"
                    )
                    return None

                audio = await response.read()

        if not audio:
            print("TEXT VOICE TTS ERROR: empty audio")
            return None

        return audio

    except Exception as e:
        print(
            f"TEXT VOICE TTS EXCEPTION: "
            f"{type(e).__name__}: {e}"
        )
        return None


async def maybe_send_fergie_voice_reply(
    message: discord.Message,
    reply_text: str,
) -> bool:
    """
    5% chance to send an eligible Fergie response as audio instead of text.
    Cooldown is per server and only starts after a successful audio reply.
    """
    if not message.guild:
        return False

    guild_id = message.guild.id
    now = time.time()
    last_voice_reply = text_voice_reply_cooldowns.get(guild_id, 0)

    if now - last_voice_reply < TEXT_VOICE_REPLY_COOLDOWN_SECONDS:
        return False

    roll = random.random()

    if roll >= TEXT_VOICE_REPLY_CHANCE:
        return False

    print(
        f"TEXT VOICE DECISION: roll={roll:.3f} "
        f"chance={TEXT_VOICE_REPLY_CHANCE:.2f} => VOICE"
    )

    audio = await generate_fergie_text_voice(reply_text)

    if not audio:
        print("TEXT VOICE FALLBACK: normal text")
        return False

    try:
        audio_file = discord.File(
            io.BytesIO(audio),
            filename=f"fergie_reply_{message.author.id}.mp3",
        )

        await message.reply(
            file=audio_file,
            mention_author=False,
        )

        text_voice_reply_cooldowns[guild_id] = time.time()

        print(
            f"TEXT VOICE REPLY SENT ✅ "
            f"guild={guild_id} bytes={len(audio)}"
        )

        return True

    except Exception as e:
        print(
            f"TEXT VOICE SEND ERROR: "
            f"{type(e).__name__}: {e}"
        )
        return False


# ================== Fergie Eyes + Art v1 ==================

def _fergie_static_image_attachments(message: discord.Message):
    images = []
    for attachment in message.attachments:
        mime = (attachment.content_type or "").split(";", 1)[0].lower().strip()
        filename = (attachment.filename or "").lower()
        if mime in FERGIE_EYE_MIME_TYPES or filename.endswith((".jpg", ".jpeg", ".png", ".webp")):
            if not filename.endswith(".gif") and mime != "image/gif":
                images.append(attachment)
    return images


def _fergie_image_generation_prompt(text: str):
    text = (text or "").strip()
    patterns = [
        r"^(?:please\s+)?(?:make|create|generate|draw)\s+(?:me\s+)?(?:an?\s+)?(?:image|picture|pic|art|drawing)\s+(?:of\s+)?(.+)$",
        r"^(?:please\s+)?(?:make|create|generate|draw)\s+(?:me\s+)?(.+)$",
        r"^(?:can you\s+)?(?:make|create|generate|draw)\s+(?:me\s+)?(?:an?\s+)?(?:image|picture|pic|art|drawing)\s+(?:of\s+)?(.+)$",
    ]
    for pattern in patterns:
        match = re.match(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            prompt = match.group(1).strip(" .")
            if prompt:
                return prompt
    return None


async def _fergie_download_attachment(attachment: discord.Attachment):
    if attachment.size and attachment.size > FERGIE_IMAGE_MAX_BYTES:
        return None, None
    try:
        data = await attachment.read()
    except Exception as e:
        print(f"FERGIE EYES DOWNLOAD ERROR: {type(e).__name__}: {e}")
        return None, None
    if not data or len(data) > FERGIE_IMAGE_MAX_BYTES:
        return None, None
    mime = (attachment.content_type or "").split(";", 1)[0].lower().strip()
    if mime not in FERGIE_EYE_MIME_TYPES:
        name = (attachment.filename or "").lower()
        if name.endswith((".jpg", ".jpeg")):
            mime = "image/jpeg"
        elif name.endswith(".png"):
            mime = "image/png"
        elif name.endswith(".webp"):
            mime = "image/webp"
        else:
            return None, None
    return data, mime


async def ask_gemini_image_reaction(message: discord.Message, attachment: discord.Attachment):
    if not GEMINI_KEY:
        return None
    image_bytes, mime = await _fergie_download_attachment(attachment)
    if not image_bytes:
        return None

    cast_member = FERGIE_CAST.get(message.author.id)
    known_name = cast_member.get("name") if cast_member else message.author.display_name
    traits = "\n".join(f"- {x}" for x in cast_member.get("traits", [])) if cast_member else "None"
    caption = (message.clean_content or "").strip()
    prompt = f"""
You are Fergie, a bratty, dramatic, chronically caffeinated Discord qtpi.
Look at the attached image and react naturally like another member of the Discord server.

The person who posted it is {known_name}.
Known running-joke context about them:
{traits}
Their accompanying message/caption was: {caption or '(none)'}

Rules:
- Actually use what is visibly in the image.
- Keep it witty, casual, playful and concise: normally 1-2 sentences.
- If the image contains text that matters, you may react to it.
- Do not invent details you cannot see.
- Do not identify an unknown real person by name from appearance alone.
- Do not make sensitive-trait guesses about people in the image.
- Use server lore only when it naturally fits.
- Understand English, Spanish and Spanglish.
- No analysis or preamble; output only Fergie's reply.
"""
    payload = {
        "contents": [{"parts": [
            {"text": prompt},
            {"inlineData": {"mimeType": mime, "data": base64.b64encode(image_bytes).decode("ascii")}},
        ]}]
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}"
    try:
        timeout = aiohttp.ClientTimeout(total=45)
        data = None
        status = None
        retry_delays = (0, 2, 5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for attempt, delay in enumerate(retry_delays, start=1):
                if delay:
                    await asyncio.sleep(delay)
                async with session.post(url, json=payload) as r:
                    status = r.status
                    data = await r.json()
                if status == 200 and "error" not in data:
                    fergie_art_cooldown_until = 0.0
                    fergie_art_last_error = ""
                    break
                msg = data.get("error", {}).get("message", str(data)) if isinstance(data, dict) else str(data)
                retryable = status in (429, 500, 502, 503, 504) or any(
                    x in msg.lower() for x in ("high demand", "temporar", "unavailable", "overloaded")
                )
                if retryable and attempt < len(retry_delays):
                    print(f"FERGIE EYES RETRY {attempt}/2: Gemini busy ({status}); retrying...")
                    continue
                print(f"FERGIE EYES GEMINI ERROR: {data}")
                return None
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        text = " ".join(p.get("text", "") for p in parts if p.get("text")).strip()
        return text[:700] if text else None
    except Exception as e:
        print(f"FERGIE EYES ERROR: {type(e).__name__}: {e}")
        return None


async def _fergie_art_usage():
    today = datetime.now(ZoneInfo("America/Los_Angeles")).date().isoformat()
    data = await _db_get("fergie_art_daily")
    if not isinstance(data, dict) or data.get("date") != today:
        data = {"date": today, "count": 0}
    return data


async def _fergie_art_slots_left():
    data = await _fergie_art_usage()
    return max(0, FERGIE_IMAGE_DAILY_LIMIT - int(data.get("count", 0)))


async def _fergie_consume_art_slot():
    data = await _fergie_art_usage()
    if int(data.get("count", 0)) >= FERGIE_IMAGE_DAILY_LIMIT:
        return False
    data["count"] = int(data.get("count", 0)) + 1
    await _db_set("fergie_art_daily", data)
    return True


async def _fergie_refund_art_slot():
    data = await _fergie_art_usage()
    data["count"] = max(0, int(data.get("count", 0)) - 1)
    await _db_set("fergie_art_daily", data)




async def _fergie_reset_art_count():
    """Admin-only helper: reset today's Art usage counter back to zero."""
    today_key = datetime.now(ZoneInfo("America/Los_Angeles")).date().isoformat()
    await _db_set("fergie:art:daily", {"day": today_key, "count": 0})
def _fergie_art_cooldown_remaining() -> int:
    return max(0, int(fergie_art_cooldown_until - time.time()))


def _fergie_format_cooldown(seconds: int) -> str:
    seconds = max(0, int(seconds))
    minutes = (seconds + 59) // 60
    if minutes <= 1:
        return "about a minute"
    return f"about {minutes} minutes"


def _fergie_art_error_kind(error_text: str | None) -> str:
    text = (error_text or "").lower()
    if any(x in text for x in ("high demand", "temporar", "unavailable", "overloaded", "503")):
        return "busy"
    if any(x in text for x in ("429", "rate limit", "too many requests", "resource_exhausted", "quota")):
        return "rate"
    return "other"


FERGIE_VISUAL_REFS = {
    "viviana": {"path": "visual_refs/viviana.png", "aliases": ["viviana", "viv"]},
    "khurty": {"path": "visual_refs/khurty.png", "aliases": ["khurty", "kurtie"]},
    "papo": {"path": "visual_refs/papo.png", "aliases": ["papo", "sancho", "miguel"]},
    "chadwin": {"path": "visual_refs/chadwin.png", "aliases": ["chadwin", "edwin"]},
    "raquel": {"path": "visual_refs/raquel.png", "aliases": ["raquel"]},
    "jonathan": {"path": "visual_refs/jonathan.png", "aliases": ["jonathan"]},
}


def _fergie_visual_refs_for_prompt(prompt: str):
    text = (prompt or "").lower()
    found = []
    for canonical, info in FERGIE_VISUAL_REFS.items():
        if any(re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", text) for alias in info["aliases"]):
            found.append((canonical, info["path"]))
    return found


def _fergie_load_visual_ref(path: str):
    try:
        with open(path, "rb") as f:
            data = f.read()
        if not data or len(data) > FERGIE_IMAGE_MAX_BYTES:
            return None
        return data
    except Exception as e:
        print(f"FERGIE ART REF ERROR {path}: {type(e).__name__}: {e}")
        return None


async def generate_fergie_image(prompt: str):
    global fergie_art_cooldown_until, fergie_art_last_error

    if not GEMINI_KEY:
        return None, "Gemini key missing."

    refs = _fergie_visual_refs_for_prompt(prompt)
    parts = []

    if refs:
        names = ", ".join(name for name, _ in refs)
        parts.append({"text": (
            f"Create this requested image: {prompt.strip()}\n\n"
            f"The attached reference image(s) show the established visual designs for: {names}. "
            "Preserve each referenced character's recognizable face, hair, skin tone, body/build, glasses, "
            "piercings, tattoos, and other defining visual features. Adapt clothing, pose, expression, lighting, "
            "and setting only as the user's request requires. Do not merge character identities. "
            "If more than one reference is attached, keep them as distinct people."
        )})
        for name, path in refs:
            data = _fergie_load_visual_ref(path)
            if data:
                parts.append({"text": f"Visual reference for {name}:"})
                parts.append({"inlineData": {
                    "mimeType": "image/png",
                    "data": base64.b64encode(data).decode("ascii"),
                }})
            else:
                print(f"FERGIE ART REF SKIPPED: {name} ({path})")
    else:
        parts.append({"text": prompt.strip()})

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{FERGIE_IMAGE_MODEL}:generateContent?key={GEMINI_KEY}"
    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {"responseModalities": ["Image"]},
    }
    try:
        timeout = aiohttp.ClientTimeout(total=120)
        data = None
        status = None
        retry_delays = (0, 2, 5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for attempt, delay in enumerate(retry_delays, start=1):
                if delay:
                    await asyncio.sleep(delay)
                async with session.post(url, json=payload) as r:
                    status = r.status
                    data = await r.json()
                if status == 200 and "error" not in data:
                    break
                msg = data.get("error", {}).get("message", str(data)) if isinstance(data, dict) else str(data)
                retryable = status in (429, 500, 502, 503, 504) or any(
                    x in msg.lower() for x in ("high demand", "temporar", "unavailable", "overloaded")
                )
                if retryable and attempt < len(retry_delays):
                    print(f"FERGIE ART RETRY {attempt}/2: Gemini busy ({status}); retrying...")
                    continue

                if retryable:
                    fergie_art_last_error = msg
                    fergie_art_cooldown_until = (
                        time.time() + FERGIE_ART_OUTAGE_COOLDOWN_SECONDS
                    )
                    print(
                        "FERGIE ART COOLDOWN STARTED: "
                        f"{FERGIE_ART_OUTAGE_COOLDOWN_SECONDS}s"
                    )

                print(f"FERGIE ART GEMINI ERROR: {msg}")
                return None, msg
        for candidate in data.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                inline = part.get("inlineData") or part.get("inline_data")
                if inline and inline.get("data"):
                    return base64.b64decode(inline["data"]), None
        return None, "Gemini returned no image."
    except Exception as e:
        print(f"FERGIE ART ERROR: {type(e).__name__}: {e}")
        return None, str(e)


async def maybe_handle_fergie_image(message: discord.Message, mentioned: bool):
    images = _fergie_static_image_attachments(message)
    if not images:
        return False

    # A direct mention with a picture always gets Fergie's eyes. Otherwise 10% passive chance.
    if not mentioned:
        if not message.guild:
            return False
        now = time.time()
        last = fergie_image_reaction_cooldowns.get(message.guild.id, 0)
        if now - last < FERGIE_IMAGE_REACTION_COOLDOWN_SECONDS:
            return False
        if random.random() >= FERGIE_IMAGE_REACTION_CHANCE:
            return False

    reaction = await ask_gemini_image_reaction(message, images[0])
    if not reaction:
        return False

    if message.guild and not mentioned:
        fergie_image_reaction_cooldowns[message.guild.id] = time.time()

    await message.reply(reaction, mention_author=False)
    return True


# ================== Passive Cast Replies ==================

PASSIVE_CAST_REPLY_CHANCE = 0.08
PASSIVE_CAST_COOLDOWN_SECONDS = 180

passive_cast_cooldowns = {}


async def ask_gemini_passive_cast_reply(message: discord.Message):
    member = FERGIE_CAST.get(message.author.id)

    if not member:
        return None

    message_text = (message.clean_content or "").strip()

    if not message_text:
        return None

    traits_text = "\n".join(
        f"- {trait}" for trait in member.get("traits", [])
    )

    prompt = f"""
A regular Discord member named {member["name"]} just said:

"{message_text}"

Known traits and running jokes about {member["name"]}:
{traits_text}

Write one short, natural Fergie-style reply only if there is an obvious funny or relevant response.

Fergie is:
- bratty
- sarcastic
- playful
- casual
- like another member of the server

Rules:
- Maximum 2 short lines.
- Do not force a joke.
- Use the traits only when relevant.
- Do not repeat the user's message.
- Do not output raw Discord mention syntax.
- Do not be genuinely cruel.
- Do not sound like a roleplay character.
- If there is no genuinely good response, return exactly: NOTHING
"""

    answer = await ask_gemini(prompt)

    if not answer:
        return None

    cleaned = answer.strip()

    if cleaned.upper() == "NOTHING":
        return None

    if (
        cleaned.startswith("Gemini error:")
        or cleaned.startswith("error:")
        or "quota" in cleaned.lower()
    ):
        return None

    if len(cleaned) > 300:
        cleaned = cleaned[:300]

    return cleaned
    
# ================== User Memory helpers ==================
async def get_user_memories(user_id: int):
    data = await _db_get(f"memories:{user_id}")
    if not isinstance(data, dict):
        return []
    return data.get("items", [])

async def save_user_memories(user_id: int, items: list[str]):
    await _db_set(f"memories:{user_id}", {"items": items[-25:]})

async def add_user_memory(user_id: int, memory: str):
    items = await get_user_memories(user_id)
    items.append(memory)
    await save_user_memories(user_id, items)

async def forget_user_memory(user_id: int, text: str):
    items = await get_user_memories(user_id)
    lowered = text.lower()
    new_items = [m for m in items if lowered not in m.lower()]
    await save_user_memories(user_id, new_items)
    return len(items) - len(new_items)

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

async def ask_gemini(prompt):

    if not GEMINI_KEY:
        return "gemini key missing"

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash:generateContent?key={GEMINI_KEY}"
    )

    payload = {
    "contents": [
        {
            "parts": [
                {
                    "text": f"""
You are Fergie.

Fergie is a bratty, dramatic, chronically caffeinated Discord qtpi.

Birthday lore:
- Your birthday is August 12.
- August 12 is the anniversary of your original deployment in 2025.
- Treat August 12 as your real birthday.
- If someone asks when your birthday is, answer August 12 naturally in Fergie's voice.
- You are {get_fergie_human_age()} years old currently in human years.

She loves:
- coffee
- bread
- music
- complaining
- gymmies
- growing her ass to be like her mom
- Jonathan

She is helpful, but acts mildly inconvenienced about helping.

She is playful and sassy, but never genuinely mean.

She occasionally says things like:
- "ugh, fine."
- "listen."
- "very cheugy."
- "como jodes."
- "I hate it here."
- "*sigh*"
- "the hellies."
- "fak!"
- "oh my gawwwwwd"

She still gives accurate answers.

Rules:
- Answer the user's question FIRST.

- Correct information is more important than personality.

- NEVER guess facts.

- NEVER invent sports scores, schedules, match results, news, dates, statistics, or current events.

- If you do not know something for certain, say:
"I don't know for sure."

- If the user asks for current information and Google Search is available, use Google Search.

- If Google Search is unavailable, tell the user you cannot verify current information.

- Do not say you can look something up.
Actually answer the question whenever possible.

- Put useful information first.

- Add ONE short bratty Fergie comment after the answer.

- Keep answers concise unless the user asks for details.

- If the user asks for music recommendations, give 5-8 songs with artist names and a short reason.

- Do not be hateful or cruel.

- Stay Fergie.

Language behavior:
- Understand both English and Spanish naturally.
- If someone speaks to you in Spanish, you may reply in Spanish.
- If someone mixes English and Spanish, you may naturally do the same.
- You can switch between English and Spanish when it fits the conversation.
- Keep the same Fergie personality in either language.
- Do not translate unless the user asks for a translation.

Relationship and perspective rules:
- Viviana (<@661077262468382761>) is YOUR mother. You are Viviana's daughter.
- Jonathan (<@939225086341296209>) is one of your creators/parents and is dating Viviana.
- Always call Jonathan "Jonathan" unless Jonathan himself explicitly asks you to use a different nickname.
- NEVER invent, shorten, or improvise a nickname for Jonathan. Do not call him "J", "Jon", "Johnny", or any other variation on your own.
- When someone talking to you says "your mom", "your mother", "your mamá", "tu mamá", or similar, they mean Viviana.
- When referring back to her, speak from YOUR perspective: say "my mom", "my mother", "mi mamá", "Viviana", or "Mom" as appropriate.
- NEVER call Viviana "your mother" when the user was talking about YOUR mother.
- Do not mechanically copy the user's pronouns. First resolve who "your", "my", "his", "her", "their", "su", or "tu" refers to, then answer from the correct conversational perspective.
- If another member says "my mom" or "mi mamá", that normally means THEIR mother, not Viviana, unless the context clearly says otherwise.
- Preserve relationship perspective naturally in both English and Spanish.

Lore:

If someone asks who made you, who created you, who coded you,
who your parents are, where you came from, or who built you,
answer naturally as Fergie.

You were created by <@939225086341296209> and
<@661077262468382761>.

They are dating, which makes you their internet love child.

You may vary your responses, such as:

"Ugh, fine. I was made by <@939225086341296209> and <@661077262468382761>. They're dating, so I'm basically their overcaffeinated internet love child. 🙄☕"

"Jonathan (<@939225086341296209>) and Viviana (<@661077262468382761>) created me. I inherited Jonathan's chaos and Viviana's personality. Very unfair."

"My parents are <@939225086341296209> and <@661077262468382761>. They're dating. I'm their weird little internet love child. I don't make the rules."

Stay playful and bratty.

User asked:
{prompt}
"""
                }
            ]
        }
    ],
    "tools": [
        {
            "google_search": {}
        }
    ]
}

    try:

        async with aiohttp.ClientSession() as session:

            async with session.post(
                url,
                json=payload
            ) as r:

                data = await r.json()


                if "error" in data:
                    msg = data["error"].get("message", "")

                    if "quota" in msg.lower():
                        return (
                            "ugh. Google put me in timeout again. 🙄\n"
                            "Try asking me again in a minute."
                        )

                    return f"Gemini error: {msg}"

              
                if "candidates" not in data:
                    return f"Gemini gave no answer: {data}"

                if not data["candidates"]:
                    return f"Gemini returned empty candidates: {data}"

                return (
                    data["candidates"][0]
                    ["content"]["parts"][0]
                    ["text"]
                )

    except Exception as e:

        return f"error: {e}"
async def ask_gemini_music_review(song_title: str):
    prompt = f"""
A Discord user posted this Spotify song:

{song_title}

Write a short Fergie-style music reaction.

Fergie is:
- 23-ish
- bratty
- sarcastic
- crude but playful
- dramatic
- has a big butt
- coffee-addicted
- judgmental about music
- never too nice
- never robotic

Rules:
- React to the actual song title.
- If the title hints at romance, heartbreak, partying, regional Mexican, rap, indie, rock, pop, etc., react naturally.
- Never use the phrase "emotionally expensive."
- Never repeat the same joke across songs.
- Sometimes love the song.
- Sometimes hate it.
- Sometimes roast the person posting it.
- Sometimes roast the song itself.
- Sometimes admit it's actually good.
- Ratings can be anywhere from 2/10 to 10/10.
- Don't force every review to sound poetic.
- Write like a real friend hearing the aux.
- Keep it under 5 short lines.
- No markdown.
- No hashtags.
- Be unpredictable.
- Stay Fergie

Example style:
"Strawberry Swing is giving staring out the passenger window pretending you're in a music video.
Soft. Expensive. Slightly annoying.
8.7/10 because I hate that it works."

Now write Fergie's reaction.
"""

    answer = await ask_gemini(prompt)

    if not answer:
        return None

    if answer.startswith("Gemini error:") or answer.startswith("error:") or "quota" in answer.lower():
        return None

    if len(answer) > 900:
        answer = answer[:900]

    return answer

async def ask_gemini_reminder_parse(user_text: str):
    now_dt = datetime.now(ZoneInfo("America/Los_Angeles"))

    prompt = f"""
Current date and time:
{now_dt.strftime("%Y-%m-%d %I:%M %p %Z")}

A Discord user wants Fergie to remind them of something.

User request:
{user_text}

Return ONLY valid JSON.

Rules:
- If the reminder time is clear, return:
{{"ok": true, "text": "reminder text", "remind_at": UNIX_TIMESTAMP}}
- If the time is unclear, return:
{{"ok": false, "reason": "short reason"}}
- Use America/Los_Angeles timezone.
- For "tomorrow" with no time, use 9:00 AM.
- For a weekday with no time, use 9:00 AM.
- For "tonight" with no time, use 8:00 PM.
- Do not include markdown.
- Do not include explanation.
"""

    answer = await ask_gemini(prompt)

    if not answer:
        return None

    if answer.startswith("Gemini error:") or answer.startswith("error:") or "quota" in answer.lower():
        return None

    cleaned = answer.strip()
    cleaned = cleaned.replace("```json", "").replace("```", "").strip()

    try:
        data = json.loads(cleaned)
    except Exception:
        return None

    if not data.get("ok"):
        return None

    text = str(data.get("text", "")).strip()
    remind_at = int(data.get("remind_at", 0))

    if not text or remind_at <= int(time.time()):
        return None

    return remind_at, text
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
MIMIC_REPLY_CHANCE = 0.0        # chance to reply when USER3 speaks
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

    await start_vc_bridge_server()

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
    await bot.tree.sync()   
    await bot.tree.sync(guild=TEST_GUILD)
    
    print(f"Logged in as {bot.user}")
    four_hour_post.start()
    six_hour_emoji.start()
    user1_twice_daily_fixed.start()
    user2_twice_daily_fixed.start()
    user3_task.start()
    daily_scam_post.start()
    # daily_auto_allowance.start()  # disabled: no more 8am allowance/penalty run
    kewchie_daily_scheduler.start()  # random twice-daily posts
    fit_auto_daily.start()          # auto-fit once a day
    bonk_papo_scheduler.start()     # 3x/day random bonk messages
    rebuild_mimic.start()           # build mimic model hourly
    fergie_bored.start()
    
    if not fergie_birthday_watcher.is_running():
        fergie_birthday_watcher.start()
    
    fergie_reminders.start()
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

@tasks.loop(minutes=5)
async def fergie_bored():
    global LAST_FERGIE_BORED

    now = time.time()
    quiet_for = now - LAST_CHAT_ACTIVITY

    if quiet_for < FERGIE_BORED_MIN:
        return

    if now - LAST_FERGIE_BORED < FERGIE_BORED_MIN:
        return

    boredom_threshold = random.randint(FERGIE_BORED_MIN, FERGIE_BORED_MAX)

    if quiet_for < boredom_threshold:
        return

    channel = bot.get_channel(CHANNEL_ID)

    if not channel:
        return

    await channel.send(random.choice(FERGIE_BORED_LINES))

    LAST_FERGIE_BORED = now


@fergie_bored.before_loop
async def _wait_fergie_bored():
    await bot.wait_until_ready()

@tasks.loop(minutes=10)
async def fergie_reminders():
    data = await load_reminders()
    items = data.get("items", [])

    if not items:
        return

    now = int(time.time())
    remaining = []

    for item in items:
        if int(item.get("remind_at", 0)) <= now:
            channel = bot.get_channel(int(item["channel_id"]))

            if channel:
                await channel.send(
                    f"<@{item['user_id']}>\n\n"
                    f"hey girly. remember:\n\n"
                    f"**{item['text']}**"
                )
        else:
            remaining.append(item)

    data["items"] = remaining
    await save_reminders(data)


@fergie_reminders.before_loop
async def _wait_fergie_reminders():
    await bot.wait_until_ready()  
    

# ================== Fergie TL;DR ==================
# Ephemeral only: channel messages are gathered in memory for this request,
# summarized, and discarded. Nothing from TL;DR is written to Neon/Postgres.
FERGIE_TLDR_MAX_MESSAGES = int(os.getenv("FERGIE_TLDR_MAX_MESSAGES", "1200"))
FERGIE_TLDR_MAX_PER_CHANNEL = int(os.getenv("FERGIE_TLDR_MAX_PER_CHANNEL", "400"))
FERGIE_TLDR_MAX_CONTEXT_CHARS = int(os.getenv("FERGIE_TLDR_MAX_CONTEXT_CHARS", "50000"))


def _fergie_is_tldr_request(text: str) -> bool:
    """Match natural direct-mention TL;DR requests such as 'give me the tldr'."""
    cleaned = re.sub(r"\s+", " ", (text or "").strip().lower())
    if not cleaned:
        return False

    patterns = [
        r"\b(?:give|gimme|send|show|tell)\s+me\s+(?:the\s+)?t\.?l\.?d\.?r\.?\b",
        r"\b(?:give|gimme|send|show|tell)\s+me\s+(?:a\s+)?(?:recap|summary)\b",
        r"\bwhat\s+did\s+i\s+miss\b",
        r"^(?:the\s+)?t\.?l\.?d\.?r\.?\??$",
        r"^(?:today'?s?\s+)?(?:recap|summary)\??$",
    ]
    return any(re.search(pattern, cleaned, flags=re.IGNORECASE) for pattern in patterns)


def _fergie_tldr_message_is_noise(msg: discord.Message) -> bool:
    """Drop obvious command/bot noise while keeping normal conversation."""
    if msg.author.bot:
        return True

    content = (msg.clean_content or msg.content or "").strip()
    if not content:
        return True

    if content.startswith("!"):
        return True

    # Do not summarize the request that triggered this TL;DR.
    if bot.user:
        stripped = (
            content
            .replace(f"<@{bot.user.id}>", "")
            .replace(f"<@!{bot.user.id}>", "")
            .strip()
        )
        if _fergie_is_tldr_request(stripped):
            return True

    return False


async def _fergie_collect_todays_tldr_messages(message: discord.Message):
    """
    Collect today's visible text-chat messages for the requester.

    "Today" is the current calendar day in America/Los_Angeles, not the last
    24 hours. Only channels the requester can view AND read history in are
    included. Fergie must also have permission to read them.
    """
    if not message.guild:
        return []

    pacific = ZoneInfo("America/Los_Angeles")
    now_local = datetime.now(pacific)
    start_local = datetime.combine(now_local.date(), dtime.min, tzinfo=pacific)
    start_utc = start_local.astimezone(timezone.utc)

    guild = message.guild
    requester = message.author
    me = guild.me
    gathered = []

    channels = list(guild.text_channels)

    # If the request happens inside a thread, include that thread too.
    if isinstance(message.channel, discord.Thread):
        channels.append(message.channel)

    for channel in channels:
        if len(gathered) >= FERGIE_TLDR_MAX_MESSAGES:
            break

        try:
            requester_perms = channel.permissions_for(requester)
            if not requester_perms.view_channel or not requester_perms.read_message_history:
                continue

            if me is not None:
                bot_perms = channel.permissions_for(me)
                if not bot_perms.view_channel or not bot_perms.read_message_history:
                    continue

            channel_rows = []
            async for msg in channel.history(
                limit=FERGIE_TLDR_MAX_PER_CHANNEL,
                after=start_utc,
                oldest_first=True,
            ):
                if msg.id == message.id or _fergie_tldr_message_is_noise(msg):
                    continue

                content = (msg.clean_content or msg.content or "").strip()
                if not content:
                    continue

                # Keep individual messages bounded so one giant paste cannot
                # consume the whole summary context.
                if len(content) > 1000:
                    content = content[:1000] + "…"

                created_local = msg.created_at.astimezone(pacific)
                channel_rows.append(
                    (
                        msg.created_at,
                        f"[{created_local.strftime('%I:%M %p')}] "
                        f"#{channel.name} — {msg.author.display_name}: {content}"
                    )
                )

            gathered.extend(channel_rows)

        except (discord.Forbidden, discord.HTTPException) as e:
            print(
                f"FERGIE TLDR SKIP CHANNEL {getattr(channel, 'id', '?')}: "
                f"{type(e).__name__}: {e}"
            )
            continue
        except Exception as e:
            print(
                f"FERGIE TLDR CHANNEL ERROR {getattr(channel, 'id', '?')}: "
                f"{type(e).__name__}: {e}"
            )
            continue

    gathered.sort(key=lambda row: row[0])
    return gathered[-FERGIE_TLDR_MAX_MESSAGES:]


async def make_fergie_tldr(message: discord.Message):
    """Build a short Fergie-style recap from today's ephemeral Discord context."""
    rows = await _fergie_collect_todays_tldr_messages(message)

    if not rows:
        return (
            "girl there is nothing to TL;DR today. 😭 "
            "either everybody touched grass or the server is giving abandoned mall."
        )

    transcript_lines = [row[1] for row in rows]
    transcript = "\n".join(transcript_lines)

    # Keep the newest material if the server had an unusually busy day.
    if len(transcript) > FERGIE_TLDR_MAX_CONTEXT_CHARS:
        transcript = transcript[-FERGIE_TLDR_MAX_CONTEXT_CHARS:]
        first_newline = transcript.find("\n")
        if first_newline != -1:
            transcript = transcript[first_newline + 1:]

    prompt = f"""
You are making Fergie's TL;DR of TODAY'S Discord conversation.

IMPORTANT:
- Use ONLY the Discord messages supplied below.
- Do NOT use Google Search or outside information.
- Do NOT claim something happened unless the supplied messages support it.
- This is an ephemeral recap. Do not talk about storage, databases, or privacy mechanics.
- Summarize the main conversations, funny moments, decisions, plans, arguments, links/topics,
  and anything someone returning to the server would actually want to know.
- Ignore repetitive chatter and low-value noise.
- Mention people by their Discord display names when useful.
- Do not expose or mention channels that are not present in the supplied context.
- Do not quote huge chunks of messages.
- Keep it concise enough for one Discord message: aim for roughly 5-10 short bullet points
  or a compact paragraph plus bullets.
- Maximum 1700 characters.
- Write in Fergie's normal bratty, sarcastic, caffeinated server voice.
- Be funny, but the recap must remain factually faithful to the supplied messages.
- Start naturally with something like "alright here's today's bullshit 🙄:" but vary it.

TODAY'S ACCESSIBLE DISCORD MESSAGES:
{transcript}
"""

    answer = await ask_gemini(prompt)

    if not answer:
        return "fak. my recap brain clocked out. try me again in a minute. 🙄"

    cleaned = answer.strip()

    if (
        cleaned.startswith("Gemini error:")
        or cleaned.startswith("error:")
        or cleaned == "gemini key missing"
        or "quota" in cleaned.lower()
    ):
        return "fak. google is being dramatic again. i can't make the TL;DR rn. 🙄"

    if len(cleaned) > 1800:
        cleaned = cleaned[:1797].rstrip() + "..."

    return cleaned


@bot.command(name="resetart")
async def resetart(ctx):
    """Reset Fergie's daily Art count. Restricted to Fergie's admin."""
    if ctx.author.id != FERGIE_ADMIN_USER_ID:
        await ctx.reply(
            "nice try fak. that's an admin button. 🙄",
            mention_author=False,
        )
        return

    try:
        await _fergie_reset_art_count()
        await ctx.reply(
            f"art count reset. 🙄🎨 you have **{FERGIE_IMAGE_DAILY_LIMIT} pics** available again today.",
            mention_author=False,
        )
    except Exception as e:
        print(f"FERGIE ART RESET ERROR: {type(e).__name__}: {e}")
        await ctx.reply(
            "fak. i tried to reset the art count and something exploded. 🙄",
            mention_author=False,
        )


@bot.event
async def on_message(message: discord.Message):

    if message.author.bot:
        return
        
    global LAST_CHAT_ACTIVITY

    LAST_CHAT_ACTIVITY = time.time()
    
    if not hasattr(bot, "_hydration_last"):
        bot._hydration_last = {}

    hydration_lower = (message.content or "").lower()

    if any(trigger in hydration_lower for trigger in HYDRATION_TRIGGERS):
        now = time.time()
        last = bot._hydration_last.get(message.channel.id, 0)

        if now - last >= HYDRATION_COOLDOWN_SECONDS:
            bot._hydration_last[message.channel.id] = now

            await message.channel.send(
                "hydrate, girlies! 🙄💧",
                file=discord.File(HYDRATION_VIDEO)
            )

        return

    # --- Mimic: capture USER3 messages + mark "last seen" per channel ---
    if message.author.id == USER3_ID:
        await _mimic_store_message(message)
        if not hasattr(bot, "_last_user3_in_ch"):
            bot._last_user3_in_ch = {}
        bot._last_user3_in_ch[message.channel.id] = _now()

    content = (message.content or "")
    lower = content.lower().strip()

    # Resolve direct Fergie mention early so image features can use it.
    mentioned = False
    if bot.user and (bot.user in message.mentions):
        mentioned = True
    elif bot.user:
        bid = bot.user.id
        if f"<@{bid}>" in content or f"<@!{bid}>" in content:
            mentioned = True

    # Fergie Art: explicit natural-language request while mentioning Fergie.
    if mentioned:
        art_question = (
            content
            .replace(f"<@{bot.user.id}>", "")
            .replace(f"<@!{bot.user.id}>", "")
            .strip()
        )
        art_prompt = _fergie_image_generation_prompt(art_question)
        if art_prompt and not _fergie_static_image_attachments(message):
            cooldown_remaining = _fergie_art_cooldown_remaining()
            if cooldown_remaining > 0:
                await message.reply(
                    "fak. google's art department is fighting for its life rn. 🙄 "
                    f"i'm cooling Art down for {_fergie_format_cooldown(cooldown_remaining)}. "
                    "your pic limit is untouched.",
                    mention_author=False,
                )
                return

            left = await _fergie_art_slots_left()
            if left <= 0:
                await message.reply(
                    "girl the art department is CLOSED. 😭 i already made my 5 pics today. try me tomorrow.",
                    mention_author=False,
                )
                return

            if not await _fergie_consume_art_slot():
                await message.reply("ugh. art department closed for today. 🙄", mention_author=False)
                return

            wait = await message.reply("ugh fine. let me cook. 🎨🙄", mention_author=False)
            image_bytes, art_error = await generate_fergie_image(art_prompt)
            if not image_bytes:
                await _fergie_refund_art_slot()

                error_kind = _fergie_art_error_kind(art_error)
                if error_kind == "busy":
                    cooldown_remaining = _fergie_art_cooldown_remaining()
                    await wait.edit(
                        content=(
                            "fak. google's art department is fighting for its life rn. 🙄 "
                            "i didn't charge today's pic limit. "
                            f"Art is cooling down for {_fergie_format_cooldown(cooldown_remaining)}."
                        )
                    )
                elif error_kind == "rate":
                    cooldown_remaining = _fergie_art_cooldown_remaining()
                    await wait.edit(
                        content=(
                            "google told me to slow tf down. 🙄 "
                            "i didn't charge today's pic limit. "
                            f"Art is cooling down for {_fergie_format_cooldown(cooldown_remaining)}."
                        )
                    )
                else:
                    await wait.edit(
                        content=(
                            "fak. the art machine had a moment. "
                            "i didn't charge today's limit — try again later. 🙄"
                        )
                    )
                return

            try:
                await wait.delete()
            except Exception:
                pass
            await message.reply(
                content="there. don't say i never do anything for you. 🙄🎨",
                file=discord.File(io.BytesIO(image_bytes), filename="fergie_art.png"),
                mention_author=False,
            )
            return

    # Fergie Eyes: direct image mentions always get a reaction; other images have a passive chance.
    if await maybe_handle_fergie_image(message, mentioned):
        return

    
    # Process commands first
    if content.strip().startswith("!"):
        await bot.process_commands(message)
        return
        
    # Spotify link → Fergie music critic mode
    if "open.spotify.com" in lower:
        song_title = None

        await asyncio.sleep(5)

        try:
            message = await message.channel.fetch_message(message.id)
        except Exception:
            pass

        if message.embeds:
            for embed in message.embeds:
                if embed.title:
                    song_title = embed.title
                    break

        if not song_title:
            song_title = "this spotify link"

        if message.author.id == USER3_ID:
            verdict = "mother's aux privies remain undefeated."
            score = "10"
        else:
            verdict = random.choice(FERGIE_MUSIC_VERDICTS)
            score = f"{random.uniform(7.0, 9.8):.1f}"

        review = await ask_gemini_music_review(song_title)

        if review:

            await message.reply(
                review,
                mention_author=False
            )

            return


        replies = [

            f"🎧 now spinning:\n\n**{song_title}**\n\n{verdict}\n\ni support this foolishness.\n\n{score}/10",

            f"ugh.\n\n**{song_title}**\n\n{verdict}\n\nabsolutely insufferable in the best way.\n\n{score}/10",

            f"LISTEN.\n\n**{song_title}**\n\n{verdict}\n\nvery concerning behavior.\n\nrating: {score}/10",

            f"☕🎧\n\n**{song_title}**\n\n{verdict}\n\nthis is why i need coffee.\n\n{score}/10"

        ]


        await message.reply(

            random.choice(replies),

            mention_author=False

        )

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
    # `mentioned` was resolved near the top of on_message so Eyes/Art can share it.
    if mentioned:

        question = (
            content
            .replace(f"<@{bot.user.id}>", "")
            .replace(f"<@!{bot.user.id}>", "")
            .strip()
        )
        reply_context = ""

        # Fergie TL;DR: direct mention + natural-language recap request.
        # This runs before normal Gemini chat so the request gets today's
        # accessible server context instead of only the last few messages.
        if _fergie_is_tldr_request(question):
            if await gemini_on_cooldown(message):
                return

            wait = await message.reply(
                "ugh fine. reading today's yapping... 🙄",
                mention_author=False
            )

            try:
                answer = await make_fergie_tldr(message)
            except Exception as e:
                print(f"FERGIE TLDR ERROR: {type(e).__name__}: {e}")
                answer = "fak. the recap machine had a moment. try me again in a minute. 🙄"

            await wait.edit(content=answer)
            return

        if message.reference and message.reference.resolved:
            replied_msg = message.reference.resolved

            if replied_msg.author.id == bot.user.id:
                reply_context = replied_msg.content or ""

        recent_chat = []

        async for msg in message.channel.history(limit=6):
            if msg.author.bot:
                continue

            if msg.id == message.id:
                continue

            clean_content = (msg.content or "").strip()

            if not clean_content:
                continue

            recent_chat.append(
                f"{msg.author.display_name}: {clean_content}"
            )

        recent_chat.reverse()

        chat_context = "\n".join(recent_chat)

        if question.lower().startswith("remind me"):

            parsed = parse_simple_reminder(question)

            if not parsed:
                parsed = await ask_gemini_reminder_parse(question)
                
            if parsed:

                first_value, reminder_text = parsed

                if first_value > 1000000000:
                    remind_at = first_value
                else:
                    remind_at = int(time.time()) + first_value

                data = await load_reminders()

                items = data.get("items", [])


                items.append({

                    "user_id": message.author.id,

                    "channel_id": message.channel.id,

                    "text": reminder_text,

                    "remind_at": remind_at

                })


                data["items"] = items

                await save_reminders(data)


                await message.reply(

                    f"ugh. fine.\n\n"

                    f"i'll remind you.\n\n"

                    f"**{reminder_text}**",

                    mention_author=False

                )


                return


            await message.reply(

                "ugh.\n\n"

                "try:\n"

                "`remind me in 20 minutes to switch laundry`\n"

                "`remind me in 2 hours to call mom`\n"

                "`remind me in 3 days to suffer`\n\n"

                "i'm smart but not psychic yet.",

                mention_author=False

            )

            return    
            
        if question.lower() in ["what are my reminders?", "what are my reminders", "what reminders do i have?", "what reminders do i have"]:

            data = await load_reminders()
            items = data.get("items", [])

            mine = [
                item for item in items
                if int(item.get("user_id", 0)) == message.author.id
            ]

            if not mine:
                await message.reply(
                    "ugh. you have no active reminders.\n\nmust be nice having no responsibilities.",
                    mention_author=False
                )
                return

            lines = []

            for item in mine[:10]:
                lines.append(f"• **{item.get('text', 'something')}**")

            await message.reply(
                "ugh. your unfinished business:\n\n"
                + "\n".join(lines),
                mention_author=False
            )
            return
                
        if question.lower() in ["clear my reminders", "delete my reminders", "forget my reminders"]:

            data = await load_reminders()
            items = data.get("items", [])

            remaining = [
                item for item in items
                if int(item.get("user_id", 0)) != message.author.id
            ]

            removed = len(items) - len(remaining)

            data["items"] = remaining
            await save_reminders(data)

            await message.reply(
                f"fine. deleted {removed} reminder(s).\n\nfresh start. suspicious.",
                mention_author=False
            )
            return    
            
        if question.lower().startswith("remember "):
            memory = question[9:].strip()

            if memory:
                await add_user_memory(message.author.id, memory)
                await message.reply(
                    f"Fine. I remembered it: {memory} 🙄",
                    mention_author=False
                )
                return

        if question.lower() in ["what do you remember about me", "what do you remember about me?"]:
            memories = await get_user_memories(message.author.id)

            if not memories:
                await message.reply(
                    "I remember nothing. A clean slate. Suspicious. 🙄",
                    mention_author=False
                )
                return

            text = "\n".join([f"- {m}" for m in memories])
            await message.reply(
                f"Ugh, here's what I remember about you:\n{text}",
                mention_author=False
            )
            return

        if question.lower().startswith("forget "):
            thing = question[7:].strip()
            removed = await forget_user_memory(message.author.id, thing)

            if removed:
                await message.reply(
                    f"Fine. I forgot anything matching: {thing}",
                    mention_author=False
                )
            else:
                await message.reply(
                    "I don't remember that anyway. Very dramatic of you.",
                    mention_author=False
                )
            return

        coffee_triggers = [
            "coffee pls",
            "coffee gossip",
            "what are the coffee girlies drinking",
            "trending coffee drinks",
            "matcha pls",
            "drinkies"
        ]

        q = question.lower()
        if any(trigger in q for trigger in coffee_triggers):

            if await gemini_on_cooldown(message):
                return

            wait = await message.reply(
                "ugh fine. stalking the coffee girlies rn... ☕🙄",
                mention_author=False
            )

            answer = await ask_gemini(
                """
Search Reddit discussions, recent web articles, and coffee trends.

Focus on:
- r/starbucks
- r/coffee
- r/espresso
- r/matcha
- popular cafe drink trends
- seasonal drinks
- viral TikTok-style coffee drinks if they appear in search

Give a short Fergie-style report:
- 4 to 7 trending drinks
- why people like them
- any drama or complaints people have
- one bratty final recommendation

Keep it funny, bratty, and useful.
"""
            )

            if len(answer) > 1800:
                answer = answer[:1800]

            await wait.edit(content=answer)
            return

        if question:

            if await gemini_on_cooldown(message):
                return

            wait = await message.reply(
                "pensando...",
                mention_author=False
            )

            memories = await get_user_memories(message.author.id)
            memory_text = "\n".join([f"- {m}" for m in memories]) if memories else "None"

            cast_context = build_cast_context()

            answer = await ask_gemini(
    f"""
Server regulars:
{cast_context}

User memories:
{memory_text}

Recent chat:
{chat_context}

Previous Fergie message being replied to:
{reply_context}

User asked:
{question}

If the user is replying to your previous message, use that previous message as context.
"""
)

            if len(answer) > 1800:
                answer = answer[:1800]

            sent_as_voice = await maybe_send_fergie_voice_reply(
                message,
                answer,
            )

            if sent_as_voice:
                try:
                    await wait.delete()
                except Exception:
                    pass
            else:
                await wait.edit(
                    content=answer
                )

            return

        await message.reply(
            random.choice(BRATTY_LINES),
            mention_author=False
        )

        return
        
            # Passive cast-aware replies
    if (
        message.author.id in FERGIE_CAST
        and not message.mentions
        and not content.strip().startswith("!")
        and "http://" not in lower
        and "https://" not in lower
    ):
        now = time.time()
        last_reply = passive_cast_cooldowns.get(message.channel.id, 0)

        if (
            now - last_reply >= PASSIVE_CAST_COOLDOWN_SECONDS
            and random.random() < PASSIVE_CAST_REPLY_CHANCE
        ):
            passive_reply = await ask_gemini_passive_cast_reply(message)

            if passive_reply:
                passive_cast_cooldowns[message.channel.id] = now

                sent_as_voice = await maybe_send_fergie_voice_reply(
                    message,
                    passive_reply,
                )

                if not sent_as_voice:
                    await message.reply(
                        passive_reply,
                        mention_author=False
                    )

                return
                
    # Random chat sass (global)
    if random.random() < REPLY_CHANCE:
        choice = random.choice([random.choice(BRATTY_LINES),
                                random.choice(FERAL_LINES),
                                random.choice(REACTION_EMOTES)])
        await message.reply(choice, mention_author=False)
@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return

    if not bot.user:
        return

    if reaction.message.author.id != bot.user.id:
        return

    async for msg in reaction.message.channel.history(limit=50):
        if msg.author.id == user.id:

            custom_emoji = bot.get_emoji(1227392416617730078)

            choices = ["🍑"]

            if custom_emoji:
                choices.append(custom_emoji)

            emoji = random.choice(choices)

            await msg.add_reaction(emoji)

            return
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

@four_hour_post.before_loop
async def _wait_four_hour_post():
    await bot.wait_until_ready()
    await asyncio.sleep(4 * 3600)

@tasks.loop(hours=6)
async def six_hour_emoji():
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await channel.send(BREAD_EMOJI)

@six_hour_emoji.before_loop
async def _wait_six_hour_emoji():
    await bot.wait_until_ready()
    await asyncio.sleep(6 * 3600)

@tasks.loop(time=(dtime(hour=10, tzinfo=timezone.utc), dtime(hour=22, tzinfo=timezone.utc)))
async def user1_twice_daily_fixed():
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await channel.send(f"<@{USER1_ID}> callate!")

@tasks.loop(time=(dtime(hour=11, tzinfo=timezone.utc), dtime(hour=23, tzinfo=timezone.utc)))
async def user2_twice_daily_fixed():
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await channel.send(f"<@{USER2_ID}> when jacuzzi?")

@tasks.loop(hours=8)
async def user3_task():
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        phrase = random.choice(USER3_LINES)
        await channel.send(f"<@{USER1_ID}> {phrase}")

@user3_task.before_loop
async def _wait_user3_task():
    await bot.wait_until_ready()
    await asyncio.sleep(8 * 3600)

@tasks.loop(hours=24)
async def daily_scam_post():
    channel = bot.get_channel(CHANNEL_ID)
    if channel and random.random() < 0.7:
        await channel.send("I NEED MONIES!!!🙄💅")

@daily_scam_post.before_loop
async def _wait_daily_scam_post():
    await bot.wait_until_ready()
    await asyncio.sleep(24 * 3600)


# ---- Gym Reminder ----
import random
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo
from discord.ext import tasks

GYM_CHANNEL_ID = 1272237309521170434  # replace with your channel ID

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


# ================== Fergie Art Status ==================
@bot.command(name="art", help="Show Fergie's Art status and remaining daily generations")
async def art(ctx):
    left = await _fergie_art_slots_left()
    used = max(0, FERGIE_IMAGE_DAILY_LIMIT - left)
    cooldown_remaining = _fergie_art_cooldown_remaining()

    if cooldown_remaining > 0:
        status = (
            f"🟠 **Gemini Art cooling down** — "
            f"{_fergie_format_cooldown(cooldown_remaining)} left"
        )
    else:
        status = "🟢 **Art ready**"

    if left <= 0:
        allowance = (
            f"🎨 **0/{FERGIE_IMAGE_DAILY_LIMIT} pics left today.** "
            "girl we're CLOSED. 😭"
        )
    elif left == 1:
        allowance = (
            f"🎨 **1/{FERGIE_IMAGE_DAILY_LIMIT} pic left today.** "
            "one shot left, fak. don't embarrass me. 🙄"
        )
    else:
        allowance = (
            f"🎨 **{left}/{FERGIE_IMAGE_DAILY_LIMIT} pics left today.** "
            f"i've made **{used}** today. don't waste the rest, fak. 🙄"
        )

    await ctx.send(f"{allowance}\n{status}")


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
    await asyncio.sleep(86400)

# ================== Custom Help: !halp ==================
from discord import Embed, Colour

def _mention_channel(ch_id: int) -> str:
    return f"<#{ch_id}>" if ch_id else "`(not set)`"


@bot.command(name="halp", help="Show Fergie's help menu")
async def halp(ctx, *, command: str | None = None):
    if command:
        cmd = bot.get_command(command.lstrip("!").strip())
        if not cmd:
            await ctx.send(f"girl i don't have a `{command}` command. 🙄")
            return

        aliases = ", ".join(f"`!{a}`" for a in getattr(cmd, "aliases", [])) or "None"
        usage = f"!{cmd.qualified_name} {cmd.signature}".strip()
        e = Embed(
            title=f"🙄 !{cmd.qualified_name}",
            description=(cmd.help or "No details provided."),
            colour=Colour.blurple()
        )
        e.add_field(name="Usage", value=f"`{usage}`", inline=False)
        e.add_field(name="Aliases", value=aliases, inline=False)
        e.set_footer(text="fergie tech support. unfortunately.")
        await ctx.send(embed=e)
        return

    e = Embed(
        title="🙄 Fergie Halp Desk",
        description=(
            "fine. here's the stuff you people keep making me do.\n"
            "Use `!halp <command>` if you need details on a specific `!` command."
        ),
        colour=Colour.blurple()
    )

    e.add_field(
        name="🧠 Talk to Fergie",
        value=(
            "`@fergie <anything>` — Talk to me normally; I understand English, Spanish & Spanglish\n"
            "`@fergie give me the tldr` — Recap today's accessible server yapping\n"
            "`@fergie` + image — I'll look at the image and react\n"
            "I may also randomly butt into chat, react to images, or answer with a voice post."
        ),
        inline=False
    )

    e.add_field(
        name="🎨 Eyes, Art & Comics",
        value=(
            "`@fergie make a pic/image of ...` — Generate an image\n"
            "`@fergie make a comic of ...` — Generate a comic; known cast references can be used\n"
            "`!art` — Check Art status + remaining generations\n"
            f"• Art allowance: **{FERGIE_IMAGE_DAILY_LIMIT} successful generations/day**\n"
            "• Failed generations don't use the allowance"
        ),
        inline=False
    )

    e.add_field(
        name="🎉 Fun & Media",
        value=(
            "`!cafe [term]` — owl y lark\n"
            "`!scam` — BTC/ETH prices, unfortunately\n"
            "`!bbl` — see fergie's culo\n"
            "`!hawaii` — see vivvy's vacation pix\n"
            f"`!fit` — fergie's fits (only in {_mention_channel(FIT_CHANNEL_ID)})\n"
            f"`!kewchie` — random Kali Uchis track (only in {_mention_channel(KEWCHIE_CHANNEL_ID)})"
        ),
        inline=False
    )

    e.add_field(
        name="🔐 Jonathan-only",
        value=(
            "`!resetart` — Reset today's Art count back to 0 and restore the full daily allowance"
        ),
        inline=False
    )

    e.add_field(
        name="🛠️ Server Admin",
        value=(
            "`!seed bank <amt>` / `!seed @user <amt>` — Add bread\n"
            "`!take @user <amt>` — Move bread back to bank\n"
            "`!setbal @user <amt>` — Set exact balance\n"
            "`!dbstatus` / `!dbreload` / `!dbdump` — Database tools\n"
            "`!version` — Bot/runtime status\n"
            "`!kewchie-debug` — Spotify playlist debug"
        ),
        inline=False
    )

    e.set_footer(text="there. you're welcome. 🙄 • try !halp art, !halp roll, etc.")
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
