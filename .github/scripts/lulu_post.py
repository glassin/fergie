import os
import random
import requests

# 🔹 Replace this with your actual Discord webhook URL
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# 🔹 Lululemon "What's New" page (you could expand this later to scrape links)
LULU_URLS = [
    "https://shop.lululemon.com/c/women-whats-new/n16o10zq0cf?icid=home-homepage;L1;l2;cdp:womens-whats-new;"
]

def main():
    if not WEBHOOK_URL:
        print("❌ Missing DISCORD_WEBHOOK_URL environment variable")
        return

    # Pick a random link (for now it’s just the one)
    link = random.choice(LULU_URLS)

    # Message text
    content = f"thoughts girly? I need new fits. 💖🥺\n{link}"

    # Send to Discord
    data = {"content": content}
    response = requests.post(WEBHOOK_URL, json=data)

    if response.status_code == 204:
        print("✅ Successfully posted to Discord")
    else:
        print(f"❌ Failed: {response.status_code}, {response.text}")

if __name__ == "__main__":
    main()
