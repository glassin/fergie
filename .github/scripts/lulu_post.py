# .github/scripts/lulu_post.py
import os, random, sys
from datetime import datetime
from zoneinfo import ZoneInfo
import requests

# Discord webhook (already saved as a repo secret)
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
PT = ZoneInfo("America/Los_Angeles")

# ROTATING LINKS – posts a different one each day (in order)
LINKS = [
    "https://www.potterybarn.com/shop/holiday-decor/holiday-decor-halloween/",
    "https://www.aloyoga.com/collections/new-arrivals",
    "https://www.anthropologie.com/new-clothes",
    "https://www.freepeople.com/whats-new/",
    # keep Lululemon too so it stays in the rotation (optional—remove if you don’t want it)
    "https://shop.lululemon.com/c/women-whats-new/n16o10zq0cf?icid=home-homepage;L1;l2;cdp:womens-whats-new;",
]

MESSAGE = "thoughts girly? I need new fits. 💗🥹"

def pick_daily_slot_pt(salt="fergie-1"):
    """Choose ONE 5-minute slot between 08:00–13:55 PT for TODAY (deterministic)."""
    today = datetime.now(PT).date().isoformat()
    random.seed(f"{today}-{salt}")
    hour = random.randint(8, 13)             # 8..13 (14:00 exclusive)
    minute = (random.randint(0, 59)//5)*5    # 0,5,10,...,55
    return hour, minute

def current_slot_pt():
    now = datetime.now(PT)
    return now.hour, (now.minute//5)*5

def pick_link_for_today(offset=0):
    """Rotate through LINKS once per day (PT)."""
    today = datetime.now(PT).date()
    # days since a fixed epoch (Jan 1, 2020) -> stable daily index
    epoch = datetime(2020, 1, 1, tzinfo=PT).date()
    days = (today - epoch).days + int(offset)
    return LINKS[days % len(LINKS)]

def send_webhook(content: str):
    r = requests.post(WEBHOOK_URL, json={"content": content}, timeout=20)
    r.raise_for_status()

def main():
    if not WEBHOOK_URL:
        print("[error] missing DISCORD_WEBHOOK_URL", file=sys.stderr)
        sys.exit(1)

    # Allow manual test: post immediately, ignoring the time window
    if os.environ.get("FORCE_NOW") == "1":
        offset = os.environ.get("LINK_OFFSET", "0")
        link = pick_link_for_today(offset)
        send_webhook(f"{link}\n{MESSAGE}")
        print(f"[ok] forced {link}")
        return

    # Scheduled mode: only post in today's chosen 5-min slot
    th, tm = pick_daily_slot_pt(os.environ.get("SALT", "fergie-1"))
    nh, nm = current_slot_pt()
    if (nh, nm) != (th, tm):
        print(f"[skip] now PT {nh:02d}:{nm:02d}, target {th:02d}:{tm:02d}")
        return

    offset = os.environ.get("LINK_OFFSET", "0")
    link = pick_link_for_today(offset)
    send_webhook(f"{link}\n{MESSAGE}")
    print(f"[ok] posted {link}")

if __name__ == "__main__":
    main()
