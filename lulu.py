# cogs/lulu.py
import os
import re
import random
from datetime import datetime, time as dtime, timedelta, timezone
from zoneinfo import ZoneInfo

import aiohttp
import discord
from discord.ext import commands, tasks


FIT_CHANNEL_ID_DEFAULT = 1273436116699058290  # default “fit” channel
LULU_WHATS_NEW_URL = (
    "https://shop.lululemon.com/c/women-whats-new/n16o10zq0cf"
    "?icid=home-homepage;L1;l2;cdp:womens-whats-new;"
)


def _pick_one_time_today_pt(start_hour=8, end_hour=14):
    """Pick a random time today in PT and return it as a UTC datetime (minute precision)."""
    tz_pt = ZoneInfo("America/Los_Angeles")
    today = datetime.now(tz_pt).date()
    start_pt = datetime.combine(today, dtime(hour=start_hour), tzinfo=tz_pt)
    end_pt   = datetime.combine(today, dtime(hour=end_hour),   tzinfo=tz_pt)
    total_minutes = max(0, int((end_pt - start_pt).total_seconds() // 60) - 1)
    offset = random.randint(0, total_minutes) if total_minutes else 0
    when_pt = start_pt + timedelta(minutes=offset)
    return when_pt.astimezone(timezone.utc).replace(second=0, microsecond=0)


async def fetch_random_lulu_link(page_url: str) -> str | None:
    """Fetch 'What's New' and return a random product URL (fallback to None)."""
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(page_url, headers=headers, timeout=20, allow_redirects=True) as r:
                if r.status != 200:
                    return None
                html = await r.text()
    except Exception:
        return None

    candidates = set()
    for href in re.findall(r'href="([^"]+)"', html):
        if "shop.lululemon.com" in href and "/p/" in href:
            candidates.add(href.split("?")[0])
        elif href.startswith("/p/"):
            candidates.add("https://shop.lululemon.com" + href.split("?")[0])

    return random.choice(list(candidates)) if candidates else None


class LuluCog(commands.Cog):
    """Lululemon once-a-day drop + on-demand command."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # message copy: env > runtime override > default
        self._default_msg = os.getenv("LULU_MSG", "").strip() or 'thoughts girlie? I need new fits. 💗 😏'
        # channel: env > default
        self.lulu_channel_id = int(os.getenv("LULU_CHANNEL_ID", str(FIT_CHANNEL_ID_DEFAULT)))
        # daily scheduler state
        self._today_target: datetime | None = None
        self._posted_today: bool = False

    def get_msg(self) -> str:
        return getattr(self.bot, "_lulu_msg", "") or self._default_msg

    @tasks.loop(minutes=1)
    async def daily(self):
        now_utc = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        if self._today_target is None or self._today_target.date() != now_utc.date():
            self._today_target = _pick_one_time_today_pt(8, 14)
            self._posted_today = False

        if (not self._posted_today) and abs((now_utc - self._today_target).total_seconds()) <= 60:
            try:
                ch = self.bot.get_channel(self.lulu_channel_id) or await self.bot.fetch_channel(self.lulu_channel_id)
                if ch:
                    link = await fetch_random_lulu_link(LULU_WHATS_NEW_URL) or LULU_WHATS_NEW_URL
                    await ch.send(f"{self.get_msg()}\\n{link}")
                self._posted_today = True
            except Exception as e:
                # Don’t crash loop if channel fetch/send fails
                print("lulu daily error:", repr(e))
                self._posted_today = True

    @daily.before_loop
    async def _wait_ready(self):
        await self.bot.wait_until_ready()

    async def cog_load(self):
        # start the loop when the cog loads
        if not self.daily.is_running():
            self.daily.start()

    async def cog_unload(self):
        # stop the loop cleanly on unload
        if self.daily.is_running():
            self.daily.cancel()

    # ------- Prefix command -------
    @commands.command(name="lulu", help="Post a random Lululemon 'What’s New' link", aliases=["lululemon"])
    @commands.guild_only()
    async def lulu_cmd(self, ctx: commands.Context, *, arg: str | None = None):
        try:
            # setmsg override
            if arg and arg.lower().startswith("setmsg "):
                new_msg = arg[7:].strip()
                if not new_msg:
                    return await ctx.reply("Give me some text after `setmsg`.")
                self.bot._lulu_msg = new_msg
                return await ctx.reply(f"Updated Lulu message to:\\n> {self.bot._lulu_msg}")

            # target channel
            target = ctx.channel
            if arg:
                m = re.search(r"<#(\\d+)>|^(\\d{15,25})$", arg.strip())
                if m:
                    chan_id = int((m.group(1) or m.group(2)))
                    target = ctx.guild.get_channel(chan_id) or await ctx.guild.fetch_channel(chan_id)

            async with ctx.typing():
                link = await fetch_random_lulu_link(LULU_WHATS_NEW_URL)
            link = link or LULU_WHATS_NEW_URL
            await target.send(f"{self.get_msg()}\\n{link}")
            if target.id != ctx.channel.id:
                await ctx.reply(f"Dropped one in <#{target.id}> ✅")
        except Exception as e:
            # Always give a visible reply instead of failing silently
            try:
                await ctx.reply("couldn't fetch a product rn, dropping the main page instead 💅\\n" + LULU_WHATS_NEW_URL)
            except Exception:
                pass
            print("!lulu error:", repr(e))

    # ------- Slash command -------
    @discord.app_commands.command(name="lulu", description="Post a random Lululemon link")
    @discord.app_commands.describe(
        channel="Where to post (defaults to here)",
        message_override="Temporarily override the message copy",
    )
    async def lulu_slash(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
        message_override: str | None = None,
    ):
        ch = channel or interaction.channel
        link = await fetch_random_lulu_link(LULU_WHATS_NEW_URL) or LULU_WHATS_NEW_URL
        msg = (message_override.strip() if message_override else self.get_msg())
        await ch.send(f"{msg}\\n{link}")
        await interaction.response.send_message(f"Sent in <#{ch.id}> ✅", ephemeral=True)


async def setup(bot: commands.Bot):
    # Preferred in discord.py 2.x: async extension setup
    await bot.add_cog(LuluCog(bot))
