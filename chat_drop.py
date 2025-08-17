import os
import random
import asyncio
import discord
from discord.ext import commands

class ChatDropCog(commands.Cog):
    def __init__(self, bot, helpers):
        self.bot = bot
        self.helpers = helpers

        # Config from env or defaults
        self.chance = float(os.getenv("CHATDROP_CHANCE", 0.22))
        self.min_interval = int(os.getenv("CHATDROP_MIN_INTERVAL_SEC", 60))
        self.max_interval = int(os.getenv("CHATDROP_MAX_INTERVAL_SEC", 420))
        self.window = int(os.getenv("CHATDROP_WINDOW_SEC", 120))
        self.claim_window = int(os.getenv("CHATDROP_CLAIM_WINDOW_SEC", 25))
        self.emoji = os.getenv("CHATDROP_REACTION_EMOJI", "<:autistic_hug:1131707829611413524>")
        self.embed_color = int(os.getenv("CHATDROP_EMBED_COLOR", "0xF4A261"), 16)

        self._active_drops = {}  # channel_id -> message

    # Quick ping check
    @commands.command(name="cdping")
    async def cdping(self, ctx):
        await ctx.send("ChatDrop is loaded ✅")

    # Debug info
    @commands.command(name="chatdrop_debug")
    async def chatdrop_debug(self, ctx):
        info = (
            f"Chance: {self.chance}\n"
            f"Interval: {self.min_interval}-{self.max_interval}s\n"
            f"Window: {self.window}s\n"
            f"Claim window: {self.claim_window}s\n"
            f"Emoji: {self.emoji}\n"
            f"Active drops: {list(self._active_drops.keys())}"
        )
        await ctx.send(f"```{info}```")

    # Force a drop now
    @commands.command(name="dropnow")
    async def dropnow(self, ctx):
        await self.spawn_drop(ctx.channel)

    # Core message listener
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        # Random chance to spawn drop
        if random.random() < self.chance:
            await self.spawn_drop(message.channel)

    async def spawn_drop(self, channel):
        if channel.id in self._active_drops:
            return  # already active

        embed = discord.Embed(
            title="🎁 A drop appeared!",
            description=f"React with {self.emoji} or type `!get` within {self.claim_window}s!",
            color=self.embed_color,
        )
        drop_msg = await channel.send(embed=embed)
        self._active_drops[channel.id] = drop_msg

        # Add reaction if emoji is unicode or custom
        try:
            await drop_msg.add_reaction(self.emoji)
        except Exception:
            pass

        def check_react(reaction, user):
            return (
                str(reaction.emoji) == str(self.emoji)
                and reaction.message.id == drop_msg.id
                and not user.bot
            )

        def check_msg(m):
            return m.content.lower().startswith("!get") and m.channel == channel and not m.author.bot

        claimed = None
        try:
            done, _ = await asyncio.wait(
                [
                    self.bot.wait_for("reaction_add", check=check_react, timeout=self.claim_window),
                    self.bot.wait_for("message", check=check_msg, timeout=self.claim_window),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in done:
                result = task.result()
                if isinstance(result, tuple):  # reaction_add
                    claimed = result[1]
                else:  # message
                    claimed = result.author
        except asyncio.TimeoutError:
            pass

        if claimed:
            await channel.send(f"🎉 {claimed.mention} claimed the drop!")
        else:
            await channel.send("⏳ Nobody claimed the drop...")

        self._active_drops.pop(channel.id, None)
