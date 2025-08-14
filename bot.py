# ================== Custom Help: !halp ==================
from discord import Embed, Colour

def _mention_channel(ch_id: int) -> str:
    return f"<#{ch_id}>" if ch_id else "`(not set)`"

@bot.command(name="halp", help="Shows an embedded help menu")
async def halp(ctx, *, command: str | None = None):
    # If a specific command is requested: show its detailed help
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

    # Main menu embed
    e = Embed(
        title="🍞 Bot Help",
        description="Here’s everything I can do. Use `!halp <command>` for details on one command.",
        colour=Colour.blurple()
    )

    # Quick tips/top notes
    e.add_field(
        name="Notes",
        value=(
            f"• Casino commands only work in {_mention_channel(GAMBLE_CHANNEL_ID)}\n"
            f"• `!fit` only works in {_mention_channel(FIT_CHANNEL_ID)}\n"
            f"• `!kewchie` only works in {_mention_channel(KEWCHIE_CHANNEL_ID)}"
        ),
        inline=False
    )

    # Economy
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

    # Casino / Gambling (restricted channel)
    e.add_field(
        name="🎲 Casino (only in casino channel)",
        value=(
            "`!roll <amount|all|half>` — Bet vs bank (win prob scales; jackpot on `all`)\n"
            "`!putasos @user` — Try to rob someone (low success, fail hurts)"
        ),
        inline=False
    )

    # Fun / Media
    e.add_field(
        name="🎉 Fun & Media",
        value=(
            "`!cafe [term]` — Random GIF (defaults to coffee)\n"
            "`!scam` — BTC/ETH prices (bratty style)\n"
            "`!bbl` — The ultimate BBL GIF\n"
            "`!hawaii` — Random Hawaii pic / Eddie Murphy GIF"
        ),
        inline=False
    )

    # Fit
    e.add_field(
        name="👗 Fit (fashion)",
        value=(
            "`!fit` — Drop a random fit pic (fit channel only). If a specific user replies within 20s, "
            "I send a cheeky follow-up."
        ),
        inline=False
    )

    # Kewchie (Kali Uchis)
    e.add_field(
        name="🎵 Kewchie (Kali Uchis)",
        value=(
            "`!kewchie` — Post a random playlist track (kewchie channel only)\n"
            "`!kewchie-debug` — Debug Spotify playlist setup"
        ),
        inline=False
    )

    # Admin
    e.add_field(
        name="🛠️ Admin (Manage Server required)",
        value=(
            "`!seed bank <amt>` — Refill bank (to cap)\n"
            "`!seed @user <amt>` — Give bread (respects wallet cap)\n"
            "`!take bank <amt>` — Burn from bank\n"
            "`!take @user <amt>` — Take from user to bank\n"
            "`!setbal @user <amt>` — Set a user’s exact balance (capped to wallet)"
        ),
        inline=False
    )

    # Hidden/automatic behaviors (useful to know)
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
