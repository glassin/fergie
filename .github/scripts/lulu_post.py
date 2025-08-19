# .github/scripts/lulu_post.py
import os, re, random, sys
from datetime import datetime
from zoneinfo import ZoneInfo
import requests

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
LULU_URL = "https://shop.lululemon.com/c/women-whats-new/n16o10zq0cf?icid=home-homepage;L1;l2;cdp:womens-whats-new;"
MESSAGE = "thoughts girly? I need new fits. 💗🥹"

PT = ZoneInfo("America/Los_Angeles")
ABS_LINK_RE = re.compile(r'https://shop\.lululemon\.com[^"\s>]+/(?:p|product)/[^"\s>#]+', re.I)
REL_LINK_RE = re.compile(r'href="(/[^"\s>]+/(?:p|product)/[^"\s>#]+)"', re.I)
BASE = "https://shop.lululemon.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (GitHubActions; +https://github.com)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

def pick_daily_slot_pt(salt="fergie-1"):
    today = datetime.now(PT).date().isoformat()
    random.seed(f"{today}-{salt}")
    hour = random.randint(8, 13)          # 8..13 (14 excluded)
    minute = (random.randint(0, 59)//5)*5 # 0,5,...55
    return hour, minute

def current_slot_pt():
    now = datetime.now(PT)
    return now.hour, (now.minute//5)*5

def fetch_one_product_url():
    try:
        r = requests.get(LULU_URL, headers=HEADERS, timeout=20)
        r.raise_for_status()
        html = r.text
    except Exception as e:
        print(f"[skip] fetch error: {e}", file=sys.stderr)
        return None

    links = set(ABS_LINK_RE.findall(html))
    for m in REL_LINK_RE.findall(html):
        if m.startswith("/"):
            links.add(BASE + m)

    links = [u for u in links if "/p/" in u or "/product/" in u]
    if not links:
        return None
    random.shuffle(links)
    return links[0]

def send_webhook(url):
    data = {"content": f"{url}\n{MESSAGE}"}
    r = requests.post(WEBHOOK_URL, json=data, timeout=20)
    r.raise_for_status()

def main():
    if not WEBHOOK_URL:
        print("[error] missing DISCORD_WEBHOOK_URL", file=sys.stderr)
        sys.exit(1)

    # manual run: force a post now
    if os.environ.get("FORCE_NOW") == "1":
        link = fetch_one_product_url() or LULU_URL
        send_webhook(link)
        print(f"[ok] forced {link}")
        return

    # scheduled window: post only in today's chosen 5-min slot
    th, tm = pick_daily_slot_pt(os.environ.get("SALT", "fergie-1"))
    nh, nm = current_slot_pt()
    if (nh, nm) != (th, tm):
        print(f"[skip] now PT {nh:02d}:{nm:02d}, target {th:02d}:{tm:02d}")
        return

    link = fetch_one_product_url() or LULU_URL
    send_webhook(link)
    print(f"[ok] posted {link}")

if __name__ == "__main__":
    main()
