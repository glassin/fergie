
import os
import re
import random
import asyncio
import discord
from collections import deque, Counter
from discord.ext import tasks, commands


class ChatDropCog(commands.Cog):
    """
    Safe plug-in Cog that adds "chat activity" bread drops.
    - Spawns a drop message when a channel is active.
    - First user to react with the configured emoji OR type !get wins.
    - Uses helpers (economy, locks, fmt) provided by the main bot.
    """

    def __init__(self, bot: commands.Bot, helpers: dict):
        self.bot = bot

        # === Pull helpers from main bot (no duplication of logic) ===
        self._now         = helpers["now"]
        self._fmt_bread   = helpers["fmt_bread"]
        self._cap_wallet  = helpers["cap_wallet"]
        self._user        = helpers["get_user"]
        self._save_bank   = helpers["save_bank"]
        self.economy      = helpers["economy"]
        self.economy_lock = helpers["economy_lock"]

        # === Tunables (env-override friendly) ===
        self.min_interval = int(os.getenv("CHATDROP_MIN_INTERVAL_SEC", "60"))
        self.max_interval = int(os.getenv("CHATDROP_MAX_INTERVAL_SEC", "420"))
        self.decay_secs   = int(os.getenv("CHATDROP_DECAY_SEC", "180"))
        self.window_secs  = int(os.getenv("CHATDROP_WINDOW_SEC", "120"))
        self.claim_window = int(os.getenv("CHATDROP_CLAIM_WINDOW_SEC", "25"))
        self.chance       = float(os.getenv("CHATDROP_CHANCE", "0.22"))
        self.amounts      = [2, 5, 10, 20]

        # Emoji can be unicode or custom (<:name:id> or <a:name:id>)
        self.reaction_emoji = os.getenv("CHATDROP_REACTION_EMOJI", "🍞")
        self.embed_color    = int(os.getenv("CHATDROP_EMBED_COLOR", str(0xF4A261)))

        # Parse custom emoji id if provided
        self._emoji_id = None
        m = re.match(r"^<a?:\\w+:(\\d+)>$", str(self.reaction_emoji))
        if m:
            try:
                self._emoji_id = int(m.group(1))
            except Exception:
                self._emoji_id = None

        # === Runtime state ===
        self.activity: dict[int, deque[float]] = {}      # channel_id -> deque[timestamps]
        self.last_drop: dict[int, float] = {}            # channel_id -> last drop ts
        self.drops: dict[int, dict] = {}                 # message_id -> drop info
        self.pending_by_channel: dict[int, int] = {}     # channel_id -> message_id

        # Start expiry watcher
        self.chat_drop_watcher.start()

    # ---------- Utilities ----------
    def _prune(self, q: deque, now_ts: float):
        cutoff = now_ts - self.window_secs
        while q and q[0] < cutoff:
            q.popleft()

    def _bump_activity(self, ch_id: int):
        now_ts = self._now()
        q = self.activity.get(ch_id)
        if q is None:
            q = deque()
            self.activity[ch_id] = q
        q.append(now_ts)
        self._prune(q, now_ts)

    def _is_channel_active(self, ch_id: int) -> bool:
        now_ts = self._now()
        q = self.activity.get(ch_id, deque())
        self._prune(q, now_ts)
        # consider active if >=4 messages in sliding window
        return len(q) >= 4

    def _can_drop(self, ch_id: int) -> bool:
        now_ts = self._now()
        last = self.last_drop.get(ch_id, 0.0)
        return (now_ts - last) >= self.min_interval and (ch_id not in self.pending_by_channel)

    async def _create_drop(self, channel: discord.abc.Messageable, ch_id: int):
        amt = random.choice(self.amounts)
        embed = discord.Embed(
            title="Bread drop!",
            description=(
                f"First to react with {self.reaction_emoji} **or** type `!get` wins **{self._fmt_bread(amt)}**.\n"
                f"Hurry! Expires in {self.claim_window}s."
            ),
            colour=self.embed_color
        )
        msg = await channel.send(embed=embed)

        # Try to add the reaction; custom emoji if available
        try:
            emoji_to_add = self.reaction_emoji
            if self._emoji_id and getattr(channel, "guild", None):
                em = discord.utils.get(channel.guild.emojis, id=self._emoji_id)
                if em:
                    emoji_to_add = em
            await msg.add_reaction(emoji_to_add)
        except Exception:
            # If cannot react (missing emoji/permissions), ignore
            pass

        expires_at = self._now() + self.claim_window
        self.drops[msg.id] = {"amount": amt, "expires": expires_at, "channel_id": ch_id, "claimed": False}
        self.pending_by_channel[ch_id] = msg.id
        self.last_drop[ch_id] = self._now()

    # ---------- Listeners / Commands ----------
    @commands.Cog.listener("on_message")
    async def _activity_listener(self, message: discord.Message):
        # Coexists with your main on_message; bail for bots/DMs
        if not message.guild or message.author.bot:
            return

        ch_id = message.channel.id

        # Don't count commands as activity
        if message.content and message.content.strip().startswith("!"):
            return

        # Bump and maybe create a drop
        self._bump_activity(ch_id)

        # Soft decay after long silence
        if (self._now() - self.last_drop.get(ch_id, 0.0)) > self.max_interval:
            self.activity[ch_id] = deque()

        if self._is_channel_active(ch_id) and self._can_drop(ch_id):
            if random.random() < self.chance:
                await self._create_drop(message.channel, ch_id)

    def _emoji_match(self, payload: discord.RawReactionActionEvent) -> bool:
        """True if payload matches our configured emoji (unicode or custom)."""
        if self._emoji_id:
            return (payload.emoji and payload.emoji.id == self._emoji_id)
        return str(payload.emoji) == str(self.reaction_emoji)

    @commands.Cog.listener("on_raw_reaction_add")
    async def _claim_by_reaction(self, payload: discord.RawReactionActionEvent):
        # ignore bot self-reactions
        if not self.bot.user or payload.user_id == self.bot.user.id:
            return

        if not self._emoji_match(payload):
            return

        drop = self.drops.get(payload.message_id)
        if not drop or drop.get("claimed"):
            return
        if self._now() > drop.get("expires", 0):
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

        await self._give_bread(member, drop, channel)

    @commands.command(name="get", help="Claim the active bread drop in this channel")
    async def get(self, ctx: commands.Context):
        msg_id = self.pending_by_channel.get(ctx.channel.id)
        if not msg_id or msg_id not in self.drops:
            await ctx.send("No active drop to claim here. Keep chatting!")
            return

        drop = self.drops.get(msg_id)
        if not drop or drop.get("claimed"):
            await ctx.send("Someone already grabbed it. 😤")
            return
        if self._now() > drop.get("expires", 0):
            await ctx.send("Drop expired. ⏰")
            return

        await self._give_bread(ctx.author, drop, ctx.channel)

    async def _give_bread(self, member: discord.Member, drop: dict, channel: discord.abc.Messageable):
        # Mark claimed once to avoid races
        if drop.get("claimed"):
            return
        drop["claimed"] = True
        self.pending_by_channel.pop(drop["channel_id"], None)

        # Payout guarded by economy_lock
        async with self.economy_lock:
            u = self._user(member.id)
            if self.economy.get("treasury", 0) <= 0:
                try:
                    await channel.send(f"{member.mention} The bank is empty. 💀 No drop payout.")
                except Exception:
                    pass
                return

            pay = min(int(drop["amount"]), int(self.economy.get("treasury", 0)))
            new_bal = int(u.get("balance", 0)) + pay
            final_bal, skim = self._cap_wallet(new_bal)
            self.economy["treasury"] = int(self.economy.get("treasury", 0)) - (pay - skim)
            u["balance"] = final_bal
            await self._save_bank()

        try:
            msg = (
                f"{member.mention} grabbed the drop for **{self._fmt_bread(pay)}**! "
                f"new: **{self._fmt_bread(u['balance'])}**"
            )
            if skim:
                msg += f" (cap skim **{self._fmt_bread(skim)}** back to bank)"
            await channel.send(msg)
        except Exception:
            pass

    # Optional admin debug to verify settings at runtime
    @commands.command(name="chatdrop_debug")
    @commands.has_permissions(manage_guild=True)
    async def chatdrop_debug(self, ctx: commands.Context):
        ch_id = ctx.channel.id
        drop = self.drops.get(self.pending_by_channel.get(ch_id, 0))
        status = "active" if drop and not drop.get("claimed") else "none"
        text = (
            "✅ ChatDrop loaded\n"
            f"Chance={self.chance} · MinInterval={self.min_interval}s · Window={self.window_secs}s · "
            f"ClaimWindow={self.claim_window}s · ActiveDrop={status}\n"
            f"Emoji={self.reaction_emoji}\n"
        )
        await ctx.send(f"```{text}```")

    # ---------- Expiry watcher ----------
    @tasks.loop(seconds=10)
    async def chat_drop_watcher(self):
        now = self._now()
        expired_ids = []
        for msg_id, info in list(self.drops.items()):
            if info.get("claimed"):
                expired_ids.append(msg_id)
                continue
            if now > info.get("expires", 0):
                expired_ids.append(msg_id)
                ch = self.bot.get_channel(info["channel_id"])
                if ch:
                    try:
                        await ch.send("⏰ Drop expired. Keep chatting to trigger another!")
                    except Exception:
                        pass
                self.pending_by_channel.pop(info["channel_id"], None)
        for mid in expired_ids:
            self.drops.pop(mid, None)

    @chat_drop_watcher.before_loop
    async def _wait_ready(self):
        await self.bot.wait_until_ready()
