import os
import logging
import requests
from flask import Flask, request, jsonify
from google import genai
from google.genai import types
import tempfile
import base64

# Configuration
BOT_TOKEN = os.environ.get("BOT_TOKEN", "6267222413:AAGIRbdQEj5fNQSGS3oLOhAju7a5QSgOHx4")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyBVrxuJiIlYqgzqRAbC_90XxwJ1npCfBBc")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Gemini client
client = genai.Client(api_key=GEMINI_API_KEY)
MODEL = "gemini-2.0-flash"

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
- Do NOT use markdown formatting like ** or __ or ``` for bold/italic/code. Use plain text only.

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
- Do NOT use markdown formatting like ** or __ or ``` for bold/italic/code. Use plain text only.

Solve the math problem shown in the image."""


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
    """Use Gemini to detect if a message is math-related."""
    try:
        prompt = MATH_DETECTION_PROMPT.format(message=text)
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt
        )
        result = response.text.strip().upper()
        return "YES" in result
    except Exception as e:
        logger.error(f"Error in math detection: {e}")
        return False


def solve_math_text(problem):
    """Use Gemini to solve a math problem from text."""
    try:
        prompt = MATH_SOLVE_PROMPT.format(problem=problem)
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"Error solving math: {e}")
        return None


def download_telegram_photo(file_id):
    """Download a photo from Telegram and return bytes."""
    try:
        # Get file path
        resp = requests.get(f"{TELEGRAM_API}/getFile", params={"file_id": file_id}, timeout=15)
        resp.raise_for_status()
        file_path = resp.json()["result"]["file_path"]

        # Download file
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        file_resp = requests.get(file_url, timeout=30)
        file_resp.raise_for_status()

        return file_resp.content
    except Exception as e:
        logger.error(f"Error downloading photo: {e}")
        return None


def is_math_image(image_bytes):
    """Use Gemini to detect if an image contains math."""
    try:
        image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
        response = client.models.generate_content(
            model=MODEL,
            contents=[IMAGE_MATH_DETECTION_PROMPT, image_part]
        )
        result = response.text.strip().upper()
        return "YES" in result
    except Exception as e:
        logger.error(f"Error in image math detection: {e}")
        return False


def solve_math_image(image_bytes):
    """Use Gemini to solve math from an image."""
    try:
        image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
        response = client.models.generate_content(
            model=MODEL,
            contents=[IMAGE_MATH_SOLVE_PROMPT, image_part]
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"Error solving math from image: {e}")
        return None


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

            # Download the photo
            image_bytes = download_telegram_photo(file_id)
            if image_bytes:
                # Check if it contains math
                if is_math_image(image_bytes):
                    solution = solve_math_image(image_bytes)
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
