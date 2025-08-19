# cogs/lulu_whatsnew.py
import os, re, random
from datetime import datetime, timedelta, time as dtime, timezone
from zoneinfo import ZoneInfo

import aiohttp
import discord
from discord.ext import tasks, commands

# === Config ===
LULU_URL = os.getenv(
    "LULU_WHATSNEW_URL",
    "https://shop.lululemon.com/c/women-whats-new/n16o10zq0cf?icid=home-homepage;L1;l2;cdp:womens-whats-new;"
).strip()

LULU_CHANNEL_ID = int(os.getenv("LULU_CHANNEL_ID", "1273436116699058290"))
LULU_TEXT = "thoughts girly? I need new fits. 💗🥹"

# === Parsing helpers ===
ABS_LINK_RE = re.compile(r'https://shop\.lululemon\.com[^"\s>]+/(?:p|product)/[^"\s>#]+', re.I)
REL_LINK_RE = re.compile(r'href="(/[^"\s>]+/(?:p|product)/[^"\s>#]+)"', re.I)
BASE = "https://shop.lululemon.com"
PT = ZoneInfo("America/Los_Angeles")

def _today_pt():
    return datetime.now(PT).date()

def _pick_random_time_pt(start_hour=8, end_hour=14):
    """Random PT time today in [start_hour, end_hour). Returns UTC datetime (minute precision)."""
    today = _today_pt()
    start = datetime.combine(today, dtime(hour=start_hour, tzinfo=PT))
    end   = datetime.combine(today, dtime(hour=end_hour, tzinfo=PT))
    total_minutes = int((end - start).total_seconds() // 60)
    if total_minutes <= 0:
        start += timedelta(days=1)
        end   += timedelta(days=1)
        total_minutes = int((end - start).total_seconds() // 60)
    offset = random.randint(0, max(0, total_minutes - 1))
    return (start + timedelta(minutes=offset)).astimezone(timezone.utc).replace(second=0, microsecond=0)

class LuluWhatsNewCog(commands.Cog):
    """Daily: post 1 random Lululemon What's New (Women) item. Also supports !lulu command."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._target_time_utc = None
        self._target_day = None
        self._posted_keys = set()
        self.scheduler.start()

    def cog_unload(self):
        try:
            self.scheduler.cancel()
        except Exception:
            pass

    async def _fetch_links(self) -> list[str]:
        headers = {
            "User-Agent": "Mozilla/5.0 (DiscordBot Helper; +https://discord.com) AppleWebKit/537.36 (KHTML, like Gecko) Safari/537.36"
        }
        links = set()
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(LULU_URL, headers=headers, timeout=20) as r:
                    if r.status != 200:
                        return []
                    html = await r.text()
            for m in ABS_LINK_RE.findall(html):
                links.add(m.split('"')[0])
            for m in REL_LINK_RE.findall(html):
                if m.startswith("/"):
                    links.add(BASE + m)
            links = {u for u in links if "/p/" in u or "/product/" in u}
        except Exception:
            return []
        return sorted(links)

    async def _post_random(self, *, destination: discord.abc.Messageable = None):
        ch = destination
        if ch is None:
            ch = self.bot.get_channel(LULU_CHANNEL_ID) or await self.bot.fetch_channel(LULU_CHANNEL_ID)
        if not ch:
            return False, "Target channel not found"

        links = await self._fetch_links()
        if not links:
            return False, "No product links found"

        url = random.choice(list(links))
        await ch.send(f"{url}\n{LULU_TEXT}")
        return True, url

    def _ensure_today_target(self):
        now_utc = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        today_key = _today_pt().isoformat()

        if (self._target_time_utc is None) or (self._target_day != today_key):
            self._target_time_utc = _pick_random_time_pt(8, 14)
            self._target_day = today_key
            self._posted_keys.discard(today_key)

        if now_utc > self._target_time_utc:
            self._target_time_utc = _pick_random_time_pt(8, 14) + timedelta(days=1)
            self._target_day = (_today_pt() + timedelta(days=1)).isoformat()
            self._posted_keys.discard(self._target_day)

    @tasks.loop(minutes=1)
    async def scheduler(self):
        await self.bot.wait_until_ready()
        self._ensure_today_target()
        now_utc = datetime.now(timezone.utc).replace(second=0, microsecond=0)

        if self._target_time_utc and abs((now_utc - self._target_time_utc).total_seconds()) <= 60:
            day_key = self._target_day
            if day_key not in self._posted_keys:
                try:
                    await self._post_random()
                finally:
                    self._posted_keys.add(day_key)

    @scheduler.before_loop
    async def _before(self):
        await self.bot.wait_until_ready()

    # === The command you asked for: !lulu ===
    @commands.command(name="lulu", help="Post a random Lululemon What's New (Women) item now.")
    @commands.cooldown(1, 10, commands.BucketType.guild)
    async def lulu_cmd(self, ctx: commands.Context):
        """Manual trigger for testing or ad-hoc posting."""
        try:
            await ctx.trigger_typing()
        except Exception:
            pass

        ok, msg = await self._post_random()  # posts to configured channel
        if ok:
            if ctx.channel.id != LULU_CHANNEL_ID:
                await ctx.reply(f"Posted to <#{LULU_CHANNEL_ID}> ✅")
            else:
                await ctx.reply("Posted ✅")
        else:
            await ctx.reply(f"Couldn’t post: {msg}")

# Extension entrypoint (works if you use extensions)
async def setup(bot: commands.Bot):
    await bot.add_cog(LuluWhatsNewCog(bot))
