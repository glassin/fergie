import os
import random
import asyncio
import discord
from discord.ext import commands

class ChatDropCog(commands.Cog):
    def __init__(self, bot, helpers):
        self.bot = bot
        self.helpers = helpers
        self.drops = {}  # channel_id -> drop info

        # Config from env or defaults
        self.chance = float(os.getenv("CHATDROP_CHANCE", "0.05"))
        self.min_interval = int(os.getenv("CHATDROP_MIN_INTERVAL_SEC", "30"))
        self.window = int(os.getenv("CHATDROP_WINDOW_SEC", "60"))
        self.claim_window = int(os.getenv("CHATDROP_CLAIM_WINDOW_SEC", "90"))
        self.reaction_emoji = os.getenv("CHATDROP_REACTION_EMOJI", "🍞")

        self.last_drop_time = {}

    def _emoji_match(self, payload):
        if payload.emoji.is_custom_emoji():
            return str(payload.emoji) == self.reaction_emoji
        else:
            return str(payload.emoji) == self.reaction_emoji

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        channel_id = message.channel.id
        now = self.helpers["now"]()

        last_time = self.last_drop_time.get(channel_id, 0)
        if now - last_time < self.min_interval:
            return

        if random.random() <= self.chance:
            await self.start_drop(message.channel)

    async def start_drop(self, channel):
        bread_amt = random.randint(1, 25)
        drop_msg = await channel.send(
            embed=discord.Embed(
                title="🍞 Bread drop!",
                description=f"React with {self.reaction_emoji} or type `!get` to claim {bread_amt} bread!",
                color=discord.Color.gold(),
            )
        )

        try:
            await drop_msg.add_reaction(self.reaction_emoji)
        except discord.Forbidden:
            pass

        self.drops[channel.id] = {
            "amount": bread_amt,
            "msg_id": drop_msg.id,
            "expires": self.helpers["now"]() + self.claim_window,
            "claimed": False,
        }
        self.last_drop_time[channel.id] = self.helpers["now"]()

        await asyncio.sleep(self.claim_window)
        drop = self.drops.get(channel.id)
        if drop and not drop["claimed"]:
            await channel.send("Nobody claimed the bread drop in time!")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return

        drop = self.drops.get(payload.channel_id)
        if not drop or drop["claimed"]:
            return
        if not self._emoji_match(payload):
            return

        guild = self.bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        await self.give_bread(member, drop, payload.channel_id)

    @commands.command()
    async def get(self, ctx: commands.Context):
        drop = self.drops.get(ctx.channel.id)
        if not drop or drop["claimed"]:
            await ctx.send("No bread drop to claim right now.")
            return
        await self.give_bread(ctx.author, drop, ctx.channel.id)

    async def give_bread(self, member, drop, channel_id):
        if drop["claimed"]:
            return
        drop["claimed"] = True

        async with self.helpers["economy_lock"]:
            wallet = self.helpers["get_user"](member.id)
            wallet["bread"] = wallet.get("bread", 0) + drop["amount"]
            self.helpers["save_bank"]()

        channel = self.bot.get_channel(channel_id)
        await channel.send(
            f"{member.mention} claimed {drop['amount']} bread! 🥖"
        )

    @commands.command()
    @commands.has_permissions(manage_guild=True)
async def setup(bot):
    await bot.add_cog(ChatDropCog(bot))
    print(
        f"✅ ChatDrop loaded | Chance={ChatDropCog.CHATDROP_CHANCE} | "
        f"MinInterval={ChatDropCog.CHATDROP_MIN_INTERVAL_SEC}s | "
        f"Window={ChatDropCog.CHATDROP_WINDOW_SEC}s | "
        f"ClaimWindow={ChatDropCog.CHATDROP_CLAIM_WINDOW_SEC}s"
    )



    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def dropnow(self, ctx):
        await self.start_drop(ctx.channel)
