"""
Run this script AFTER deploying to Render to set the webhook URL.
Replace YOUR_RENDER_URL with your actual Render service URL.

Usage:
    python set_webhook.py https://your-app-name.onrender.com
"""

import sys
import requests

BOT_TOKEN = "6267222413:AAGIRbdQEj5fNQSGS3oLOhAju7a5QSgOHx4"

if len(sys.argv) < 2:
    print("Usage: python set_webhook.py <YOUR_RENDER_URL>")
    print("Example: python set_webhook.py https://math-teacher-bot.onrender.com")
    sys.exit(1)

render_url = sys.argv[1].rstrip("/")
webhook_url = f"{render_url}/webhook"

response = requests.get(
    f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
    params={"url": webhook_url}
)

print(f"Setting webhook to: {webhook_url}")
print(f"Response: {response.json()}")
