
import os
import random
import asyncio
import discord
from collections import deque
from discord.ext import tasks, commands


class ChatDropCog(commands.Cog):
    """
    Lightweight chat-drop add-on.
    - Spawns a "bread drop" embed when a channel is active.
    - First user to react with the emoji OR type !get claims it.
    - Uses helper functions provided by the host bot for economy updates.
    """

    def __init__(self, bot: commands.Bot, helpers: dict):
        self.bot = bot

        # --- pull helpers from host bot (MUST be provided when adding the cog) ---
        self.helpers = helpers
        self._now = helpers["now"]
        self._fmt_bread = helpers["fmt_bread"]
        self._cap_wallet = helpers["cap_wallet"]
        self._get_user = helpers["get_user"]
        self._save_bank = helpers["save_bank"]
        self._economy = helpers["economy"]
        self._lock = helpers["economy_lock"]

        # --- tunables (env overridable) ---
        self.CHANCE = float(os.getenv("CHATDROP_CHANCE", "0.22"))
        self.MIN_INTERVAL = int(os.getenv("CHATDROP_MIN_INTERVAL_SEC", "60"))
        self.WINDOW_SEC = int(os.getenv("CHATDROP_WINDOW_SEC", "120"))
        self.CLAIM_WINDOW = int(os.getenv("CHATDROP_CLAIM_WINDOW_SEC", "25"))
        self.AMOUNTS = [2, 5, 10, 20]
        self.EMOJI = os.getenv("CHATDROP_REACTION_EMOJI", "🍞")
        self.COLOR = int(os.getenv("CHATDROP_EMBED_COLOR", str(0xF4A261)))

        # --- runtime state ---
        self.activity: dict[int, deque] = {}   # channel_id -> deque[timestamps]
        self.last_drop: dict[int, float] = {}  # channel_id -> last drop ts
        self.drops: dict[int, dict] = {}       # msg_id -> {amount, expires, channel_id, claimed}
        self.ch_pending: dict[int, int] = {}   # channel_id -> msg_id

        # background watcher
        self._watcher.start()

    def cog_unload(self):
        self._watcher.cancel()

    # ---------------------- internal helpers ----------------------
    def _bump(self, ch_id: int):
        now = self._now()
        q = self.activity.get(ch_id)
        if q is None:
            q = deque()
            self.activity[ch_id] = q
        q.append(now)
        cutoff = now - self.WINDOW_SEC
        while q and q[0] < cutoff:
            q.popleft()

    def _active(self, ch_id: int) -> bool:
        now = self._now()
        q = self.activity.get(ch_id, deque())
        cutoff = now - self.WINDOW_SEC
        while q and q[0] < cutoff:
            q.popleft()
        return len(q) >= 4

    def _can_drop(self, ch_id: int) -> bool:
        last = self.last_drop.get(ch_id, 0.0)
        return (self._now() - last) >= self.MIN_INTERVAL and ch_id not in self.ch_pending

    async def _spawn_drop(self, channel: discord.abc.Messageable, ch_id: int):
        amount = random.choice(self.AMOUNTS)
        embed = discord.Embed(
            title="Bread drop!",
            description=(
                f"First to react with {self.EMOJI} **or** type `!get` in this channel "
                f"wins **{self._fmt_bread(amount)}**.\nExpires in {self.CLAIM_WINDOW}s."
            ),
            colour=self.COLOR
        )
        msg = await channel.send(embed=embed)
        try:
            await msg.add_reaction(self.EMOJI)
        except Exception:
            pass

        self.drops[msg.id] = {
            "amount": amount,
            "expires": self._now() + self.CLAIM_WINDOW,
            "channel_id": ch_id,
            "claimed": False,
        }
        self.ch_pending[ch_id] = msg.id
        self.last_drop[ch_id] = self._now()

    async def _payout(self, member: discord.Member, drop: dict, channel: discord.abc.Messageable):
        async with self._lock:
            u = self._get_user(member.id)
            if self._economy["treasury"] <= 0:
                await channel.send(f"{member.mention} The bank is empty. 💀 No drop payout.")
                return
            pay = min(drop["amount"], self._economy["treasury"])
            new_bal = u["balance"] + pay
            final_bal, skim = self._cap_wallet(new_bal)
            self._economy["treasury"] -= (pay - skim)
            u["balance"] = final_bal
            await self._save_bank()

        msg = (
            f"{member.mention} grabbed the drop for **{self._fmt_bread(pay)}**! "
            f"new: **{self._fmt_bread(u['balance'])}**"
        )
        if skim:
            msg += f" (cap skim **{self._fmt_bread(skim)}** back to bank)"
        await channel.send(msg)

    # ---------------------- listeners ----------------------
    @commands.Cog.listener("on_message")
    async def _activity_listener(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        if message.content and message.content.strip().startswith("!"):
            # don't count commands as activity
            return

        ch_id = message.channel.id
        self._bump(ch_id)

        if self._active(ch_id) and self._can_drop(ch_id) and random.random() < self.CHANCE:
            await self._spawn_drop(message.channel, ch_id)

    @commands.Cog.listener("on_raw_reaction_add")
    async def _on_reaction(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == getattr(self.bot.user, "id", None):
            return
        msg_id = payload.message_id
        drop = self.drops.get(msg_id)
        if not drop or drop["claimed"]:
            return
        # only accept our emoji
        if str(payload.emoji) != str(self.EMOJI):
            return

        guild = self.bot.get_guild(payload.guild_id) if payload.guild_id else None
        if not guild:
            return
        member = guild.get_member(payload.user_id)
        if not member or member.bot:
            return
        channel = self.bot.get_channel(drop["channel_id"])
        if not channel:
            return

        drop["claimed"] = True
        self.ch_pending.pop(drop["channel_id"], None)
        await self._payout(member, drop, channel)

    # ---------------------- commands ----------------------
    @commands.command(name="cdping")
    async def cdping(self, ctx: commands.Context):
        """Quick sanity check that the Cog loaded."""
        await ctx.send("ChatDropCog is alive ✅")

    @commands.command(name="chatdrop_debug")
    async def chatdrop_debug(self, ctx: commands.Context):
        msg_id = self.ch_pending.get(ctx.channel.id)
        status = "active" if msg_id else "none"
        await ctx.send(
            f"ChatDrop status: {status} · "
            f"Chance={self.CHANCE}, MinInterval={self.MIN_INTERVAL}s, "
            f"Window={self.WINDOW_SEC}s, ClaimWindow={self.CLAIM_WINDOW}s"
        )

    @commands.command(name="dropnow")
    async def dropnow(self, ctx: commands.Context):
        """Force a drop in the current channel (for testing)."""
        await self._spawn_drop(ctx.channel, ctx.channel.id)

    @commands.command(name="get")
    async def get(self, ctx: commands.Context):
        msg_id = self.ch_pending.get(ctx.channel.id)
        if not msg_id:
            await ctx.send("No active drop to claim here. Keep chatting!")
            return
        drop = self.drops.get(msg_id)
        if not drop or drop["claimed"]:
            await ctx.send("Someone already grabbed it. 😤")
            return
        if self._now() > drop["expires"]:
            await ctx.send("Drop expired. ⏰")
            self.ch_pending.pop(ctx.channel.id, None)
            self.drops.pop(msg_id, None)
            return

        drop["claimed"] = True
        self.ch_pending.pop(ctx.channel.id, None)
        await self._payout(ctx.author, drop, ctx.channel)

    # ---------------------- background expiry ----------------------
    @tasks.loop(seconds=10)
    async def _watcher(self):
        now = self._now()
        to_remove = []
        for msg_id, info in list(self.drops.items()):
            if info["claimed"]:
                to_remove.append(msg_id)
                continue
            if now > info["expires"]:
                to_remove.append(msg_id)
                ch = self.bot.get_channel(info["channel_id"])
                if ch:
                    try:
                        await ch.send("⏰ Drop expired. Keep chatting to trigger another!")
                    except Exception:
                        pass
                self.ch_pending.pop(info["channel_id"], None)
        for m in to_remove:
            self.drops.pop(m, None)

    @_watcher.before_loop
    async def _wait_ready(self):
        await self.bot.wait_until_ready()
