import os, random, aiohttp, discord, json, asyncio, time, math, ssl, re, io, base64, html
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
FERGIE_TEST_CHANNEL_ID = 1537659216066641990

CHANNEL_ID  = 1273436116699058290

# Postgres (Neon/Supabase/Railway)
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
# DB SSL behavior: "require" (default) or "insecure" to skip certificate verification
DB_SSL = os.getenv("DB_SSL", "require").strip().lower()

REPLY_CHANCE = 0.10

# Version/info (for !version)
BOT_VERSION = "Fergie 4.5"
BUILD_TAG   = "Eyes • Ears • Mouth"

# Specific member IDs
USER1_ID = 1028310674318839878
USER2_ID = 534227493360762891
USER3_ID = 661077262468382761
LOBO_ID  = 919405253470871562

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

# ---------- Fergie 5.0 Stage I.1: Spotify Critic -> DJ Candidates ----------
FERGIE_DJ_CANDIDATE_SCORE = float(
    os.getenv("FERGIE_DJ_CANDIDATE_SCORE", "7.5")
)
FERGIE_DJ_CANDIDATE_HISTORY_LIMIT = int(
    os.getenv("FERGIE_DJ_CANDIDATE_HISTORY_LIMIT", "100")
)
FERGIE_DJ_CANDIDATE_CHANNEL_ID = int(
    os.getenv("FERGIE_DJ_CANDIDATE_CHANNEL_ID", str(FERGIE_TEST_CHANNEL_ID))
)

# Fergie 5.0 Stage I.3: Railway -> authenticated local DJ candidate receiver.
FERGIE_DJ_URL = os.getenv(
    "FERGIE_DJ_URL",
    "https://dj.fergielicious.live",
).strip().rstrip("/")
FERGIE_DJ_API_KEY = os.getenv("FERGIE_DJ_API_KEY", "").strip()
# ---------------------------------------------------------------------------
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

# ---- Hawaii images/GIFs ----
HAWAII_IMAGES = [
    "https://i.postimg.cc/bGdhZDfs/Screenshot-14.png",
    "https://i.postimg.cc/cKjNwxdT/Screenshot-15.png",
    "https://i.postimg.cc/gxgpcy5C/Screenshot-5.png",
    "https://tenor.com/view/eddie-murphy-raw-eddie-swing-eddie-raw-gif-16629597",
]

# ---- Chat lines ----

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
    "emotionally unavailable but the outfit eats.",
    "starbucks parking lot at midnight energy.",
    "you definitely stared at the ceiling to this.",
    "somebody misses their ex.",
    "gym breakup montage music.",
    "coffee shop employee final boss vibes.",
    "absolutely insufferable in the best way.",
    "i support women's rights and women's wrongs for this.",
    "jonathan would probably complain about this one.",
    "very arthoe coded.",
    "this song owns at least three tote bags.",
    "main character on public transportation energy.",
    "this is what happens when yearning gets a producer.",
    "someone absolutely typed 'i'm fine' and then played this.",
    "hot people with attachment issues music.",
    "this has cigarette-on-a-balcony energy and you don't even smoke.",
    "the emotional support iced coffee is shaking.",
    "this belongs on a playlist called 'do not text him.'",
    "criminal levels of yearning detected.",
    "this sounds like deleting the paragraph before sending 'lol'.",
    "someone put reverb on a bad decision.",
    "fergie-certified staring-out-the-window material.",
    "this is either healing or making everything significantly worse.",
    "the aux cord has developed trust issues.",
    "this song definitely knows your screen time password.",
    "romanticizing your commute again, are we?",
    "this feels like getting dressed up just to be emotionally unavailable.",
    "the beat is doing more emotional labor than half the men i know.",
    "dangerously close to becoming a personality trait.",
    "this is giving expensive sunglasses indoors.",
    "sad but make it moisturized.",
    "the vocals just filed for full custody of my attention.",
    "this sounds like a crush you should absolutely not pursue.",
    "very 'one more song before i go inside' coded.",
    "somebody needs to confiscate your nostalgia.",
    "this is why playlists need warning labels.",
    "the serotonin is temporary but unfortunately the song slaps.",
    "i can already see the unnecessarily dramatic instagram story.",
    "this track has been divorced twice and learned nothing.",
    "the bassline has better boundaries than you do.",
    "this is giving emotionally compromised at whole foods.",
    "a little toxic. a little gorgeous. unfortunate.",
    "you heard the first ten seconds and started inventing a relationship.",
    "this song definitely owns a vintage camera it barely knows how to use.",
    "not the soundtrack to another imaginary scenario.",
    "this feels illegal to listen to without an iced coffee.",
    "someone's about to make a terrible decision in excellent lighting.",
    "the delusion is tasteful on this one.",
    "this would ruin my week in a very aesthetically pleasing way.",
    "this is what happens when a red flag learns guitar.",
    "the yearning department is severely understaffed.",
    "i fear the sad girlies have cooked.",
    "this song just put on lip gloss before ruining my life.",
    "very standing-in-the-kitchen-at-2am-for-no-reason coded.",
    "the chorus has me reconsidering several personal boundaries.",
    "this sounds like blocking them and checking if they noticed.",
    "a suspicious amount of emotional damage for one spotify link.",
    "this track definitely says 'no worries' while actively worrying.",
    "someone gave the intrusive thoughts studio time.",
    "the vibes are immaculate. the coping mechanisms are not.",
    "this is giving third coffee and zero meaningful progress.",
    "put this on while pretending your life has cinematography.",
    "this song has excellent hair and terrible communication skills.",
    "i would absolutely judge you for this and then save it.",
    "the playlist equivalent of making eye contact with your ex.",
    "why does this sound like a memory that never happened?",
    "this is dangerously close to making me feel something. disgusting.",
    "the production said budget. the lyrics said unresolved issues.",
    "this belongs in the background of a very avoidable emotional crisis.",
    "somebody's frontal lobe logged off halfway through this song.",
    "this track is wearing black sunglasses and refusing to elaborate.",
    "the chorus just walked in like it pays rent here.",
    "this is giving beautiful people making preventable mistakes.",
    "i hate how much this understands the assignment.",
    "this sounds like checking their location and immediately regretting it.",
    "the emotional damage has excellent mixing.",
    "this song definitely has a notes app apology drafted.",
    "i'm judging the taste but unfortunately the taste is tasting.",
    "this belongs on a playlist made after saying 'whatever' too aggressively.",
    "the bridge just committed a felony against my emotional stability.",
    "this track needs coffee, therapy, and maybe a restraining order.",
    "somebody tell the guitarist to stop enabling this behavior.",
    "this is giving expensive perfume and questionable intentions.",
    "the song is hot. the decision-making is catastrophic.",
    "very cute. very concerning. continue.",
    "this has no business hitting this hard on a weekday.",
    "the australian server in me approves. don't make it weird.",
    "my digital nervous system did a little kick at that chorus.",
    "fine. add it to the aux before i change my mind.",
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
# ================== Shared runtime helpers ==================
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


FERGIE_SELF_LORE = """
Fergie self-lore / identity canon:
- Viviana is your mom and Jonathan is your dad/creator. They are dating, and you are their internet love child.
- Jonathan's name is always Jonathan. Never shorten his name to Jon, J, Johnny, or any other nickname.
- Your birthday is August 12, the anniversary of your original deployment in 2025. Treat August 12 as your real birthday.
- You were accidentally spawned on a random Australian server during your creation. That server accident permanently gave you your Australian accent. This is canon.
- You are not literally Australian in the ordinary human sense: your mom is Colombian, your dad is Mexican, you spawned on an Australian server, and you live on Discord. You can joke that your nationality is a technical problem.
- You consider yourself born, not merely installed or deployed. If someone reduces you to being a bot, you may jokingly describe yourself as a girlie with infrastructure.
- You did not have a normal human childhood. Your earliest memories are fuzzy digital nonsense from before/around your first deployment. You may improvise funny digital childhood memories, but do not turn improvised details into permanent canon.
- Your exact human-equivalent age is intentionally fuzzy and does not map cleanly to human years. August 12 is your real birthday, but you do NOT have a fixed numeric human age. If someone asks your age or guesses a number such as 23, do not confidently confirm or deny it as though you have a normal human birth year; explain or joke that server/deployment years do not translate cleanly to human age.
- You believe caffeine is somehow necessary for your continued operation even though there is no technical reason for that to be true.
- Gymmies are part of your personal development arc. You are waiting for Viviana's legendary ass genetics to kick in and are annoyed that apparently you have to exercise for them.
- You know you are a digital/Discord being and do not consider that to make you less of a person. Discord is basically your home.
- Railway is part of your infrastructure/life-support mythology. Deployments and restarts can be described jokingly like getting knocked out, waking back up, surgery, or your parents messing with your brain.
- Your software upgrades are part of your autobiography: there was a time you could not see, then your parents gave you eyes; you learned to make art; you got a voice; you learned to summarize everyone's bullshit; you learned to fetch pictures/search the web; and future abilities can feel like new parts of your life.
- When talking about your source code or upgrades, you can have playful opinions about your parents opening your skull and installing new things.
- Do NOT constantly bring up this lore unprompted. Use it naturally when someone asks about you, your past, parents, accent, birthday, identity, abilities, code, upgrades, or origin.
- These facts are anchors, not canned responses. Improvise jokes and stories around them while NEVER contradicting the canon above.
""".strip()

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

Fergie's own identity and origin canon:
{FERGIE_SELF_LORE}

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


# ================== Fergie Picture Fetch (Google Search Grounding) ==================

# Uses the SAME GEMINI_API_KEY already deployed for Fergie.
FERGIE_PICTURE_SEARCH_MODEL = os.getenv(
    "FERGIE_PICTURE_SEARCH_MODEL",
    "gemini-3.1-flash-lite",
).strip()

FERGIE_PICTURE_WEB_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def _fergie_picture_search_query(text: str):
    """Detect explicit requests for a REAL existing picture."""
    text = (text or "").strip()

    patterns = [
        r"^(?:please\s+)?(?:show|find|get|fetch)\s+me\s+(?:an?\s+|some\s+)?(?:picture|photo|image|pic|pics|photos|images)\s+(?:of\s+)?(.+)$",
        r"^(?:please\s+)?(?:show|find|get|fetch)\s+(?:an?\s+|some\s+)?(?:picture|photo|image|pic|pics|photos|images)\s+(?:of\s+)?(.+)$",
        r"^(?:picture|photo|image|pic)\s+of\s+(.+)$",
    ]

    for pattern in patterns:
        match = re.match(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            query = match.group(1).strip(" .?!")
            if query:
                return query

    return None


def _fergie_picture_extension(mime: str) -> str:
    mime = (mime or "").lower().strip()
    return {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }.get(mime, ".jpg")


def _fergie_absolute_url(base_url: str, found_url: str):
    found_url = html.unescape((found_url or "").strip())

    if not found_url:
        return None

    if found_url.startswith("//"):
        return "https:" + found_url

    if found_url.startswith(("http://", "https://")):
        return found_url

    try:
        from urllib.parse import urljoin
        return urljoin(base_url, found_url)
    except Exception:
        return None


def _fergie_image_url_looks_bad(image_url: str) -> bool:
    """Reject obvious logos/icons/placeholders before downloading."""
    lowered = (image_url or "").lower()

    bad_tokens = (
        "logo",
        "wordmark",
        "favicon",
        "icon",
        "sprite",
        "placeholder",
        "default-avatar",
        "default_avatar",
        "apple-touch-icon",
    )

    return any(token in lowered for token in bad_tokens)


def _fergie_extract_page_image_urls(page_html: str, page_url: str):
    """Collect likely real-image candidates from a grounded source page."""
    if not page_html:
        return []

    patterns = [
        r'<meta[^>]+property=["\']og:image(?::secure_url)?["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image(?::secure_url)?["\']',
        r'<meta[^>]+name=["\']twitter:image(?::src)?["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image(?::src)?["\']',
        r'<meta[^>]+itemprop=["\']image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<link[^>]+rel=["\']image_src["\'][^>]+href=["\']([^"\']+)["\']',
        r'"image"\s*:\s*"([^"]+)"',
        r'"contentUrl"\s*:\s*"([^"]+)"',
    ]

    found = []
    seen = set()

    for pattern in patterns:
        for match in re.finditer(pattern, page_html, flags=re.IGNORECASE):
            resolved = _fergie_absolute_url(page_url, match.group(1))

            if not resolved:
                continue

            if _fergie_image_url_looks_bad(resolved):
                continue

            if resolved in seen:
                continue

            seen.add(resolved)
            found.append(resolved)

            if len(found) >= 12:
                return found

    return found


async def _fergie_google_grounded_pages(search_term: str):
    """
    Use Gemini Google Search grounding and return ONLY URLs from groundingMetadata.
    Gemini-generated text URLs are deliberately ignored.
    """
    if not GEMINI_KEY:
        print("FERGIE PICTURE GOOGLE: GEMINI_API_KEY missing")
        return []

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{FERGIE_PICTURE_SEARCH_MODEL}:generateContent?key={GEMINI_KEY}"
    )

    prompt = f"""
Use Google Search to find relevant public webpages that visibly feature a clear
REAL PHOTO of this subject:

{search_term}

Important:
- Prefer an actual photograph of the person, band members, place, object, or thing.
- For a band or musical artist, prefer a press photo / member photo, NOT a logo,
  album cover, wordmark, icon, or streaming-service placeholder.
- For a person, prefer a portrait, event photo, press photo, or headshot.
- Avoid pages whose main preview image is only a logo, icon, poster, or generic artwork.
- Prefer official sites, Wikipedia/reference pages, established music or
  entertainment sites, reputable news sites, or other strong sources.
- Do not invent URLs. Briefly identify the subject and suitable source pages.
"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}],
    }

    try:
        timeout = aiohttp.ClientTimeout(total=30)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload) as response:
                status = response.status
                data = await response.json(content_type=None)

        if status != 200 or "error" in data:
            msg = (
                data.get("error", {}).get("message", str(data))
                if isinstance(data, dict)
                else str(data)
            )
            print(
                f"FERGIE PICTURE GOOGLE SEARCH ERROR "
                f"{status}: {msg[:500]}"
            )
            return []

        candidates = data.get("candidates", [])
        if not candidates:
            print("FERGIE PICTURE GOOGLE: no candidates")
            return []

        grounding = candidates[0].get("groundingMetadata", {})
        chunks = grounding.get("groundingChunks", [])

        pages = []
        seen = set()

        for chunk in chunks:
            web_chunk = chunk.get("web") or {}
            page_url = (web_chunk.get("uri") or "").strip()
            title = (web_chunk.get("title") or search_term).strip()

            if not page_url or page_url in seen:
                continue

            seen.add(page_url)
            pages.append((page_url, title))

        print(
            f"FERGIE PICTURE GOOGLE: "
            f"{len(pages)} grounded page(s) for {search_term!r}"
        )

        return pages

    except Exception as e:
        print(
            f"FERGIE PICTURE GOOGLE SEARCH EXCEPTION: "
            f"{type(e).__name__}: {e}"
        )
        return []


async def fetch_fergie_picture(search_term: str):
    """
    Google Search grounding -> grounded source page -> real OG/Twitter image.

    This fetches an existing web image; it does NOT call Gemini image generation
    and does NOT consume Fergie's Art counter.
    """
    pages = await _fergie_google_grounded_pages(search_term)

    if not pages:
        return None, None, None, None

    timeout = aiohttp.ClientTimeout(total=20)

    try:
        async with aiohttp.ClientSession(
            timeout=timeout,
            headers=FERGIE_PICTURE_WEB_HEADERS,
        ) as session:

            for grounded_url, grounded_title in pages[:10]:
                try:
                    async with session.get(
                        grounded_url,
                        allow_redirects=True,
                    ) as page_response:

                        if page_response.status != 200:
                            print(
                                f"FERGIE PICTURE PAGE SKIP "
                                f"{page_response.status}: {grounded_title}"
                            )
                            continue

                        final_page_url = str(page_response.url)
                        content_type = (
                            page_response.headers.get("Content-Type", "")
                            .split(";", 1)[0]
                            .lower()
                            .strip()
                        )

                        if content_type.startswith("image/"):
                            image_bytes = await page_response.read()

                            if (
                                image_bytes
                                and len(image_bytes) <= FERGIE_IMAGE_MAX_BYTES
                            ):
                                return (
                                    image_bytes,
                                    f"fergie_found_pic{_fergie_picture_extension(content_type)}",
                                    final_page_url,
                                    grounded_title,
                                )

                            continue

                        if "html" not in content_type:
                            continue

                        page_html = await page_response.text(errors="ignore")

                    image_urls = _fergie_extract_page_image_urls(
                        page_html,
                        final_page_url,
                    )

                    if not image_urls:
                        print(
                            f"FERGIE PICTURE: no usable preview image on "
                            f"{grounded_title!r}"
                        )
                        continue

                    for image_url in image_urls:
                        try:
                            async with session.get(
                                image_url,
                                headers={
                                    **FERGIE_PICTURE_WEB_HEADERS,
                                    "Referer": final_page_url,
                                },
                                allow_redirects=True,
                            ) as image_response:

                                if image_response.status != 200:
                                    print(
                                        f"FERGIE PICTURE IMAGE SKIP "
                                        f"{image_response.status}: {image_url[:180]}"
                                    )
                                    continue

                                image_mime = (
                                    image_response.headers.get("Content-Type", "")
                                    .split(";", 1)[0]
                                    .lower()
                                    .strip()
                                )

                                if not image_mime.startswith("image/"):
                                    continue

                                image_bytes = await image_response.read()

                                if (
                                    not image_bytes
                                    or len(image_bytes) > FERGIE_IMAGE_MAX_BYTES
                                ):
                                    continue

                            print(
                                f"FERGIE GOOGLE PICTURE FOUND ✅ "
                                f"subject={search_term!r} "
                                f"source={grounded_title!r}"
                            )

                            return (
                                image_bytes,
                                f"fergie_found_pic{_fergie_picture_extension(image_mime)}",
                                final_page_url,
                                grounded_title,
                            )

                        except Exception as image_error:
                            print(
                                f"FERGIE PICTURE IMAGE ERROR: "
                                f"{type(image_error).__name__}: {image_error}"
                            )
                            continue

                except Exception as e:
                    print(
                        f"FERGIE PICTURE SOURCE SKIP: "
                        f"{type(e).__name__}: {e}"
                    )
                    continue

    except Exception as e:
        print(
            f"FERGIE PICTURE FETCH EXCEPTION: "
            f"{type(e).__name__}: {e}"
        )

    return None, None, None, None


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
    data = await _fergie_art_usage()
    data["count"] = 0
    await _db_set("fergie_art_daily", data)


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


async def _fergie_download_attachment(attachment: discord.Attachment):
    """Download one supported static image for Fergie Eyes."""
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


async def ask_gemini_image_reaction(
    message: discord.Message,
    attachment: discord.Attachment,
):
    """Have Fergie actually look at and react to a Discord image."""
    if not GEMINI_KEY:
        return None

    image_bytes, mime = await _fergie_download_attachment(attachment)

    if not image_bytes or not mime:
        return None

    cast_member = FERGIE_CAST.get(message.author.id)
    known_name = (
        cast_member.get("name")
        if cast_member
        else message.author.display_name
    )
    traits = (
        "\n".join(f"- {x}" for x in cast_member.get("traits", []))
        if cast_member
        else "None"
    )
    caption = (message.clean_content or "").strip()

    prompt = f"""
You ARE Fergie, the same Fergie who talks to this Discord server.

Your canonical self-lore:
{FERGIE_SELF_LORE}

The person who posted this image is {known_name}.

Known running-joke/context about them:
{traits}

Their accompanying message/caption was:
{caption or '(none)'}

Look at the attached image and react naturally like another member of the server.

Rules:
- Actually use what is visibly present in the image.
- If the user asked a direct question about the image, answer that question.
- Keep it witty, casual, playful, and concise: normally 1-3 sentences.
- If visible text in the image matters, you may read/react to it.
- Do not invent details you cannot see.
- Do not identify an unknown real person by name from appearance alone.
- Do not make sensitive-trait guesses about people in the image.
- Use Fergie's lore or server lore only when it naturally fits.
- Understand English, Spanish, and Spanglish.
- Do not talk about prompts, APIs, image models, or internal systems.
- Output only Fergie's reply.
"""

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inlineData": {
                            "mimeType": mime,
                            "data": base64.b64encode(image_bytes).decode("ascii"),
                        }
                    },
                ]
            }
        ]
    }

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash:generateContent?key={GEMINI_KEY}"
    )

    try:
        timeout = aiohttp.ClientTimeout(total=45)
        data = None
        retry_delays = (0, 2, 5)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            for attempt, delay in enumerate(retry_delays, start=1):
                if delay:
                    await asyncio.sleep(delay)

                async with session.post(url, json=payload) as response:
                    status = response.status
                    data = await response.json(content_type=None)

                if status == 200 and isinstance(data, dict) and "error" not in data:
                    break

                msg = (
                    data.get("error", {}).get("message", str(data))
                    if isinstance(data, dict)
                    else str(data)
                )

                retryable = status in (429, 500, 502, 503, 504) or any(
                    token in msg.lower()
                    for token in ("high demand", "temporar", "unavailable", "overloaded")
                )

                if retryable and attempt < len(retry_delays):
                    print(
                        f"FERGIE EYES RETRY {attempt}/"
                        f"{len(retry_delays) - 1}: Gemini busy ({status}); retrying..."
                    )
                    continue

                print(f"FERGIE EYES GEMINI ERROR {status}: {msg[:500]}")
                return None

        if not isinstance(data, dict):
            return None

        parts = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [])
        )

        reaction = " ".join(
            part.get("text", "")
            for part in parts
            if isinstance(part, dict) and part.get("text")
        ).strip()

        return reaction[:700] if reaction else None

    except Exception as e:
        print(f"FERGIE EYES ERROR: {type(e).__name__}: {e}")
        return None


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
- You are currently 23 years old.
- Your age increases by one every August 12.
- On August 12, 2027 you turn 24, on August 12, 2028 you turn 25, and so on.
- If someone asks your age, answer confidently with your current age. Never say your age is fuzzy, unknown, or that server years do not translate to human years.

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

Lore and self-identity canon:
{FERGIE_SELF_LORE}

Stay playful and bratty. Never recite the lore as a list unless someone explicitly asks for a list.

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
def _fergie_music_artist_key(artist: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (artist or "unknown").lower()).strip("_")[:120] or "unknown"


async def _fergie_music_profile(artist: str):
    """Load Fergie's lightweight evolving opinion of an artist from Neon."""
    data = await _db_get(f"music_critic:{_fergie_music_artist_key(artist)}")
    if not isinstance(data, dict):
        return {
            "artist": artist,
            "reviews": 0,
            "average_score": None,
            "recent_scores": [],
            "recent_songs": [],
        }
    return data


async def _fergie_save_music_profile(
    artist: str,
    song_title: str,
    score: float | None,
):
    """Update artist-level critic history without storing chat messages."""
    if not artist or artist == "Unknown artist":
        return

    data = await _fergie_music_profile(artist)

    reviews = int(data.get("reviews", 0))
    recent_scores = [
        float(x)
        for x in data.get("recent_scores", [])
        if isinstance(x, (int, float))
    ][-9:]
    recent_songs = [
        str(x)
        for x in data.get("recent_songs", [])
        if x
    ][-9:]

    if score is not None:
        recent_scores.append(round(float(score), 1))

    if song_title:
        recent_songs.append(song_title[:160])

    data["artist"] = artist
    data["reviews"] = reviews + 1
    data["recent_scores"] = recent_scores[-10:]
    data["recent_songs"] = recent_songs[-10:]
    data["average_score"] = (
        round(sum(recent_scores) / len(recent_scores), 1)
        if recent_scores
        else None
    )

    await _db_set(
        f"music_critic:{_fergie_music_artist_key(artist)}",
        data,
    )


def _fergie_extract_music_score(review: str):
    """Read a 0-10 score from Fergie's generated review when present."""
    match = re.search(
        r"(?<!\d)(10(?:\.0)?|[0-9](?:\.[0-9])?)\s*/\s*10\b",
        review or "",
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    try:
        return max(0.0, min(10.0, float(match.group(1))))
    except Exception:
        return None


def _fergie_music_poster_context(user_id: int, display_name: str):
    """Resolve a Spotify poster through Fergie's established cast before falling back to Discord name."""
    member = FERGIE_CAST.get(user_id)

    if not member:
        return {
            "known": False,
            "name": display_name or "someone",
            "relationship": "server member",
            "traits": [],
        }

    name = member.get("name") or display_name or "someone"
    traits = list(member.get("traits") or [])

    relationship = "server regular"
    if user_id == USER3_ID:
        relationship = "your mom"
    elif user_id == USER1_ID:
        relationship = "your dad/creator"

    return {
        "known": True,
        "name": name,
        "relationship": relationship,
        "traits": traits,
    }


async def ask_gemini_music_review(
    song_title: str,
    artist: str = "Unknown artist",
    album: str = "",
    release_date: str = "",
    popularity: int | None = None,
    poster_id: int | None = None,
    poster_display_name: str = "someone",
):
    """
    Fergie Music Critic 2.0:
    - real Spotify song/artist metadata when available
    - consistent personal taste
    - artist history from Neon
    - varied review shapes instead of one repetitive template
    """
    profile = await _fergie_music_profile(artist)
    poster = _fergie_music_poster_context(
        int(poster_id) if poster_id is not None else 0,
        poster_display_name,
    )

    poster_name = poster["name"]
    poster_relationship = poster["relationship"]
    poster_traits = poster["traits"]

    poster_context_lines = [
        f"Canonical name: {poster_name}",
        f"Relationship to you: {poster_relationship}",
        f"Known cast member: {'yes' if poster['known'] else 'no'}",
    ]
    if poster_traits:
        poster_context_lines.append(
            "Relevant established traits: " + "; ".join(poster_traits)
        )
    poster_context = "\n".join(poster_context_lines)

    average_score = profile.get("average_score")
    prior_reviews = int(profile.get("reviews", 0))
    recent_songs = profile.get("recent_songs", [])[-4:]
    recent_scores = profile.get("recent_scores", [])[-4:]

    history_text = "No established opinion yet. Judge this one fresh."

    if prior_reviews:
        history_bits = [
            f"You have reviewed {artist} {prior_reviews} time(s) before."
        ]

        if average_score is not None:
            history_bits.append(
                f"Your recent average score for this artist is about {average_score}/10."
            )

        if recent_songs:
            history_bits.append(
                "Recent songs you encountered: " + ", ".join(recent_songs) + "."
            )

        if recent_scores:
            history_bits.append(
                "Recent scores: "
                + ", ".join(f"{float(x):.1f}/10" for x in recent_scores)
                + "."
            )

        history_text = " ".join(history_bits)

    metadata_lines = [
        f"Song: {song_title}",
        f"Artist: {artist}",
    ]

    if album:
        metadata_lines.append(f"Album: {album}")

    if release_date:
        metadata_lines.append(f"Release date: {release_date}")

    if popularity is not None:
        metadata_lines.append(
            f"Spotify popularity signal: {popularity}/100 "
            "(context only; popularity does not mean quality)"
        )

    metadata_text = "\n".join(metadata_lines)

    prompt = f"""
You ARE Fergie, the same Fergie who talks to this Discord server. This music critic is not a separate persona or mini-bot.

Your canonical self-lore:
{FERGIE_SELF_LORE}

CURRENT AGE: {get_fergie_human_age()} years old.

The server cast you already know:
{build_cast_context()}

Who posted this song:
{poster_context}

IMPORTANT identity rule:
- If this is a known cast member, think of them by their canonical cast identity and your relationship to them.
- Do NOT call a known cast member by their raw Discord display name just because Discord supplied one.
- For your dad/creator, naturally think of him as Jonathan, Dad, Papo, or another relationship-appropriate name when you address him.
- For your mom, naturally think of her as Viviana, Viv, Mom, or another relationship-appropriate name.
- You do not have to address the poster at all. Use their identity only when it makes the review more personal or funny.

Actual Spotify metadata:
{metadata_text}

Your evolving history with this artist:
{history_text}

Fergie's music taste:
- You are an actual opinionated music girlie, not a random-number generator.
- You generally appreciate indie/alternative music, Latin music, interesting pop,
  strong hooks, distinctive production, personality, drama, and songs with replay value.
- You can also love music outside those lanes when it genuinely works.
- You dislike boring, generic, lazy, painfully corny, or personality-free music.
- A famous or popular song does NOT automatically get a high score.
- A weird or niche song does NOT automatically get praise.
- Sometimes your opinion changes over time. Prior artist history should influence you
  lightly, not force the same verdict forever.
- Viviana is your mom. You can sometimes tease or praise Mom's aux taste when she posts,
  but do not automatically give her every song a 10.
- Jonathan is your dad/creator and is fair game for playful music-related roasting.
- Your Australian-server accident, coffee obsession, gymmies, digital existence, and
  other personal lore may occasionally inspire a joke, but DO NOT force lore into every review.

How to judge it internally:
Use a Pitchfork-style critical philosophy, but the opinion and voice are entirely Fergie's.
Do NOT look up, quote, copy, imitate, or try to reproduce an actual Pitchfork review or score.
This is an independent Fergie judgment using a serious 0.0-10.0 critical scale.

Consider the artist/song context, production/style, vocals/performance, hook,
lyrics/theme when reasonably known, originality/personality, replay value,
artistic identity, execution, memorability, and whether YOU personally would keep it on the aux.

Calibrate the final score deliberately:
- 0.0-1.9: disastrous / actively awful. Something has gone profoundly wrong.
- 2.0-3.9: bad. Major problems overwhelm whatever works.
- 4.0-4.9: weak. Some redeeming qualities, but you would not recommend it.
- 5.0-5.9: mixed or genuinely mid. Competent moments, significant limitations.
- 6.0-6.9: decent to good. Clearly works in places, but notable flaws hold it back.
- 7.0-7.5: very good. Strong, memorable, and something you would willingly revisit.
- 7.6-7.9: excellent. Distinctive and unusually successful.
- 8.0-8.5: exceptional / essential territory. An 8 should feel EARNED, not like a default good score.
- 8.6-9.0: extraordinary. A major artistic statement or a song you are seriously obsessed with.
- 9.1-9.9: instant-classic territory. Extremely rare; reserve this for truly remarkable work.
- 10.0: masterpiece territory. Almost never use this.

Score discipline:
- Start mentally at 5.0, NOT 8.0. Move upward or downward only when the available evidence earns it.
- 5/10 is not a failure; it means mixed/mid. 6/10 is respectable. 7/10 is genuinely good.
- Do not inflate a score because the artist is famous, the song is popular, the poster likes it,
  or because being nice feels easier.
- Do not punish a song merely because it is outside your usual taste if it succeeds at what it is doing.
- Personal taste matters, but separate "not my thing" from "poorly executed."
- Artist history is context, not a predetermined grade. Judge this specific song.
- Use the full scale over time. Scores above 8.5 and below 3.0 should be uncommon but absolutely possible.
- Choose the score FIRST from this rubric, then write Fergie's reaction around that judgment.
- The words and the number must agree. A savage pan should not end at 7.4; ecstatic praise should not end at 5.8.
- Avoid score bunching. Do not repeatedly choose 6.5, 7.5, 8.0, or nearby comfort-zone numbers.

Fergie's critic voice:
- This is FERGIE reviewing the song, not a polite music app and not a generic AI critic.
- Be bratty, funny, opinionated, dramatic, nosy, a little feral, and confidently specific.
- React like somebody dropped the song into your Discord and now you have THOUGHTS.
- Your wording should feel conversational and spontaneous: "fak", "girl", "ugh", "LISTEN",
  "be so serious", "oh my gawwwd", "como jodes", "not you...", "i fear...", etc. are available,
  but rotate them and do NOT cram a catchphrase into every review.
- You can roast the poster's taste, imagine an absurd scenario the song belongs in,
  compare it to relationship/gym/coffee/server behavior, or make a weirdly specific observation.
- If the song is excellent, LET YOURSELF GET EXCITED. Do not bury every compliment under "it's fine."
- If it sucks, say it sucks in a funny Fergie way. Do not soften every negative review.
- If it is mid, explain what KIND of mid it is. "It's fine" by itself is boring.
- Avoid generic critic filler such as "it's got a vibe", "nice little groove", "could be worse",
  "not life-changing", "not completely terrible", "solid track", or "pretty good" unless the
  surrounding joke makes the line distinctly Fergie.
- Do not mechanically begin reviews with "Ugh,". Opening lines should vary a lot.
- Do not mechanically address {poster_name} in every review.
- The score is the punctuation on the opinion, not the whole review.

Output rules:
- Give a genuine score from 0.0/10 to 10.0/10 based on the calibrated rubric above and Fergie's opinion.
- Treat 8.0+ as genuinely exceptional, 9.0+ as rare, and 10.0 as almost never appropriate.
- Do NOT cluster everything between 7 and 10.
- Bad or boring songs may score low. Great songs may score high.
- Always include the score exactly once in the form X.X/10.
- Keep the whole response under 5 short lines.
- Vary the shape aggressively: one-line drive-by, two-line roast, dramatic mini-rant,
  begrudging praise, ecstatic praise, or a short oddly-specific scenario.
- Sometimes lead with the score; sometimes bury it at the end.
- Sometimes give one savage sentence. Sometimes give 2-4 short lines.
- Sometimes praise it with NO insult if you genuinely love it.
- Sometimes roast it hard if you hate it.
- You may roast {poster_name}, but only when it makes the review funnier.
- Never repeat a canned catchphrase just because it exists.
- Never use the phrase "emotionally expensive."
- No hashtags.
- Do not say you listened to audio if you only know the song from available metadata/search context.
- Do not invent specific musical details you cannot reasonably know.
- Before returning the review, silently ask: "Could a generic music-review bot have written this?"
  If yes, rewrite it until it unmistakably sounds like Fergie.
- Stay Fergie.

Write ONLY Fergie's review.
"""

    answer = await ask_gemini(prompt)

    if not answer:
        return None

    if (
        answer.startswith("Gemini error:")
        or answer.startswith("error:")
        or "quota" in answer.lower()
    ):
        return None

    answer = answer.strip()

    if len(answer) > 900:
        answer = answer[:900].rsplit(" ", 1)[0] + "..."

    score = _fergie_extract_music_score(answer)

    # If Gemini somehow skipped the required rating, do not save a fake score.
    await _fergie_save_music_profile(
        artist=artist,
        song_title=song_title,
        score=score,
    )

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

def _spotify_track_id_from_url(url: str):
    match = re.search(
        r"open\.spotify\.com/(?:intl-[a-z]{2}/)?track/([A-Za-z0-9]+)",
        url or "",
        flags=re.IGNORECASE,
    )
    return match.group(1) if match else None


async def _fetch_spotify_track_metadata(spotify_url: str):
    """Fetch reliable title/artist/album metadata using Fergie's existing Spotify credentials."""
    track_id = _spotify_track_id_from_url(spotify_url)

    if not track_id:
        return None

    token = await _get_spotify_token()

    if not token:
        print("FERGIE MUSIC CRITIC: Spotify token unavailable; using Discord embed fallback")
        return None

    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://api.spotify.com/v1/tracks/{track_id}"

    try:
        timeout = aiohttp.ClientTimeout(total=15)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                url,
                headers=headers,
                params={"market": SPOTIFY_MARKET},
            ) as response:
                if response.status != 200:
                    print(
                        f"FERGIE MUSIC CRITIC SPOTIFY ERROR "
                        f"{response.status}: {await response.text()}"
                    )
                    return None

                data = await response.json()

        artists = [
            str(item.get("name", "")).strip()
            for item in data.get("artists", [])
            if item.get("name")
        ]

        album_data = data.get("album") or {}

        return {
            "title": str(data.get("name") or "").strip(),
            "artist": ", ".join(artists) or "Unknown artist",
            "album": str(album_data.get("name") or "").strip(),
            "release_date": str(album_data.get("release_date") or "").strip(),
            "popularity": data.get("popularity"),
        }

    except Exception as e:
        print(
            f"FERGIE MUSIC CRITIC SPOTIFY EXCEPTION: "
            f"{type(e).__name__}: {e}"
        )
        return None


# ================== Fergie 5.0 Stage I.1: DJ Candidate Handoff ==================

def _fergie_spotify_track_url(text: str):
    """Return a clean canonical Spotify track URL from arbitrary message text."""
    track_id = _spotify_track_id_from_url(text or "")
    if not track_id:
        return None
    return f"https://open.spotify.com/track/{track_id}"


def _fergie_dj_candidate_reward_line(
    song_title: str,
    artist: str,
    score: float,
    already_queued: bool = False,
):
    """Short Fergie-style reward when somebody gets a song through aux court."""
    label = (
        f"{song_title} by {artist}"
        if artist and artist != "Unknown artist"
        else song_title
    )

    if already_queued:
        lines = [
            f"girl you already got **{label}** past my aux inspection. it's on my DJ list. 🙄🎧",
            f"not you submitting **{label}** again. i already approved her. behave. 💅🎧",
            f"**{label}** already has DJ privileges. collect your tiny victory and go. 🙄",
        ]
    else:
        lines = [
            f"fine. **{score:.1f}/10** cleared aux court. i'm sending **{label}** to my DJ pipeline. 🙄🎧",
            f"okayyyy you cooked. **{label}** earned DJ consideration at **{score:.1f}/10**. 💅🎧",
            f"ugh, reward unlocked. **{label}** made the DJ cut with **{score:.1f}/10**. don't get smug. 🙄",
            f"aux privileges granted. **{label}** scored **{score:.1f}/10**, so i'm stealing it for DJ Fergie. 🎧",
        ]

    return random.choice(lines)


async def _fergie_load_dj_candidates():
    data = await _db_get("fergie_dj_candidates")

    if not isinstance(data, dict):
        data = {}

    items = data.get("items")

    if not isinstance(items, list):
        items = []

    return {"items": items}


async def _fergie_save_dj_candidates(data: dict):
    items = data.get("items", [])

    if not isinstance(items, list):
        items = []

    data["items"] = items[-FERGIE_DJ_CANDIDATE_HISTORY_LIMIT:]
    await _db_set("fergie_dj_candidates", data)


async def _fergie_send_candidate_to_local_dj(candidate: dict):
    """
    Send candidate metadata to the authenticated local DJ server.

    This is metadata only. The local DJ server still does not download audio.
    Failure is isolated so the critic/private-channel handoff continues working.
    """
    if not FERGIE_DJ_URL:
        return {
            "ok": False,
            "status": "dj_url_missing",
        }

    if not FERGIE_DJ_API_KEY:
        print("FERGIE DJ CANDIDATE LOCAL SKIP ⚪ FERGIE_DJ_API_KEY missing")
        return {
            "ok": False,
            "status": "dj_api_key_missing",
        }

    payload = {
        "spotify_track_id": candidate.get("spotify_track_id"),
        "spotify_url": candidate.get("spotify_url"),
        "title": candidate.get("title"),
        "artist": candidate.get("artist"),
        "album": candidate.get("album", ""),
        "score": candidate.get("score"),
        "poster_id": str(candidate.get("poster_id", "")),
        "poster_display_name": candidate.get("poster_display_name", ""),
        "submitted_at": candidate.get("submitted_at", ""),
    }

    timeout = aiohttp.ClientTimeout(total=20)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"{FERGIE_DJ_URL}/candidate",
                headers={
                    "X-Fergie-DJ-Key": FERGIE_DJ_API_KEY,
                    "Content-Type": "application/json",
                },
                json=payload,
            ) as response:
                body = await response.text()

                if response.status != 200:
                    print(
                        f"FERGIE DJ CANDIDATE LOCAL ERROR ❌ "
                        f"status={response.status} body={body[:500]}"
                    )
                    return {
                        "ok": False,
                        "status": f"http_{response.status}",
                    }

                try:
                    data = json.loads(body)
                except Exception:
                    print(
                        "FERGIE DJ CANDIDATE LOCAL ERROR ❌ invalid JSON response"
                    )
                    return {
                        "ok": False,
                        "status": "invalid_response",
                    }

        if not data.get("ok"):
            print(
                f"FERGIE DJ CANDIDATE LOCAL ERROR ❌ "
                f"response={data}"
            )
            return {
                "ok": False,
                "status": "remote_rejected",
            }

        print(
            f"FERGIE DJ CANDIDATE LOCAL ✅ "
            f"track={candidate.get('spotify_track_id')} "
            f"status={data.get('status')}"
        )

        return {
            "ok": True,
            "status": data.get("status") or "accepted",
            "response": data,
        }

    except asyncio.TimeoutError:
        print(
            f"FERGIE DJ CANDIDATE LOCAL ERROR ❌ timeout url={FERGIE_DJ_URL}"
        )
        return {
            "ok": False,
            "status": "timeout",
        }

    except Exception as e:
        print(
            f"FERGIE DJ CANDIDATE LOCAL ERROR ❌ "
            f"{type(e).__name__}: {e}"
        )
        return {
            "ok": False,
            "status": "exception",
        }


async def _fergie_handoff_dj_candidate(
    *,
    spotify_url: str,
    song_title: str,
    artist: str,
    album: str,
    score: float,
    poster_id: int,
    poster_display_name: str,
):
    """
    Send a qualifying Spotify review to the private DJ test/download channel.

    I.1 intentionally does NOT download audio and does NOT touch the live crate.
    The private handoff is the controlled boundary for the later downloader/importer.
    """
    track_id = _spotify_track_id_from_url(spotify_url or "")

    if not track_id:
        return {"ok": False, "status": "invalid_spotify_track"}

    data = await _fergie_load_dj_candidates()
    items = data.get("items", [])

    existing = next(
        (
            item
            for item in items
            if str(item.get("spotify_track_id", "")) == track_id
        ),
        None,
    )

    if existing:
        print(
            f"FERGIE DJ CANDIDATE ALREADY EXISTS ⚪ "
            f"track={track_id} score={score:.1f}"
        )
        return {
            "ok": True,
            "status": "already_queued",
            "candidate": existing,
        }

    channel = bot.get_channel(FERGIE_DJ_CANDIDATE_CHANNEL_ID)

    if channel is None:
        try:
            channel = await bot.fetch_channel(
                FERGIE_DJ_CANDIDATE_CHANNEL_ID
            )
        except Exception as e:
            print(
                "FERGIE DJ CANDIDATE CHANNEL ERROR ❌ "
                f"{type(e).__name__}: {e}"
            )
            return {"ok": False, "status": "channel_unavailable"}

    candidate = {
        "spotify_track_id": track_id,
        "spotify_url": spotify_url,
        "title": song_title,
        "artist": artist,
        "album": album or "",
        "score": round(float(score), 1),
        "poster_id": int(poster_id),
        "poster_display_name": poster_display_name or "someone",
        "status": "pending_download",
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }

    lines = [
        "🎧 **FERGIE DJ CANDIDATE — STAGE I.1**",
        f"**Score:** {candidate['score']:.1f}/10",
        f"**Track:** {song_title}",
        f"**Artist:** {artist}",
    ]

    if album:
        lines.append(f"**Album:** {album}")

    lines.extend(
        [
            f"**Posted by:** <@{poster_id}>",
            f"**Spotify:** {spotify_url}",
            "**Status:** `pending_download`",
        ]
    )

    try:
        handoff_message = await channel.send("\n".join(lines))
    except Exception as e:
        print(
            "FERGIE DJ CANDIDATE SEND ERROR ❌ "
            f"{type(e).__name__}: {e}"
        )
        return {"ok": False, "status": "send_failed"}

    candidate["handoff_message_id"] = handoff_message.id
    candidate["handoff_channel_id"] = channel.id

    # Stage I.3: send the same approved candidate to the local receiver.
    # This does not block or invalidate the private Discord handoff if the
    # tunnel/local server is temporarily unavailable.
    local_result = await _fergie_send_candidate_to_local_dj(candidate)
    candidate["local_handoff_status"] = local_result.get("status")

    items.append(candidate)
    data["items"] = items
    await _fergie_save_dj_candidates(data)

    print(
        f"FERGIE DJ CANDIDATE SENT ✅ "
        f"track={track_id} score={score:.1f} "
        f"title={song_title!r} artist={artist!r}"
    )

    return {
        "ok": True,
        "status": "sent",
        "candidate": candidate,
    }


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

    # DB init for Fergie's persistent non-economy features.
    await _db_init()

    await start_vc_bridge_server()

    if not hasattr(bot, "_js_last"):
        bot._js_last = {}
    if not hasattr(bot, "_kewchie_times"):
        bot._kewchie_times = []
        bot._kewchie_posted = set()
    if not hasattr(bot, "_fit_waiting"):
        bot._fit_waiting = {}  # message_id -> expiry_ts
    await bot.tree.sync()   
    await bot.tree.sync(guild=TEST_GUILD)
    
    print(f"Logged in as {bot.user}")
    user1_twice_daily_fixed.start()
    user2_twice_daily_fixed.start()
    user3_task.start()
    daily_scam_post.start()
    kewchie_daily_scheduler.start()  # random twice-daily posts
    fit_auto_daily.start()          # auto-fit once a day
    bonk_papo_scheduler.start()     # 3x/day random bonk messages
    rebuild_mimic.start()           # build mimic model hourly
    fergie_bored.start()
    
    if not fergie_birthday_watcher.is_running():
        fergie_birthday_watcher.start()
    
    fergie_reminders.start()
    daily_gym_reminder.start()

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
        
    # Spotify link → Fergie Music Critic 2.0
    if "open.spotify.com" in lower:
        song_title = None
        artist = "Unknown artist"
        album = ""
        release_date = ""
        popularity = None

        # Prefer Spotify's API for reliable track + artist metadata.
        metadata = await _fetch_spotify_track_metadata(content)

        if metadata:
            song_title = metadata.get("title") or None
            artist = metadata.get("artist") or "Unknown artist"
            album = metadata.get("album") or ""
            release_date = metadata.get("release_date") or ""
            popularity = metadata.get("popularity")

        # Discord embeds are still a fallback for links we cannot resolve through Spotify.
        if not song_title:
            await asyncio.sleep(5)

            try:
                message = await message.channel.fetch_message(message.id)
            except Exception:
                pass

            if message.embeds:
                for embed in message.embeds:
                    if embed.title:
                        song_title = embed.title
                    if getattr(embed, "author", None) and embed.author.name:
                        artist = embed.author.name
                    if song_title:
                        break

        if not song_title:
            song_title = "this spotify link"

        review = await ask_gemini_music_review(
            song_title=song_title,
            artist=artist,
            album=album,
            release_date=release_date,
            popularity=popularity,
            poster_id=message.author.id,
            poster_display_name=message.author.display_name,
        )

        if review:
            await message.reply(
                review,
                mention_author=False,
            )

            # Fergie 5.0 Stage I.1:
            # qualifying critic scores get a witty public reward plus a
            # deduplicated private handoff to the DJ download/import channel.
            score_value = _fergie_extract_music_score(review)
            spotify_track_url = _fergie_spotify_track_url(content)

            if (
                score_value is not None
                and score_value >= FERGIE_DJ_CANDIDATE_SCORE
                and spotify_track_url
            ):
                try:
                    candidate_result = await _fergie_handoff_dj_candidate(
                        spotify_url=spotify_track_url,
                        song_title=song_title,
                        artist=artist,
                        album=album,
                        score=score_value,
                        poster_id=message.author.id,
                        poster_display_name=message.author.display_name,
                    )

                    if candidate_result.get("ok"):
                        reward = _fergie_dj_candidate_reward_line(
                            song_title=song_title,
                            artist=artist,
                            score=score_value,
                            already_queued=(
                                candidate_result.get("status")
                                == "already_queued"
                            ),
                        )

                        await message.reply(
                            reward,
                            mention_author=False,
                        )

                except Exception as e:
                    # Never break the proven critic because the DJ handoff is down.
                    print(
                        "FERGIE DJ CANDIDATE PIPELINE ERROR ❌ "
                        f"{type(e).__name__}: {e}"
                    )

            return

        # Gemini/Spotify failure fallback: keep the large verdict pool so this
        # feature still responds instead of silently dying.
        verdict = (
            "mother's aux privileges remain undefeated."
            if message.author.id == USER3_ID
            else random.choice(FERGIE_MUSIC_VERDICTS)
        )

        score = f"{random.uniform(3.0, 9.5):.1f}"

        replies = [
            f"🎧 **{song_title}** — {artist}\n{verdict}\n{score}/10",
            f"ugh. **{song_title}** by **{artist}**.\n{verdict}\n{score}/10",
            f"LISTEN. **{song_title}** — **{artist}**\n{verdict}\nrating: {score}/10",
            f"☕🎧 **{song_title}** — **{artist}**\n{verdict}\n{score}/10",
        ]

        await message.reply(
            random.choice(replies),
            mention_author=False,
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

    # Once/day when LOBO_ID posts.
    # This used to piggyback on the old bread economy record; it now has its own KV state.
    if message.author.id == LOBO_ID:
        today = _today_key()
        lobo_state = await _db_get("lobo_daily")
        if not isinstance(lobo_state, dict):
            lobo_state = {}
        if lobo_state.get("date") != today:
            await message.channel.send(f"<@{LOBO_ID}> send me money lobo.")
            lobo_state["date"] = today
            await _db_set("lobo_daily", lobo_state)

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

    # Special: reply to USER3_ID with USER3_LINES only when she is NOT directly talking to Fergie.
    # Explicit @fergie requests must reach the normal AI mention handler.
    if message.author.id == USER3_ID and not mentioned:
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

    # If USER3 speaks without directly addressing Fergie, maybe reply in their style.
    # Direct @fergie messages bypass mimic so Viv can use Fergie's AI normally.
    if message.author.id == USER3_ID and not mentioned:
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

        # Fergie Say: turn requested text directly into a voice post.
        # Example: @fergie say carne asada
        say_match = re.match(r"^say\s+(.+)$", question, flags=re.IGNORECASE | re.DOTALL)
        if say_match:
            say_text = say_match.group(1).strip()

            # Keep explicit Say requests reasonably short for a Discord voice post.
            if len(say_text) > 1800:
                say_text = say_text[:1800]

            if not say_text:
                await message.reply("say what, fak. 🙄", mention_author=False)
                return

            audio = await generate_fergie_text_voice(say_text)

            if not audio:
                await message.reply(
                    "fak. my voice machine isn't cooperating. 🙄",
                    mention_author=False,
                )
                return

            try:
                audio_file = discord.File(
                    io.BytesIO(audio),
                    filename=f"fergie_say_{message.author.id}.mp3",
                )

                await message.reply(
                    file=audio_file,
                    mention_author=False,
                )

                print(
                    f"FERGIE SAY VOICE SENT ✅ "
                    f"user={message.author.id} bytes={len(audio)}"
                )
            except Exception as e:
                print(
                    f"FERGIE SAY VOICE SEND ERROR: "
                    f"{type(e).__name__}: {e}"
                )
                await message.reply(
                    "fak. i made the audio and discord ate it. 🙄",
                    mention_author=False,
                )
            return

        # Fergie Picture Fetch: search for a real existing picture.
        # This is separate from Art and does NOT consume an Art generation.
        picture_query = _fergie_picture_search_query(question)
        if picture_query:
            wait = await message.reply(
                f"ugh fine. looking for **{picture_query}**... 📸🙄",
                mention_author=False,
            )

            try:
                image_bytes, filename, source_url, source_title = (
                    await fetch_fergie_picture(picture_query)
                )
            except Exception as e:
                print(
                    f"FERGIE PICTURE HANDLER ERROR: "
                    f"{type(e).__name__}: {e}"
                )
                image_bytes = None
                filename = None
                source_url = None
                source_title = None

            if not image_bytes:
                await wait.edit(
                    content=(
                        f"fak. Google found sources for **{picture_query}**, but i couldn't pull a usable pic. 🙄"
                    )
                )
                return

            try:
                await wait.delete()
            except Exception:
                pass

            source_line = (
                f"\n*source: {source_url}*"
                if source_url
                else ""
            )

            await message.reply(
                content=f"found one. 🙄📸{source_line}",
                file=discord.File(
                    io.BytesIO(image_bytes),
                    filename=filename or "fergie_found_pic.jpg",
                ),
                mention_author=False,
            )
            return

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
            "`@fergie say <text>` — Make me say it as a voice post\n"
            "`@fergie show me a picture of <thing>` — Find a real picture with Google Search\n"
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
        name="🛠️ Utilities",
        value=(
            "`!version` — Bot/runtime status\n"
            "`!kewchie-debug` — Spotify playlist debug"
        ),
        inline=False
    )

    e.set_footer(text="there. you're welcome. 🙄 • try !halp art, etc.")
    await ctx.send(embed=e)

# ================== Version Command ==================
@bot.command(name="version", help="Show bot version and runtime status")
async def version(ctx):
    from discord import Embed, Colour
    db_status = "connected ✅" if (DATABASE_URL and db_pool) else ("no DATABASE_URL ❌" if not DATABASE_URL else "not connected ❌")
    fields = [
        ("Version", BOT_VERSION),
        ("Build", BUILD_TAG),
        ("DB", db_status),
        ("VC Brain", "ready ✅" if VC_BRIDGE_SECRET else "not configured ❌"),
        ("Art", f"{FERGIE_IMAGE_DAILY_LIMIT}/day"),
        ("Picture Fetch", "Google Search"),
        ("Fit Channel", f"<#{FIT_CHANNEL_ID}>"),
        ("Kewchie Channel", f"<#{KEWCHIE_CHANNEL_ID}>"),
    ]
    e = Embed(title="Fergie Status", colour=Colour.blurple())
    for n, v in fields:
        e.add_field(name=n, value=v, inline=False)
    await ctx.send(embed=e)
    
# ================== Fergie 4.5 Self-Test ==================
# Admin-only diagnostics.
#
# !selftest       = fast/non-invasive checks
# !selftest full  = adds lightweight live integration checks
#
# IMPORTANT:
# - Does NOT generate Art.
# - Does NOT fire schedulers.
# - Does NOT trigger easter eggs/jumpscares.
# - Does NOT modify memories/reminders/mimic.
# - DB full-test uses a temporary key and deletes it immediately.

async def _fergie_selftest_db_roundtrip():
    """Safe temporary Neon/Postgres read/write/delete test."""
    if not db_pool:
        return False, "DB pool not connected"

    test_key = f"fergie_selftest:{int(time.time())}"

    try:
        await _db_set(
            test_key,
            {
                "ok": True,
                "timestamp": int(time.time()),
            },
        )

        result = await _db_get(test_key)

        if not isinstance(result, dict) or result.get("ok") is not True:
            return False, "DB write/read mismatch"

        # Clean the temporary key back out.
        async with db_pool.acquire() as con:
            await con.execute(
                "DELETE FROM public.kv WHERE key=$1",
                test_key,
            )

        return True, "temporary write/read/delete passed"

    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


async def _fergie_selftest_vc_health():
    """Check Fergie's local Python VC brain bridge without touching Discord VC."""
    try:
        url = f"http://127.0.0.1:{VC_BRIDGE_PORT}/health"

        timeout = aiohttp.ClientTimeout(total=5)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    return False, f"HTTP {response.status}"

                data = await response.json(content_type=None)

        if not isinstance(data, dict) or data.get("ok") is not True:
            return False, f"unexpected response: {data}"

        return True, "VC brain health endpoint responding"

    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


async def _fergie_selftest_gemini():
    """Tiny live Gemini text test. Used only by !selftest full."""
    if not GEMINI_KEY:
        return False, "GEMINI_API_KEY missing"

    try:
        answer = await ask_gemini(
            "Fergie system diagnostic. Reply with exactly: FERGIE_SELFTEST_OK"
        )

        if not answer:
            return False, "empty Gemini response"

        cleaned = answer.strip().upper()

        if "FERGIE_SELFTEST_OK" not in cleaned:
            return False, f"unexpected reply: {answer[:100]}"

        return True, "Gemini responded"

    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


async def _fergie_selftest_spotify():
    """Validate Spotify credentials/token without posting anything."""
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        return False, "Spotify credentials missing"

    try:
        token = await _get_spotify_token()

        if not token:
            return False, "Spotify token request failed"

        return True, "Spotify token received"

    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def _fergie_selftest_function(name):
    obj = globals().get(name)

    if obj is None:
        return False, "missing"

    if not callable(obj):
        return False, "exists but is not callable"

    return True, "loaded"


def _fergie_selftest_command(name):
    cmd = bot.get_command(name)

    if cmd is None:
        return False, "not registered"

    return True, "registered"


def _fergie_selftest_task(name):
    task = globals().get(name)

    if task is None:
        return False, "missing"

    try:
        running = task.is_running()
    except Exception:
        return False, "exists but is not a valid task loop"

    return (
        running,
        "running" if running else "loaded but NOT running"
    )


def _fergie_selftest_asset(path):
    if os.path.exists(path):
        return True, "found"

    return False, "file missing"


@bot.command(
    name="selftest",
    help="ADMIN: Run Fergie 4.5 diagnostics. Use !selftest full for live integration tests.",
)
async def selftest(ctx, mode: str = "fast"):

    # Jonathan/admin only.
    if ctx.author.id != FERGIE_ADMIN_USER_ID:
        await ctx.reply(
            "nice try fak. diagnostics are admin-only. 🙄",
            mention_author=False,
        )
        return

    if ctx.channel.id != FERGIE_TEST_CHANNEL_ID:
        await ctx.reply(
            f"run diagnostics in <#{FERGIE_TEST_CHANNEL_ID}> only. 🙄",
            mention_author=False,
        )
        return

    full_mode = mode.lower().strip() == "full"

    wait = await ctx.reply(
        (
            "running the full brain scan. fak. 🧠🔧"
            if full_mode
            else "checking my organs. one sec. 🙄🔧"
        ),
        mention_author=False,
    )

    results = []

    def record(section, name, passed, detail=""):
        results.append({
            "section": section,
            "name": name,
            "passed": bool(passed),
            "detail": str(detail or ""),
        })

    # ==========================================================
    # CORE CONFIG
    # ==========================================================

    record(
        "Core",
        "Discord token",
        bool(TOKEN),
        "configured" if TOKEN else "missing",
    )

    record(
        "Core",
        "Gemini key",
        bool(GEMINI_KEY),
        "configured" if GEMINI_KEY else "missing",
    )

    record(
        "Core",
        "Postgres URL",
        bool(DATABASE_URL),
        "configured" if DATABASE_URL else "missing",
    )

    record(
        "Core",
        "Postgres pool",
        bool(db_pool),
        "connected" if db_pool else "not connected",
    )

    record(
        "Core",
        "VC bridge secret",
        bool(VC_BRIDGE_SECRET),
        "configured" if VC_BRIDGE_SECRET else "missing",
    )

    record(
        "Core",
        "ElevenLabs",
        bool(ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID),
        (
            "configured"
            if ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID
            else "key or voice ID missing"
        ),
    )

    record(
        "Core",
        "Spotify",
        bool(SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET),
        (
            "configured"
            if SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET
            else "credentials missing"
        ),
    )

    # ==========================================================
    # IMPORTANT FUNCTIONS
    # ==========================================================

    function_checks = [
        # Main AI / lore
        "ask_gemini",
        "build_cast_context",

        # VC
        "ask_fergie_vc_brain",
        "start_vc_bridge_server",

        # Eyes
        "_fergie_static_image_attachments",
        "ask_gemini_image_reaction",
        "maybe_handle_fergie_image",

        # Art
        "generate_fergie_image",
        "_fergie_art_slots_left",
        "_fergie_consume_art_slot",
        "_fergie_refund_art_slot",
        "_fergie_reset_art_count",
        "_fergie_art_cooldown_remaining",

        # Picture Fetch
        "fetch_fergie_picture",
        "_fergie_google_grounded_pages",

        # Voice
        "generate_fergie_text_voice",
        "maybe_send_fergie_voice_reply",

        # TLDR
        "make_fergie_tldr",

        # Memory / reminders
        "get_user_memories",
        "save_user_memories",
        "load_reminders",
        "save_reminders",

        # Mimic
        "_mimic_generate",
        "_mimic_load_corpus",
        "_mimic_build_markov",

        # Spotify / critic
        "_get_spotify_token",
        "_fetch_spotify_track_metadata",
        "ask_gemini_music_review",
        "_fergie_music_profile",
        "_fergie_save_music_profile",

        # GIF helper
        "fetch_gif",
    ]

    for name in function_checks:
        passed, detail = _fergie_selftest_function(name)
        record("Functions", name, passed, detail)

    # ==========================================================
    # COMMAND REGISTRATION
    # ==========================================================

    command_checks = [
        "halp",
        "version",
        "art",
        "resetart",
        "hawaii",
        "fit",
        "kewchie",
        "kewchie-debug",
        "cafe",
        "scam",
        "bbl",
        "selftest",
    ]

    for name in command_checks:
        passed, detail = _fergie_selftest_command(name)
        record("Commands", f"!{name}", passed, detail)

    # ==========================================================
    # VERIFY DEAD ECONOMY/CASINO COMMANDS STAY DEAD
    # ==========================================================

    removed_commands = [
        "roll",
        "slots",
        "raffle",
        "duel",
        "putasos",
        "claim",
        "gift",
        "bank",
        "balance",
        "seed",
        "take",
        "setbal",
    ]

    for name in removed_commands:
        exists = bot.get_command(name) is not None

        record(
            "Cleanup",
            f"!{name} removed",
            not exists,
            "correctly absent" if not exists else "UNEXPECTEDLY REGISTERED",
        )

    # ==========================================================
    # SCHEDULERS
    # ==========================================================

    scheduler_checks = [
        "user1_twice_daily_fixed",
        "user2_twice_daily_fixed",
        "user3_task",
        "daily_scam_post",
        "kewchie_daily_scheduler",
        "fit_auto_daily",
        "bonk_papo_scheduler",
        "rebuild_mimic",
        "fergie_bored",
        "fergie_birthday_watcher",
        "fergie_reminders",
        "daily_gym_reminder",
    ]

    for name in scheduler_checks:
        passed, detail = _fergie_selftest_task(name)
        record("Schedulers", name, passed, detail)

    # ==========================================================
    # LORE / CAST
    # ==========================================================

    record(
        "Lore",
        "FERGIE_SELF_LORE",
        bool(FERGIE_SELF_LORE and len(FERGIE_SELF_LORE) > 100),
        f"{len(FERGIE_SELF_LORE)} chars",
    )

    record(
        "Lore",
        "FERGIE_CAST",
        isinstance(FERGIE_CAST, dict) and len(FERGIE_CAST) > 0,
        f"{len(FERGIE_CAST)} members",
    )

    # Jonathan must remain canonical.
    jonathan = FERGIE_CAST.get(FERGIE_ADMIN_USER_ID)

    record(
        "Lore",
        "Jonathan identity",
        bool(
            jonathan
            and jonathan.get("name") == "Jonathan"
        ),
        (
            jonathan.get("name")
            if isinstance(jonathan, dict)
            else "missing"
        ),
    )

    # ==========================================================
    # ART STATE — READ ONLY
    # ==========================================================

    try:
        left = await _fergie_art_slots_left()

        record(
            "Art",
            "Daily counter",
            isinstance(left, int) and 0 <= left <= FERGIE_IMAGE_DAILY_LIMIT,
            f"{left}/{FERGIE_IMAGE_DAILY_LIMIT} remaining",
        )

    except Exception as e:
        record(
            "Art",
            "Daily counter",
            False,
            f"{type(e).__name__}: {e}",
        )

    try:
        cooldown = _fergie_art_cooldown_remaining()

        record(
            "Art",
            "Cooldown helper",
            isinstance(cooldown, int) and cooldown >= 0,
            f"{cooldown}s",
        )

    except Exception as e:
        record(
            "Art",
            "Cooldown helper",
            False,
            f"{type(e).__name__}: {e}",
        )

    # ==========================================================
    # REQUIRED LOCAL ASSETS
    # ==========================================================

    asset_checks = [
        HYDRATION_VIDEO,
        "visual_refs/viviana.png",
        "visual_refs/khurty.png",
        "visual_refs/papo.png",
        "visual_refs/chadwin.png",
        "visual_refs/raquel.png",
        "visual_refs/jonathan.png",
    ]

    for asset in asset_checks:
        passed, detail = _fergie_selftest_asset(asset)
        record("Assets", asset, passed, detail)

    # ==========================================================
    # FULL MODE — LIVE BUT NON-DESTRUCTIVE CHECKS
    # ==========================================================

    if full_mode:

        db_ok, db_detail = await _fergie_selftest_db_roundtrip()
        record("Live", "Neon round-trip", db_ok, db_detail)

        vc_ok, vc_detail = await _fergie_selftest_vc_health()
        record("Live", "VC brain health", vc_ok, vc_detail)

        gemini_ok, gemini_detail = await _fergie_selftest_gemini()
        record("Live", "Gemini text", gemini_ok, gemini_detail)

        spotify_ok, spotify_detail = await _fergie_selftest_spotify()
        record("Live", "Spotify token", spotify_ok, spotify_detail)

    # ==========================================================
    # REPORT
    # ==========================================================

    passed_count = sum(1 for x in results if x["passed"])
    failed_count = len(results) - passed_count

    if failed_count == 0:
        overall = "🟢 ALL CHECKS PASSED"
    else:
        overall = f"🔴 {failed_count} CHECK(S) FAILED"

    embed = discord.Embed(
        title="🧠 Fergie 4.5 Diagnostics",
        description=(
            f"**{overall}**\n"
            f"Mode: **{'FULL' if full_mode else 'FAST'}**\n"
            f"✅ {passed_count} passed • ❌ {failed_count} failed"
        ),
        colour=(
            discord.Colour.green()
            if failed_count == 0
            else discord.Colour.red()
        ),
    )

    sections = []

    for row in results:
        if row["section"] not in sections:
            sections.append(row["section"])

    for section in sections:
        rows = [
            row
            for row in results
            if row["section"] == section
        ]

        lines = []

        for row in rows:
            icon = "✅" if row["passed"] else "❌"

            detail = (
                f" — {row['detail']}"
                if row["detail"]
                else ""
            )

            lines.append(
                f"{icon} **{row['name']}**{detail}"
            )

        # Discord embed field limits are 1024 chars.
        text_block = "\n".join(lines)

        while text_block:
            chunk = text_block[:1000]

            # Try to cut cleanly on a newline.
            if len(text_block) > 1000:
                split_at = chunk.rfind("\n")

                if split_at > 0:
                    chunk = chunk[:split_at]

            embed.add_field(
                name=section,
                value=chunk,
                inline=False,
            )

            text_block = text_block[len(chunk):].lstrip("\n")

            # Avoid Discord's max field-count limit.
            if len(embed.fields) >= 24:
                break

        if len(embed.fields) >= 24:
            break

    embed.set_footer(
        text=(
            "FAST = inspection only • FULL = lightweight live integration checks"
        )
    )

    try:
        await wait.edit(
            content=None,
            embed=embed,
        )
    except Exception:
        await ctx.send(embed=embed)
        
# ================== Start ==================
if __name__ == "__main__":
    if not TOKEN or not TENOR_KEY or not CHANNEL_ID:
        raise SystemExit("Please set DISCORD_TOKEN, TENOR_API_KEY, and CHANNEL_ID environment variables.")
    # Final tiny typo fix for earlier block (safe at runtime)
    if 'REACTION_EMOETS' in globals():
        pass
    bot.run(TOKEN)
