# .github/scripts/lulu_post.py
import os, re, random, sys
from datetime import datetime
from zoneinfo import ZoneInfo
import requests

# 👇 same name you'll add in GitHub Secrets
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# Page to scrape (Women -> What's New)
LULU_URL = "https://shop.lululemon.com/c/women-whats-new/n16o10zq0cf?icid=home-homepage;L1;l2;cdp:womens-whats-new;"
MESSAGE = "thoughts girly? I need new fits. 💗🥹"

PT = ZoneInfo("America/Los_Angeles")
ABS_LINK_RE = re.compile(r'https://shop\.lululemon\.com[^"\s>]+/(?:p|product)/[^"\s>#]+', re.I)
REL_LINK_RE = re.compile(r'href="(/[^"\s>]+/(?:p|product)/[^"\s>#]+)"', re.I)
BASE = "https://shop.lululemon.com"

def pick_daily_slot_pt(salt=""):
    """Choose ONE 5-minute slot between 08:00–13:55 PT for TODAY (deterministic)."""
    today = datetime.now(PT).date().isoformat()
    random.seed(f"{today}-{salt}")
    hour = random.randint(8, 13)          # 8..13 (14:00 exclusive)
    minute = (random.randint(0, 59)//5)*5 # 0,5,10,...55
    return hour, minute

def current_slot_pt():
    now = datetime.now(PT)
    return now.hour, (now.minute//5)*5

def fetch_one_product_url():
    """Download page HTML, extract product links, pick one at random."""
    try:
        r = requests.get(LULU_URL, headers={"User-Agent":"Mozilla/5.0"}, timeout=20)
        r.raise_for_status()
        html = r.text
    except Exception as e:
        print(f"[skip] fetch error: {e}", file=sys.stderr)
        return None

    links = set(ABS_LINK_RE.findall(html))
    for m in REL_LINK_RE.findall(html):
        if m.startswith("/"):
            links.add(BASE + m)

    # keep only product pages
    links = [u for u in links if "/p/" in u or "/product/" in u]
    if not links:
        return None
    random.shuffle(links)
    return links[0]

def send_webhook(url):
    r = requests.post(WEBHOOK_URL, json={"content": f"{url}\n{MESSAGE}"}, timeout=20)
    r.raise_for_status()

def main():
    if not WEBHOOK_URL:
        print("[error] missing DISCORD_WEBHOOK_URL secret", file=sys.stderr)
        sys.exit(1)

    # allow manual one-off test
    if os.environ.get("FORCE_NOW") == "1":
        link = fetch_one_product_url()
        if link:
            send_webhook(link)
            print(f"[ok] forced post {link}")
        else:
            print("[skip] no product links found")
        return

    # scheduled mode: only post in today's chosen slot
    salt = os.environ.get("SALT", "fergie-1")
    target_h, target_m = pick_daily_slot_pt(salt)
    now_h, now_m = current_slot_pt()
    if (now_h, now_m) != (target_h, target_m):
        print(f"[skip] now PT {now_h:02d}:{now_m:02d}, target {target_h:02d}:{target_m:02d}")
        return

    link = fetch_one_product_url()
    if not link:
        print("[skip] no product links found")
        return

    send_webhook(link)
    print(f"[ok] posted {link}")

if __name__ == "__main__":
    main()
