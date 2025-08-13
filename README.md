
# Bread Bot (Minimal)

A tiny Discord bot that:
- Replies randomly with bread GIFs or bread puns (no pings)
- Posts bread content every 4 hours
- Posts a bread emoji every 6 hours

## Hosting (Railway example)
1. Push these files to a new GitHub repo.
2. Go to https://railway.app → New Project → Deploy from GitHub.
3. Add Environment Variables:
   - DISCORD_TOKEN = your bot token
   - TENOR_API_KEY = your Tenor key
   - CHANNEL_ID = numeric channel ID
   - (optional) BREAD_EMOJI = default 🍞
4. Start command: `python bot.py`
5. Deploy.
