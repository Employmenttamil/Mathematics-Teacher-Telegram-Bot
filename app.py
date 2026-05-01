import os
import logging
import requests
import base64
from flask import Flask, request, jsonify

# Configuration
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# Models
TEXT_MODEL = "llama-3.3-70b-versatile"
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

MATH_DETECTION_PROMPT = """You are a classifier. Determine if the following message is a math-related question, math problem, or math doubt.
Reply ONLY with "YES" if it is math-related, or "NO" if it is not.
Do not explain. Just reply YES or NO.

Message: {message}"""

MATH_SOLVE_PROMPT = """You are a professional math teacher. Solve the following math problem.

Rules:
- Use shortcut methods if possible
- Explain the solution in Tamil language (Tamil script)
- Use relevant emojis in your response
- Be clear and concise
- Format the math expressions clearly
- Do NOT use markdown formatting like **, ##, __, ``` or $. Use plain text only.
- Do NOT use LaTeX formatting.

Problem: {problem}"""

IMAGE_MATH_DETECTION_PROMPT = """Look at this image. Is this a math problem, math question, or contains mathematical content that needs solving?
Reply ONLY with "YES" if it contains math to solve, or "NO" if it does not.
Do not explain. Just reply YES or NO."""

IMAGE_MATH_SOLVE_PROMPT = """You are a professional math teacher. Look at this image containing a math problem and solve it.

Rules:
- Use shortcut methods if possible
- Explain the solution in Tamil language (Tamil script)
- Use relevant emojis in your response
- Be clear and concise
- Format the math expressions clearly
- Do NOT use markdown formatting like **, ##, __, ``` or $. Use plain text only.
- Do NOT use LaTeX formatting.

Solve the math problem shown in the image."""


def groq_chat(messages, model=TEXT_MODEL, max_tokens=1000):
    """Call Groq API."""
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.3
    }
    try:
        resp = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        return None


def send_message(chat_id, text, reply_to_message_id=None):
    """Send a message to a Telegram chat."""
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "reply_to_message_id": reply_to_message_id
    }
    try:
        resp = requests.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return None


def get_user_mention(user):
    """Create a mention tag for the user."""
    if user.get("username"):
        return f"@{user['username']}"
    else:
        first_name = user.get("first_name", "")
        user_id = user.get("id", "")
        return f'<a href="tg://user?id={user_id}">{first_name}</a>'


def is_math_question(text):
    """Use Groq to detect if a message is math-related."""
    prompt = MATH_DETECTION_PROMPT.format(message=text)
    messages = [{"role": "user", "content": prompt}]
    result = groq_chat(messages, model=TEXT_MODEL, max_tokens=10)
    if result:
        return "YES" in result.strip().upper()
    return False


def solve_math_text(problem):
    """Use Groq to solve a math problem from text."""
    prompt = MATH_SOLVE_PROMPT.format(problem=problem)
    messages = [{"role": "user", "content": prompt}]
    return groq_chat(messages, model=TEXT_MODEL, max_tokens=1500)


def download_telegram_photo(file_id):
    """Download a photo from Telegram and return base64."""
    try:
        resp = requests.get(f"{TELEGRAM_API}/getFile", params={"file_id": file_id}, timeout=15)
        resp.raise_for_status()
        file_path = resp.json()["result"]["file_path"]

        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        file_resp = requests.get(file_url, timeout=30)
        file_resp.raise_for_status()

        return base64.b64encode(file_resp.content).decode("utf-8")
    except Exception as e:
        logger.error(f"Error downloading photo: {e}")
        return None


def is_math_image(image_base64):
    """Use Groq vision model to detect if an image contains math."""
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": IMAGE_MATH_DETECTION_PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
            ]
        }
    ]
    result = groq_chat(messages, model=VISION_MODEL, max_tokens=10)
    if result:
        return "YES" in result.strip().upper()
    return False


def solve_math_image(image_base64):
    """Use Groq vision model to solve math from an image."""
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": IMAGE_MATH_SOLVE_PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
            ]
        }
    ]
    return groq_chat(messages, model=VISION_MODEL, max_tokens=1500)


def add_shop_link(text):
    """Add the shop hyperlink at the end of every response."""
    return text + '\n\n🛒 <a href="https://employmenttamil.in/shop/">விற்பனை நிலையம்</a>'


@app.route("/", methods=["GET"])
def index():
    return "Math Teacher Bot is running! 📐✏️", 200


@app.route("/webhook", methods=["POST"])
def webhook():
    """Handle incoming Telegram updates."""
    try:
        update = request.get_json()
        if not update:
            return jsonify({"ok": True}), 200

        message = update.get("message")
        if not message:
            return jsonify({"ok": True}), 200

        chat_id = message["chat"]["id"]
        message_id = message["message_id"]
        user = message.get("from", {})
        user_mention = get_user_mention(user)

        # Handle text messages
        if "text" in message:
            text = message["text"]

            # Skip bot commands and very short messages
            if text.startswith("/") or len(text) < 3:
                return jsonify({"ok": True}), 200

            # Check if it's a math question
            if is_math_question(text):
                solution = solve_math_text(text)
                if solution:
                    reply = f"📝 {user_mention}\n\n{solution}"
                    reply = add_shop_link(reply)
                    send_message(chat_id, reply, reply_to_message_id=message_id)

        # Handle photo messages
        elif "photo" in message:
            # Get the largest photo
            photo = message["photo"][-1]
            file_id = photo["file_id"]

            # Download the photo as base64
            image_base64 = download_telegram_photo(file_id)
            if image_base64:
                # Check if it contains math
                if is_math_image(image_base64):
                    solution = solve_math_image(image_base64)
                    if solution:
                        reply = f"📝 {user_mention}\n\n{solution}"
                        reply = add_shop_link(reply)
                        send_message(chat_id, reply, reply_to_message_id=message_id)

        return jsonify({"ok": True}), 200

    except Exception as e:
        logger.error(f"Error processing update: {e}")
        return jsonify({"ok": True}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
