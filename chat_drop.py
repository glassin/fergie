import os, random, asyncio, discord, time
from collections import deque, Counter
from discord.ext import tasks, commands

class ChatDropCog(commands.Cog):
    """
    Safe, plug-in Cog: active-chat currency drops with dual-claim (reaction OR !get).
    This Cog does NOT overwrite your commands or events; it listens alongside them.
    """

    def __init__(self, bot: commands.Bot, helpers: dict):
        self.bot = bot

        # Pull helpers from your existing bot so we don't duplicate logic:
        self._now         = helpers["now"]
        self._fmt_bread   = helpers["fmt_bread"]
        self._cap_wallet  = helpers["cap_wallet"]
        self._user        = helpers["get_user"]
        self._save_bank   = helpers["save_bank"]
        self.economy      = helpers["economy"]
        self.economy_lock = helpers["economy_lock"]

        # Tunables (env override-friendly)
        self.CHATDROP_MIN_INTERVAL_SEC = int(os.getenv("CHATDROP_MIN_INTERVAL_SEC", "60"))
        self.CHATDROP_MAX_INTERVAL_SEC = int(os.getenv("CHATDROP_MAX_INTERVAL_SEC", "420"))
        self.CHATDROP_DECAY_SEC        = int(os.getenv("CHATDROP_DECAY_SEC", "180"))
        self.CHATDROP_WINDOW_SEC       = int(os.getenv("CHATDROP_WINDOW_SEC", "120"))
        self.CHATDROP_AMOUNTS          = [2, 5, 10, 20]
        self.CHATDROP_CHANCE           = float(os.getenv("CHATDROP_CHANCE", "0.22"))
        self.CHATDROP_CLAIM_WINDOW_SEC = int(os.getenv("CHATDROP_CLAIM_WINDOW_SEC", "25"))
        self.CHATDROP_REACTION_EMOJI   = os.getenv("CHATDROP_REACTION_EMOJI", "<:autistic_hug:1131707829611413524>")
        self.CHATDROP_EMBED_COLOR      = int(os.getenv("CHATDROP_EMBED_COLOR", str(0xF4A261)))

        # Runtime state
        self._recent_activity = {}   # ch_id -> deque[timestamps]
        self._last_drop_ts    = {}   # ch_id -> float
        self._pending_drops   = {}   # msg_id -> {amount, expires, channel_id, claimed}
        self._channel_pending = {}   # ch_id -> msg_id
        self._claimed_drops   = set()

        # Start expiry watcher
        self.chat_drop_watcher.start()

    def cog_unload(self):
        # Stop task when Cog is unloaded
        self.chat_drop_watcher.cancel()

    # ===== Internal helpers =====
    def _prune_activity(self, q: deque, now_ts: float):
        cutoff = now_ts - self.CHATDROP_WINDOW_SEC
        while q and q[0] < cutoff:
            q.popleft()

    def _activity_bump(self, channel_id: int):
        now_ts = self._now()
        q = self._recent_activity.get(channel_id)
        if q is None:
            q = deque()
            self._recent_activity[channel_id] = q
        q.append(now_ts)
        self._prune_activity(q, now_ts)

    def _channel_is_active(self, channel_id: int) -> bool:
        now_ts = self._now()
        q = self._recent_activity.get(channel_id, deque())
        self._prune_activity(q, now_ts)
        return len(q) >= 4

    def _can_drop_in_channel(self, channel_id: int) -> bool:
        now_ts = self._now()
        last = self._last_drop_ts.get(channel_id, 0.0)
        return (now_ts - last) >= self.CHATDROP_MIN_INTERVAL_SEC and (channel_id not in self._channel_pending)

    async def _create_chat_drop(self, channel: discord.abc.Messageable, channel_id: int):
        amt = random.choice(self.CHATDROP_AMOUNTS)
        embed = discord.Embed(
            title="Bread drop!",
            description=(
                f"First to react with {self.CHATDROP_REACTION_EMOJI} **or** type `!get` in this channel "
                f"wins **{self._fmt_bread(amt)}**.\nHurry! Expires in {self.CHATDROP_CLAIM_WINDOW_SEC}s."
            ),
            colour=self.CHATDROP_EMBED_COLOR
        )
        msg = await channel.send(embed=embed)
        try:
            await msg.add_reaction(self.CHATDROP_REACTION_EMOJI)
        except Exception:
            pass
        exp = self._now() + self.CHATDROP_CLAIM_WINDOW_SEC
        self._pending_drops[msg.id] = {"amount": amt, "expires": exp, "channel_id": channel_id, "claimed": False}
        self._channel_pending[channel_id] = msg.id
        self._last_drop_ts[channel_id] = self._now()

    # ===== Public listeners/commands =====
    @commands.Cog.listener("on_message")
    async def _chat_activity_listener(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        ch_id = message.channel.id
        if message.content and message.content.strip().startswith("!"):
            return
        self._activity_bump(ch_id)
        if (self._now() - self._last_drop_ts.get(ch_id, 0.0)) > self.CHATDROP_MAX_INTERVAL_SEC:
            self._recent_activity[ch_id] = deque()
        if self._channel_is_active(ch_id) and self._can_drop_in_channel(ch_id):
            if random.random() < self.CHATDROP_CHANCE:
                await self._create_chat_drop(message.channel, ch_id)

    @commands.Cog.listener("on_raw_reaction_add")
    async def _claim_by_reaction(self, payload: discord.RawReactionActionEvent):
        if not self.bot.user or payload.user_id == self.bot.user.id:
            return
        if str(payload.emoji) != self.CHATDROP_REACTION_EMOJI:
            return
        drop = self._pending_drops.get(payload.message_id)
        if not drop or drop.get("claimed") or self._now() > drop.get("expires", 0):
            return
        guild = self.bot.get_guild(payload.guild_id) if payload.guild_id else None
        if not guild:
            return
        member = guild.get_member(payload.user_id)
        if not member or member.bot:
            return
        ch = self.bot.get_channel(drop["channel_id"])
        if not ch:
            return
        drop["claimed"] = True
        self._channel_pending.pop(drop["channel_id"], None)
        self._claimed_drops.add(payload.message_id)
        async with self.economy_lock:
            u = self._user(member.id)
            if self.economy["treasury"] <= 0:
                try:
                    await ch.send(f"{member.mention} The bank is empty. 💀 No drop payout.")
                except Exception:
                    pass
                return
            pay = min(drop["amount"], self.economy["treasury"])
            new_bal = u["balance"] + pay
            final_bal, skim = self._cap_wallet(new_bal)
            self.economy["treasury"] -= (pay - skim)
            u["balance"] = final_bal
            await self._save_bank()
        try:
            await ch.send(
                f"{member.mention} snagged the drop for **{self._fmt_bread(pay)}**! "
                f"new: **{self._fmt_bread(u['balance'])}**"
                + (f" (cap skim **{self._fmt_bread(skim)}** back to bank)" if skim else "")
            )
        except Exception:
            pass

    @commands.command(name="get", help="Grab the latest bread drop in this channel (first-come-first-serve)")
    async def get_drop(self, ctx: commands.Context):
        msg_id = self._channel_pending.get(ctx.channel.id)
        if not msg_id:
            await ctx.send("No active drop to claim here. Keep chatting!")
            return
        drop = self._pending_drops.get(msg_id)
        if not drop or drop.get("claimed"):
            await ctx.send("Someone already grabbed it. 😤")
            return
        if self._now() > drop.get("expires", 0):
            await ctx.send("Drop expired. ⏰")
            return
        drop["claimed"] = True
        self._channel_pending.pop(ctx.channel.id, None)
        self._claimed_drops.add(msg_id)
        async with self.economy_lock:
            u = self._user(ctx.author.id)
            if self.economy["treasury"] <= 0:
                await ctx.send("The bank is empty. 💀 No drop payout.")
                return
            pay = min(drop["amount"], self.economy["treasury"])
            new_bal = u["balance"] + pay
            final_bal, skim = self._cap_wallet(new_bal)
            self.economy["treasury"] -= (pay - skim)
            u["balance"] = final_bal
            await self._save_bank()
        msg = (
            f"{ctx.author.mention} grabbed the drop for **{self._fmt_bread(pay)}**! "
            f"new: **{self._fmt_bread(u['balance'])}**"
        )
        if skim:
            msg += f" (cap skim **{self._fmt_bread(skim)}** back to bank)"
        await ctx.send(msg)

    @tasks.loop(seconds=10)
    async def chat_drop_watcher(self):
        now = self._now()
        expired = []
        for msg_id, info in list(self._pending_drops.items()):
            if info.get("claimed"):
                expired.append(msg_id)
                continue
            if now > info.get("expires", 0):
                expired.append(msg_id)
                ch = self.bot.get_channel(info["channel_id"])
                if ch:
                    try:
                        await ch.send("⏰ Drop expired. Keep chatting to trigger another!")
                    except Exception:
                        pass
                self._channel_pending.pop(info["channel_id"], None)
        for m in expired:
            self._pending_drops.pop(m, None)

    @chat_drop_watcher.before_loop
    async def _chatdrop_wait_ready(self):
        await self.bot.wait_until_ready()

# ===== Setup function =====
async def setup(bot: commands.Bot):
    helpers = bot.helpers
    await bot.add_cog(ChatDropCog(bot, helpers))
